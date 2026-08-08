import datetime as dt
import datetime as dt
import json
from types import SimpleNamespace

import pandas as pd
import pytest

from task import fund_flow_backfill


class FakeAkShare:
    def __init__(self):
        self.rank_calls = []
        self.history_calls = []

    def stock_sector_fund_flow_rank(self, indicator, sector_type):
        self.rank_calls.append((indicator, sector_type))
        return pd.DataFrame([
            {
                "板块代码": "BK0420",
                "名称": "机器人",
                "今日主力净流入最大股": "示例股份",
            }
        ])

    def stock_sector_fund_flow_hist(self, symbol):
        self.history_calls.append(symbol)
        return pd.DataFrame([
            {"日期": "2026-08-07", "主力净流入-净额": 325_000_000},
        ])


class FakeSource:
    def __init__(self, fail_history_times=0):
        self.fail_history_times = fail_history_times
        self.history_attempts = 0

    def list_boards(self, flow_type):
        return [{"board_code": f"{flow_type}-1", "board_name": f"{flow_type}-board", "leader": "leader"}]

    def board_history(self, board_name):
        self.history_attempts += 1
        if self.history_attempts <= self.fail_history_times:
            raise ConnectionError("source unavailable")
        return pd.DataFrame([
            {"trade_date": 20250807, "f62": 100_000_000},
            {"trade_date": 20260806, "f62": 200_000_000},
            {"trade_date": 20260807, "f62": 300_000_000},
        ])


class FakeCursor:
    def __init__(self, events):
        self.events = events
        self.lastrowid = 17

    def execute(self, sql, params):
        self.events.append(("mysql_execute", sql, params))

    def fetchone(self):
        return None

    def executemany(self, sql, values):
        self.events.append(("mysql_executemany", sql, values))

    def close(self):
        self.events.append(("mysql_cursor_close",))


class FakeConnection:
    def __init__(self, events, fail_commit=False):
        self.events = events
        self.fail_commit = fail_commit

    def cursor(self, dictionary=False):
        assert dictionary is True
        return FakeCursor(self.events)

    def commit(self):
        self.events.append(("mysql_commit",))
        if self.fail_commit:
            raise RuntimeError("mysql commit failed")

    def rollback(self):
        self.events.append(("mysql_rollback",))

    def close(self):
        self.events.append(("mysql_close",))


class FakeRedis:
    def __init__(self, events):
        self.events = events
        self.values = {}
        self.sets = {}

    def get(self, key):
        self.events.append(("redis_get", key))
        return self.values.get(key)

    def set(self, key, value):
        self.events.append(("redis_set", key, value))
        self.values[key] = value

    def sadd(self, key, value):
        self.events.append(("redis_sadd", key, value))
        self.sets.setdefault(key, set()).add(value)

    def smembers(self, key):
        self.events.append(("redis_smembers", key))
        return self.sets.get(key, set())

    def delete(self, *keys):
        self.events.append(("redis_delete", *keys))


def test_adapter_uses_injected_akshare_and_maps_board_metadata():
    fake_akshare = FakeAkShare()
    source = fund_flow_backfill.AkShareFundFlowSource(fake_akshare)

    boards = source.list_boards("industry")
    history = source.board_history("机器人")

    assert boards == [{"board_code": "BK0420", "board_name": "机器人", "leader": "示例股份"}]
    assert history.to_dict("records") == [{"日期": "2026-08-07", "主力净流入-净额": 325_000_000}]
    assert fake_akshare.rank_calls == [("今日", "行业资金流")]
    assert fake_akshare.history_calls == ["机器人"]


def test_normalize_history_rows_converts_f62_like_yuan_to_100m():
    frame = pd.DataFrame([
        {"日期": "2026-08-07", "主力净流入-净额": 325_000_000},
        {"日期": dt.date(2026, 8, 6), "f62": -50_000_000},
    ])
    board = {"board_code": "BK0420", "board_name": "机器人", "leader": "示例股份"}

    rows = fund_flow_backfill.normalize_history_rows(frame, board, "concept")

    assert rows == [
        {
            "trade_date": 20260807,
            "board_code": "BK0420",
            "board_name": "机器人",
            "leader": "示例股份",
            "net_inflow_100m": 3.25,
            "flow_type": "concept",
        },
        {
            "trade_date": 20260806,
            "board_code": "BK0420",
            "board_name": "机器人",
            "leader": "示例股份",
            "net_inflow_100m": -0.5,
            "flow_type": "concept",
        },
    ]


