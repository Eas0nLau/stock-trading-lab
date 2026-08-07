from stock_lab.jobs.fund_flow_backfill import backfill_fund_flow, migrate_legacy_redis


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
