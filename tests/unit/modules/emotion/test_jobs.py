import pytest

from stock_lab.modules.emotion.jobs import (
    run_hot_board_emotion_job,
    run_index_emotion_job,
    write_tables,
)
from stock_lab.shared.errors import DataValidationError


class FakeRepository:
    def index_daily_rows_through(self, end_date, limit):
        return [{
            "trade_date": 20260806,
            "open_price": 3500,
            "close_price": 3560,
            "high_price": 3580,
            "low_price": 3490,
            "turnover": 500,
            "change_pct": 1.2,
        }]

    def market_breadth_rows_through(self, end_date, limit):
        return [{
            "trade_date": 20260806,
            "total_count": 5000,
            "up_count": 3000,
            "down_count": 2000,
            "up_gt5_count": 300,
            "down_lt5_count": 100,
            "limit_up_count": 80,
            "limit_down_count": 5,
            "amount": 12000,
            "avg_pct_chg": 0.8,
        }]

    def board_action_rows(self, trade_date):
        return [{
            "board_name": "机器人",
            "board_stock_count": 20,
            "stock_code": "000001",
            "stock_name": "平安银行",
        }]

    def daily_quote_rows(self, trade_date, stock_codes):
        return {"000001": {"stock_code": "000001", "previous_close": 10, "high_price": 11, "low_price": 9.8, "change_pct": 10}}

    def previous_trading_date(self, trade_date):
        return 20260805

    def jiuyan_date_complete(self, trade_date):
        return True


def test_index_job_writes_english_tables_and_json():
    writes = []

    def calculator(index_rows, market_rows):
        assert index_rows[0]["trade_date"] == 20260806
        return {
            "trade_date": 20260806,
            "cycle_state": "发酵",
            "cycle_score": 70,
            "index_quote": {"close_price": 3560},
            "market_breadth": {"advancing_count": 3000},
            "score_components": {},
            "moving_averages": {},
            "moving_average_slopes": {},
            "signals": [],
            "recent_trend": [],
            "volatility_chart": [],
        }

    run_index_emotion_job(20260806, FakeRepository(), calculator, lambda tables: writes.extend(tables))

    assert [table for table, _keys, _rows in writes] == ["index_market_breadth", "index_emotion_daily"]
    index_row = writes[1][2][0]
    assert index_row["trade_date"] == 20260806
    assert '"cycle_state": "发酵"' in index_row["full_result_json"]


def test_hot_board_job_writes_english_rows():
    writes = []

    def analyzer(**values):
        return {
            "trade_date": values["trade_date"],
            "board_name": values["board_name"],
            "sample_trade_date": values["sample_trade_date"],
            "current_board_count": 20,
            "overall_status": "强势延续",
            "emotion_score": 80,
            "decision_reasons": {"reason": "test"},
        }

    run_hot_board_emotion_job(20260806, 20260805, FakeRepository(), analyzer, lambda tables: writes.extend(tables))

    assert writes[0][0] == "hot_board_emotion_daily"
    row = writes[0][2][0]
    assert row["board_name"] == "机器人"
    assert row["overall_status"] == "强势延续"
    assert row["decision_reasons_json"] == '{"reason": "test"}'


def test_index_job_rejects_previous_day_market_breadth():
    repository = FakeRepository()
    repository.market_breadth_rows_through = lambda end_date, limit: [{"trade_date": 20260805}]

    with pytest.raises(DataValidationError, match="20260806"):
        run_index_emotion_job(20260806, repository, lambda *_args: {}, lambda _tables: None)


def test_index_job_requests_history_through_target_date():
    repository = FakeRepository()
    calls = []
    repository.index_daily_rows_through = lambda end_date, limit: calls.append(
        ("index", end_date, limit)
    ) or FakeRepository().index_daily_rows_through(end_date, limit)
    repository.market_breadth_rows_through = lambda end_date, limit: calls.append(
        ("breadth", end_date, limit)
    ) or FakeRepository().market_breadth_rows_through(end_date, limit)

    run_index_emotion_job(
        20260806,
        repository,
        lambda *_args: {
            "trade_date": 20260806,
            "score_components": {},
            "moving_averages": {},
            "moving_average_slopes": {},
        },
        lambda _tables: None,
    )

    assert calls == [("index", 20260806, 180), ("breadth", 20260806, 80)]


def test_hot_board_job_rejects_non_adjacent_sample_date():
    with pytest.raises(DataValidationError, match="Previous trading date mismatch"):
        run_hot_board_emotion_job(
            20260806,
            20260804,
            FakeRepository(),
            lambda **kwargs: {},
            lambda tables: None,
        )


@pytest.mark.parametrize("incomplete_date", [20260805, 20260806])
def test_hot_board_job_requires_complete_manifests(incomplete_date):
    repository = FakeRepository()
    repository.jiuyan_date_complete = lambda trade_date: trade_date != incomplete_date

    with pytest.raises(DataValidationError, match="Unverified Jiuyan actions"):
        run_hot_board_emotion_job(
            20260806,
            20260805,
            repository,
            lambda **kwargs: {},
            lambda tables: None,
        )


def test_hot_board_job_keeps_union_and_filters_invalid_actions():
    repository = FakeRepository()
    repository.board_action_rows = lambda trade_date: (
        [
            {"board_name": "Previous", "board_stock_count": 2, "stock_code": "000001", "stock_name": "One"},
            {"board_name": "Invalid", "board_stock_count": 2, "stock_code": "300001", "stock_name": "Growth"},
        ]
        if trade_date == 20260805
        else [
            {"board_name": "Current", "board_stock_count": 2, "stock_code": "600000", "stock_name": "Two"},
            {"board_name": "Invalid", "board_stock_count": 2, "stock_code": "000002", "stock_name": "ST Sample"},
        ]
    )
    repository.daily_quote_rows = lambda trade_date, codes: {}
    analyzed = []

    def analyzer(**values):
        analyzed.append(values)
        return {
            "trade_date": values["trade_date"],
            "board_name": values["board_name"],
            "decision_reasons": {},
        }

    assert run_hot_board_emotion_job(
        20260806,
        20260805,
        repository,
        analyzer,
        lambda tables: None,
    ) == 2
    assert [values["board_name"] for values in analyzed] == ["Current", "Previous"]
    assert all(values["previous_list_complete"] is True for values in analyzed)
    assert all(values["current_list_complete"] is True for values in analyzed)


def test_hot_board_analyzer_failure_performs_no_write():
    writes = []

    with pytest.raises(RuntimeError, match="analysis failed"):
        run_hot_board_emotion_job(
            20260806,
            20260805,
            FakeRepository(),
            lambda **kwargs: (_ for _ in ()).throw(RuntimeError("analysis failed")),
            writes.append,
        )

    assert writes == []


def test_write_tables_replaces_hot_board_target_date_in_one_transaction():
    calls = []

    class Result:
        rowcount = 1

    class Connection:
        def execute(self, statement, parameters=None):
            calls.append((str(statement), parameters))
            return Result()

    class Transaction:
        def __enter__(self):
            return Connection()

        def __exit__(self, exc_type, exc, traceback):
            return False

    class Engine:
        def begin(self):
            return Transaction()

    rows = [{"trade_date": 20260806, "board_name": "Robotics"}]
    write_tables(Engine(), [("hot_board_emotion_daily", ("trade_date", "board_name"), rows)])

    assert "DELETE FROM `hot_board_emotion_daily`" in calls[0][0]
    assert calls[0][1] == {"trade_date": 20260806}
    assert "INSERT INTO `hot_board_emotion_daily`" in calls[1][0]