def test_default_writer_composes_repositories_and_commits_mysql_before_redis():
    events = []
    connection = FakeConnection(events)
    redis = FakeRedis(events)
    settings = SimpleNamespace()
    received_settings = []
    writer = fund_flow_backfill._default_writer(
        settings=settings,
        connection_factory=lambda: connection,
        redis_factory=lambda received: (received_settings.append(received), redis)[1],
    )

    trade_date = dt.date.today().strftime("%Y%m%d")
    writer("industry", trade_date, "15:00:00", [{
        "board_code": "BK0420",
        "board_name": "robotics",
        "leader": "example",
        "net_inflow_100m": "3.25",
        "flow_type": "industry",
        "trade_date": 20260807,
    }])

    assert received_settings == [settings]
    assert next(index for index, event in enumerate(events) if event[0] == "mysql_commit") < next(
        index for index, event in enumerate(events) if event[0] == "redis_set"
    )
    redis_payload = json.loads(redis.values[f"fund_flow:v1:industry:history:{trade_date}"])
    assert redis_payload == [[{
        "board_code": "BK0420",
        "board_name": "robotics",
        "leader": "example",
        "net_inflow_100m": 3.25,
        "time": "15:00:00",
    }]]


def test_default_writer_does_not_touch_redis_when_mysql_commit_fails():
    events = []
    writer = fund_flow_backfill._default_writer(
        settings=SimpleNamespace(),
        connection_factory=lambda: FakeConnection(events, fail_commit=True),
        redis_factory=lambda _settings: FakeRedis(events),
    )

    with pytest.raises(RuntimeError, match="mysql commit failed"):
        writer("concept", "20260807", "15:00:00", [{
            "board_code": "BK0420",
            "board_name": "robotics",
            "leader": "example",
            "net_inflow_100m": 3.25,
        }])

    assert ("mysql_rollback",) in events
    assert not any(event[0].startswith("redis_") for event in events)


def test_backfill_uses_calendar_year_bounds_and_writes_newest_first():
    writes = []
    sleeps = []

    result = fund_flow_backfill.backfill_fund_flow(
        trading_dates=[20250806, 20250807, 20260806, 20260807, 20260808],
        source=FakeSource(),
        now=dt.date(2026, 8, 7),
        retries=0,
        rate_delay=0.25,
        sleep=sleeps.append,
        writer=lambda prefix, date, snapshot_time, records: writes.append(
            (prefix, date, snapshot_time, records)
        ),
    )

    assert result["status"] == "success"
    assert result["processed_dates"] == [20260807, 20260806, 20250807]
    assert result["failed_dates"] == []
    assert [(flow_type, date) for flow_type, date, _, _ in writes] == [
        ("industry", "20260807"),
        ("concept", "20260807"),
        ("industry", "20260806"),
        ("concept", "20260806"),
        ("industry", "20250807"),
        ("concept", "20250807"),
    ]
    assert all(snapshot_time == "15:00:00" for _, _, snapshot_time, _ in writes)
    assert writes[0][3][0] == {
        "trade_date": 20260807,
        "board_code": "industry-1",
        "board_name": "industry-board",
        "leader": "leader",
        "net_inflow_100m": 3.0,
        "flow_type": "industry",
    }
    assert sleeps == [0.25, 0.25, 0.25]


def test_backfill_injects_retry_delay_before_success():
    sleeps = []
    source = FakeSource(fail_history_times=1)

    result = fund_flow_backfill.backfill_fund_flow(
        trading_dates=[20260807],
        source=source,
        now=dt.date(2026, 8, 7),
        retries=1,
        retry_delay=1.5,
        rate_delay=0,
        sleep=sleeps.append,
        writer=lambda *args: None,
    )

    assert result["status"] == "success"
    assert source.history_attempts == 3
    assert sleeps == [1.5]


def test_exhausted_network_failure_reports_dates_without_writing():
    writes = []

    result = fund_flow_backfill.backfill_fund_flow(
        trading_dates=[20260806, 20260807],
        source=FakeSource(fail_history_times=10),
        now=dt.date(2026, 8, 7),
        retries=1,
        retry_delay=0,
        rate_delay=0,
        sleep=lambda seconds: None,
        writer=lambda *args: writes.append(args),
    )

    assert result["status"] == "failed"
    assert result["processed_dates"] == []
    assert result["failed_dates"] == [20260807, 20260806]
    assert "source unavailable" in result["errors"][0]["error"]
    assert writes == []


def test_write_network_failure_is_reported_and_older_dates_continue():
    writes = []

    def writer(prefix, date, snapshot_time, records):
        if date == "20260807":
            raise ConnectionError("redis unavailable")
        writes.append((prefix, date))

    result = fund_flow_backfill.backfill_fund_flow(
        trading_dates=[20260806, 20260807],
        source=FakeSource(),
        now=dt.date(2026, 8, 7),
        retries=0,
        rate_delay=0,
        writer=writer,
    )

    assert result["status"] == "failed"
    assert result["processed_dates"] == [20260806]
    assert result["failed_dates"] == [20260807]
    assert result["errors"] == [
        {"trade_date": 20260807, "error": "redis unavailable"}
    ]
    assert writes == [
        ("industry", "20260806"),
        ("concept", "20260806"),
    ]
