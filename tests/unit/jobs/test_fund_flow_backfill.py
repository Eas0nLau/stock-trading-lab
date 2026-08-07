import datetime as dt

import pytest

from stock_lab.jobs.fund_flow_backfill import (
    EastMoneyFundFlowSource,
    backfill_fund_flow,
    migrate_legacy_redis,
    parse_daykline_response,
    run_backfill,
)


class Catalog:
    def board_catalog(self, flow_type):
        return [{"board_code": "BK0732", "board_name": "机器人", "leader": "甲"}]


class Response:
    status_code = 200

    def raise_for_status(self):
        pass

    def json(self):
        return {"data": {"klines": ["2026-08-07,325000000,0,0,0,0"]}}


class Session:
    def __init__(self, response=None):
        self.response = response or Response()
        self.calls = []

    def get(self, url, params, headers, timeout):
        self.calls.append((url, params, headers, timeout))
        return self.response


def test_direct_source_uses_mysql_catalog_and_browser_headers():
    session = Session()
    source = EastMoneyFundFlowSource(Catalog(), session=session)

    assert source.list_boards("industry") == [
        {"board_code": "BK0732", "board_name": "机器人", "leader": "甲"}
    ]
    assert source.board_history({"board_code": "BK0732", "board_name": "机器人", "leader": "甲"}) == [{
        "trade_date": 20260807,
        "board_code": "BK0732",
        "board_name": "机器人",
        "leader": "甲",
        "net_inflow_100m": 3.25,
        "flow_type": "industry",
    }]
    url, params, headers, timeout = session.calls[0]
    assert url.endswith("/api/qt/stock/fflow/daykline/get")
    assert params["secid"] == "90.BK0732"
    assert headers["User-Agent"].startswith("Mozilla/")
    assert headers["Referer"]
    assert timeout > 0


def test_direct_parser_rejects_malformed_response():
    with pytest.raises(ValueError, match="klines"):
        parse_daykline_response({"data": {}}, {"board_code": "BK0732"}, "industry")


def test_run_backfill_checks_mysql_before_writing_and_skips_duplicates():
    class Source:
        def list_boards(self, flow_type):
            return [{"board_code": flow_type, "board_name": flow_type, "leader": "甲"}]

        def board_history(self, board_name):
            return [{
                "trade_date": 20260807,
                "board_code": board_name,
                "board_name": board_name,
                "leader": "甲",
                "net_inflow_100m": 1,
                "flow_type": "industry",
            }]

    mysql = MySQL(existing={("concept", 20260807)})
    writes = []
    result = run_backfill(
        trading_dates=[20260807],
        source=Source(),
        mysql_repository=mysql,
        redis_repository=Redis(),
        writer=lambda flow_type, trade_date, snapshot_time, rows: writes.append(flow_type),
        now=dt.date(2026, 8, 7),
        retries=0,
        rate_delay=0,
    )

    assert result["status"] == "success"
    assert writes == ["industry"]


class Source:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def fetch(self, flow_type, trade_date):
        self.calls.append((flow_type, trade_date))
        if (flow_type, trade_date) in self.rows:
            return self.rows[(flow_type, trade_date)]
        raise RuntimeError("source unavailable")


class MySQL:
    def __init__(self, existing=()):
        self.existing = set(existing)
        self.saved = []

    def has_snapshot(self, flow_type, trade_date):
        return (flow_type, trade_date) in self.existing

    def save_snapshot(self, flow_type, trade_date, collected_at, records):
        self.saved.append((flow_type, trade_date, collected_at, records))
        return len(self.saved)


class Redis:
    def __init__(self):
        self.saved = []

    def save_history(self, flow_type, trade_date, records):
        self.saved.append((flow_type, trade_date, records))


def test_legacy_redis_migration_is_guarded_after_success():
    class RedisMigration:
        def __init__(self):
            self.marker = "1"
            self.redis = self

        def get(self, key):
            return self.marker

    result = migrate_legacy_redis(RedisMigration(), object())

    assert result == {"saved": [], "failed": [], "skipped": True}


def test_legacy_migration_does_not_divide_new_canonical_history():
    class RedisMigration:
        def __init__(self):
            self.marker = None
            self.redis = self
            self.history_value = [[{"time": "10:00:00", "net_inflow_100m": 4.111302}]]

        def get(self, key):
            return self.marker

        def set(self, key, value):
            self.marker = value

    class RedisRepository:
        def __init__(self):
            self.redis = RedisMigration()

        def dates(self, flow_type):
            return ["20260807"]

        def history(self, flow_type, trade_date):
            return self.redis.history_value

        def replace_history(self, flow_type, trade_date, snapshots):
            self.redis.history_value = snapshots

        def is_canonical_history(self, flow_type, trade_date):
            return True

    mysql = MySQL()
    result = migrate_legacy_redis(RedisRepository(), mysql)

    assert result["failed"] == []
    assert mysql.saved == []


def test_backfill_iterates_newest_to_oldest_and_reports_failed_dates():
    source = Source({("industry", 20260807): [{"board_code": "A", "net_inflow_100m": "1", "source_unit": "wan"}]})
    mysql = MySQL(existing={("concept", 20260806)})
    result = backfill_fund_flow(20260805, 20260807, source, mysql, Redis(), lambda start, end: [20260805, 20260806, 20260807])

    assert source.calls == [("industry", 20260807), ("concept", 20260807), ("industry", 20260806), ("industry", 20260805), ("concept", 20260805)]
    assert [row[1] for row in mysql.saved] == [20260807]
    assert mysql.saved[0][3][0]["net_inflow_100m"] == 0.0001
    assert result["failed"] == [{"flow_type": "concept", "trade_date": 20260807, "error": "source unavailable"}, {"flow_type": "industry", "trade_date": 20260806, "error": "source unavailable"}, {"flow_type": "industry", "trade_date": 20260805, "error": "source unavailable"}, {"flow_type": "concept", "trade_date": 20260805, "error": "source unavailable"}]


def test_backfill_does_not_treat_empty_source_result_as_success():
    source = Source({("industry", 20260807): []})
    mysql = MySQL()
    result = backfill_fund_flow(20260807, 20260807, source, mysql, Redis(), lambda start, end: [20260807])

    assert mysql.saved == []
    assert result["failed"][0]["error"] == "source returned no records"
