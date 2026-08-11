import pytest

from stock_lab.jobs.daily_update import (
    DAILY_UPDATE_LOCK_KEY,
    backfill_daily_updates,
    daily_update_completion_key,
    run_daily_update,
)
from stock_lab.modules.market_data.jiuyan import HumanVerificationRequired
from stock_lab.shared.errors import JobExecutionError


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.expiries = {}

    def exists(self, key):
        return key in self.values

    def set(self, key, value, *, nx=False, ex=None):
        if nx and key in self.values:
            return False
        self.values[key] = value
        self.expiries[key] = ex
        return True

    def eval(self, _script, _key_count, key, token):
        if self.values.get(key) != token:
            return 0
        self.values.pop(key)
        return 1


class FakeCollector:
    def __init__(self, dates=None, calls=None):
        self.dates = dates or [20260804, 20260805]
        self.calls = calls if calls is not None else []

    def trading_dates(self, limit):
        assert limit == 160
        self.calls.append("trading_dates")
        return self.dates

    def update_securities(self):
        self.calls.append("securities")
        return 1

    def update_daily_quotes(self, start_date, end_date):
        self.calls.append(("daily_quotes", start_date, end_date))
        return 2

    def update_index_daily(self, start_date, end_date):
        self.calls.append(("index_daily", start_date, end_date))
        return 3

    def collect_board_actions(self, trade_date):
        self.calls.append(("board_actions", trade_date))
        return {
            "status": "success",
            "updated": 7,
            "trade_date": trade_date,
            "export_paths": ["7_全部.ini"],
            "warnings": [],
        }

    def update_market_cap(self, trade_date):
        self.calls.append(("market_cap", trade_date))
        return {"status": "success", "updated": 4, "failed_dates": []}

    def update_dde(self, trade_date):
        self.calls.append(("dde", trade_date))
        return {"status": "success", "updated": 5, "failed": []}

    def update_kdj(self, trade_date):
        self.calls.append(("kdj", trade_date))
        return 6


def test_daily_update_runs_sources_before_analysis_and_marks_completion():
    calls = []
    redis = FakeRedis()
    collector = FakeCollector(calls=calls)

    result = run_daily_update(
        "2026-08-05",
        collector=collector,
        state=redis,
        run_hot_board=lambda date, source: calls.append(("hot_board", date, source)) or 8,
        run_index=lambda date: calls.append(("index_emotion", date)) or 9,
    )

    assert calls == [
        "trading_dates",
        ("index_daily", 20260804, 20260805),
        "securities",
        ("daily_quotes", 20260804, 20260805),
        ("market_cap", 20260805),
        ("dde", 20260805),
        ("kdj", 20260805),
        ("board_actions", 20260805),
        ("hot_board", 20260805, 20260804),
        ("index_emotion", 20260805),
    ]
    assert result == {
        "status": "success",
        "trade_date": 20260805,
        "source_trade_date": 20260804,
        "counts": {
            "securities": 1,
            "daily_quotes": 2,
            "index_daily": 3,
            "market_cap": 4,
            "dde": 5,
            "kdj": 6,
            "board_actions": 7,
            "hot_board_emotion": 8,
            "index_emotion": 9,
        },
        "warnings": [],
    }
    completion_key = daily_update_completion_key(20260805)
    assert redis.expiries[completion_key] == 7 * 86400
    assert DAILY_UPDATE_LOCK_KEY not in redis.values


def test_daily_update_seeds_index_dates_before_resolving_trading_window():
    calls = []
    redis = FakeRedis()

    class SeedCollector(FakeCollector):
        def __init__(self):
            super().__init__(calls=calls)
            self.date_results = iter([[], [20260804, 20260805]])

        def trading_dates(self, limit):
            calls.append("trading_dates")
            return next(self.date_results)

    result = run_daily_update(
        20260805,
        collector=SeedCollector(),
        state=redis,
        run_hot_board=lambda *_args: 1,
        run_index=lambda *_args: 1,
    )

    assert result["status"] == "success"
    assert calls[:5] == [
        "trading_dates",
        ("index_daily", 20250805, 20260805),
        "trading_dates",
        ("index_daily", 20260804, 20260805),
        "securities",
    ]


def test_daily_update_skips_completed_date_without_acquiring_lock():
    redis = FakeRedis()
    redis.values[daily_update_completion_key(20260805)] = "complete"

    result = run_daily_update(20260805, collector=FakeCollector(), state=redis)

    assert result == {"status": "skipped", "trade_date": 20260805, "reason": "already completed"}
    assert DAILY_UPDATE_LOCK_KEY not in redis.values


def test_daily_update_rejects_concurrent_run():
    redis = FakeRedis()
    redis.values[DAILY_UPDATE_LOCK_KEY] = "another-owner"

    with pytest.raises(JobExecutionError, match="already running"):
        run_daily_update(20260805, collector=FakeCollector(), state=redis)

    assert redis.values[DAILY_UPDATE_LOCK_KEY] == "another-owner"


def test_daily_update_failure_releases_lock_without_completion():
    redis = FakeRedis()
    collector = FakeCollector()
    collector.update_securities = lambda: (_ for _ in ()).throw(RuntimeError("source down"))

    with pytest.raises(RuntimeError, match="source down"):
        run_daily_update(
            20260805,
            collector=collector,
            state=redis,
            run_hot_board=lambda *_args: 1,
            run_index=lambda *_args: 1,
        )

    assert DAILY_UPDATE_LOCK_KEY not in redis.values
    assert daily_update_completion_key(20260805) not in redis.values


