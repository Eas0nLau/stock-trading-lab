from stock_lab.modules.dragon_tiger.models import Broker, BrokerTopStats
from stock_lab.modules.dragon_tiger.repository import DragonTigerRepository


class FakeQuery:
    def __init__(self, rows=()):
        self.rows = list(rows)
        self.calls = []

    def __call__(self, sql, params=None, fetch=False):
        self.calls.append((sql, params, fetch))
        return self.rows


class FakeConnection:
    def __init__(self):
        self.calls = []

    def execute(self, statement, rows):
        self.calls.append((str(statement), rows))


class BeginContext:
    def __init__(self, connection):
        self.connection = connection

    def __enter__(self):
        return self.connection

    def __exit__(self, *_):
        return False


class FakeEngine:
    def __init__(self):
        self.connection = FakeConnection()

    def begin(self):
        return BeginContext(self.connection)


def test_trading_dates_are_read_from_daily_quotes():
    query = FakeQuery([{"trade_date": 20260805}, {"trade_date": 20260806}])

    result = DragonTigerRepository(query).trading_dates(20260806)

    assert result == [20260806]
    assert "FROM `daily_quotes`" in query.calls[0][0]
    assert query.calls[0][1] == (20260806,)


def test_listings_use_bound_filters_and_canonical_columns():
    query = FakeQuery([{"stock_code": "000001", "trade_date": 20260806}])

    result = DragonTigerRepository(query).listings(
        start_date=20260801,
        end_date=20260806,
        stock_codes=["000001", "600000"],
    )

    sql, params, fetch = query.calls[0]
    assert result[0]["stock_code"] == "000001.SZ"
    assert "FROM `dragon_tiger`" in sql
    assert "`trade_date` >= %s" in sql
    assert "LPAD(SUBSTRING_INDEX(`stock_code`, '.', 1), 6, '0') IN (%s, %s)" in sql
    assert params == (20260801, 20260806, "000001", "600000")
    assert fetch is True


def test_broker_history_uses_canonical_table_and_broker_filter():
    query = FakeQuery([{"stock_code": "600000"}])

    result = DragonTigerRepository(query).broker_history(20260701, 20260806, ["B2", "B1"])

    sql, params, _ = query.calls[0]
    assert "FROM `broker_listing_history`" in sql
    assert "`broker_id` IN (%s,%s)" in sql
    assert params == (20260701, 20260806, "B1", "B2")
    assert result[0]["stock_code"] == "600000.SH"


def test_upsert_brokers_uses_schema_fields_and_primary_key():
    engine = FakeEngine()
    repository = DragonTigerRepository(FakeQuery(), engine)

    assert repository.upsert_brokers([Broker("B1", "Broker One")]) == 1

    sql, rows = engine.connection.calls[0]
    assert "INSERT INTO `brokers`" in sql
    assert "`broker_id`" in sql
    assert "`broker_name` = VALUES(`broker_name`)" in sql
    assert rows == [{"broker_id": "B1", "broker_name": "Broker One"}]


def test_empty_upsert_does_not_open_transaction():
    engine = FakeEngine()

    assert DragonTigerRepository(FakeQuery(), engine).upsert_brokers([]) == 0
    assert engine.connection.calls == []


def test_upsert_listings_persists_canonical_stock_code():
    engine = FakeEngine()

    DragonTigerRepository(FakeQuery(), engine).upsert_listings([{
        "data_id": "row-1", "stock_code": "600000",
    }])

    _, rows = engine.connection.calls[0]
    assert rows[0]["stock_code"] == "600000.SH"


def test_upsert_broker_history_persists_canonical_stock_code():
    engine = FakeEngine()

    DragonTigerRepository(FakeQuery(), engine).upsert_broker_history([{
        "data_id": "row-1", "stock_code": "430001",
    }])

    _, rows = engine.connection.calls[0]
    assert rows[0]["stock_code"] == "430001.BJ"


def test_broker_top_stats_reads_all_canonical_columns():
    row = {
        "broker_id": "B1",
        "broker_name": "Broker One",
        "listing_count": 12,
        "total_capital_used": 3456.0,
        "year_listing_count": 7,
        "year_stock_count": 5,
        "three_day_follow_success_rate": 66.7,
    }
    query = FakeQuery([row])

    result = DragonTigerRepository(query).broker_top_stats()

    assert result == [row]
    sql, params, fetch = query.calls[0]
    assert "FROM `broker_top_stats`" in sql
    assert all(f"`{column}`" in sql for column in row)
    assert params is None
    assert fetch is True


def test_upsert_broker_top_stats_updates_non_key_columns():
    engine = FakeEngine()
    repository = DragonTigerRepository(FakeQuery(), engine)
    stats = BrokerTopStats(
        broker_id="B1",
        broker_name="Broker One",
        listing_count=12,
        total_capital_used=3456.0,
        year_listing_count=7,
        year_stock_count=5,
        three_day_follow_success_rate=66.7,
    )

    assert repository.upsert_broker_top_stats([stats]) == 1

    sql, rows = engine.connection.calls[0]
    assert "INSERT INTO `broker_top_stats`" in sql
    assert "`broker_id` = VALUES(`broker_id`)" not in sql
    assert "`listing_count` = VALUES(`listing_count`)" in sql
    assert rows == [{
        "broker_id": "B1",
        "broker_name": "Broker One",
        "listing_count": 12,
        "total_capital_used": 3456.0,
        "year_listing_count": 7,
        "year_stock_count": 5,
        "three_day_follow_success_rate": 66.7,
    }]