@pytest.mark.parametrize("failed_stage", ["market_cap", "dde"])
def test_daily_update_rejects_failed_enrichment_without_completion(failed_stage):
    redis = FakeRedis()
    collector = FakeCollector()
    setattr(
        collector,
        f"update_{failed_stage}",
        lambda _date: {"status": "failed", "updated": 1},
    )

    with pytest.raises(JobExecutionError, match=failed_stage):
        run_daily_update(
            20260805,
            collector=collector,
            state=redis,
            run_hot_board=lambda *_args: 1,
            run_index=lambda *_args: 1,
        )

    assert DAILY_UPDATE_LOCK_KEY not in redis.values
    assert daily_update_completion_key(20260805) not in redis.values


def test_daily_update_rejects_kdj_failure_without_completion():
    redis = FakeRedis()
    collector = FakeCollector()
    collector.update_kdj = lambda _date: (_ for _ in ()).throw(
        RuntimeError("kdj failed")
    )

    with pytest.raises(JobExecutionError, match="KDJ update failed"):
        run_daily_update(
            20260805,
            collector=collector,
            state=redis,
            run_hot_board=lambda *_args: 1,
            run_index=lambda *_args: 1,
        )

    assert DAILY_UPDATE_LOCK_KEY not in redis.values
    assert daily_update_completion_key(20260805) not in redis.values


def test_daily_update_continues_after_jiuyan_export_warning():
    redis = FakeRedis()
    collector = FakeCollector()
    calls = []
    collector.collect_board_actions = lambda trade_date: {
        "status": "succeeded_with_warnings",
        "updated": 7,
        "trade_date": trade_date,
        "export_paths": [],
        "warnings": ["export failed"],
    }

    result = run_daily_update(
        20260805,
        collector=collector,
        state=redis,
        run_hot_board=lambda *_args: calls.append("hot") or 1,
        run_index=lambda *_args: calls.append("index") or 1,
    )

    assert calls == ["hot", "index"]
    assert result["counts"]["board_actions"] == 7
    assert result["warnings"] == ["export failed"]
    assert daily_update_completion_key(20260805) in redis.values


def test_daily_update_human_verification_releases_lock_without_completion():
    redis = FakeRedis()
    collector = FakeCollector()
    collector.collect_board_actions = lambda _date: (_ for _ in ()).throw(
        HumanVerificationRequired("slider")
    )

    with pytest.raises(HumanVerificationRequired):
        run_daily_update(
            20260805,
            collector=collector,
            state=redis,
            run_hot_board=lambda *_args: 1,
            run_index=lambda *_args: 1,
        )

    assert DAILY_UPDATE_LOCK_KEY not in redis.values
    assert daily_update_completion_key(20260805) not in redis.values


def test_daily_update_rejects_failed_jiuyan_status_without_completion():
    redis = FakeRedis()
    collector = FakeCollector()
    collector.collect_board_actions = lambda trade_date: {
        "status": "failed",
        "updated": 0,
        "trade_date": trade_date,
        "warnings": [],
    }

    with pytest.raises(JobExecutionError, match="Jiuyan collection failed"):
        run_daily_update(
            20260805,
            collector=collector,
            state=redis,
            run_hot_board=lambda *_args: 1,
            run_index=lambda *_args: 1,
        )

    assert DAILY_UPDATE_LOCK_KEY not in redis.values
    assert daily_update_completion_key(20260805) not in redis.values


@pytest.mark.parametrize("failed_stage", ["hot_board", "index_emotion"])
def test_daily_update_emotion_failure_suppresses_completion(failed_stage):
    redis = FakeRedis()

    def hot_board(*_args):
        if failed_stage == "hot_board":
            raise RuntimeError("hot-board failed")
        return 1

    def index_emotion(*_args):
        if failed_stage == "index_emotion":
            raise RuntimeError("index failed")
        return 1

    with pytest.raises(RuntimeError):
        run_daily_update(
            20260805,
            collector=FakeCollector(),
            state=redis,
            run_hot_board=hot_board,
            run_index=index_emotion,
        )

    assert DAILY_UPDATE_LOCK_KEY not in redis.values
    assert daily_update_completion_key(20260805) not in redis.values


def test_daily_update_rejects_date_without_previous_session():
    redis = FakeRedis()

    with pytest.raises(JobExecutionError, match="previous trading date"):
        run_daily_update(20260805, collector=FakeCollector(dates=[20260805]), state=redis)

    assert DAILY_UPDATE_LOCK_KEY not in redis.values


def test_backfill_reports_failures_and_continues():
    redis = FakeRedis()
    collector = FakeCollector(dates=[20260804, 20260805])
    calls = []

    def runner(date, **_kwargs):
        calls.append(date)
        if date == 20260804:
            raise RuntimeError("failed date")
        return {"status": "success", "trade_date": date}

    result = backfill_daily_updates(2, collector=collector, state=redis, runner=runner)

    assert calls == [20260804, 20260805]
    assert result["status"] == "failed"
    assert [item["status"] for item in result["results"]] == ["failed", "success"]
