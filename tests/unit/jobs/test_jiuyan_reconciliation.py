import pytest

from stock_lab.jobs.jiuyan_reconciliation import (
    DuplicateJiuyanSourceKeys,
    recalculate_complete_hot_board_emotion,
    reconcile_jiuyan_data,
    verify_jiuyan_parity,
)


class FakeConnection:
    def __init__(self):
        self.statements = []

    def execute(self, statement, rows=None):
        self.statements.append((str(statement), rows))


class FakeBegin:
    def __init__(self, connection):
        self.connection = connection

    def __enter__(self):
        return self.connection

    def __exit__(self, *_args):
        return False


class FakeEngine:
    def __init__(self):
        self.connection = FakeConnection()

    def begin(self):
        return FakeBegin(self.connection)


class FakeDatabase:
    def __init__(self, responses):
        self.responses = responses
        self.engine = FakeEngine()
        self.queries = []

    def query(self, sql, params=None, fetch=False):
        self.queries.append((sql, params, fetch))
        for key, response in self.responses:
            if key in sql:
                return response
        raise AssertionError(f"Unexpected SQL: {sql}")


def test_reconciliation_reports_legacy_rows_missing_from_canonical_table():
    database = FakeDatabase([
        ("source_count", [{"source_count": 2, "target_count": 1}]),
        ("GROUP BY", []),
        ("NOT EXISTS", [{
            "data_id": "20260804_机器人_1",
            "date": 20260804,
            "板块": "机器人",
            "板块个股数量": 8,
            "股票代码": 1,
            "股票名称": "平安银行",
            "code": "000001",
            "涨停时间": None,
            "几天几板": "首板",
            "涨幅": 10.0,
            "涨停解析": "测试",
        }]),
    ])

    report = reconcile_jiuyan_data(database=database)

    assert report.source_count == 2
    assert report.target_count == 1
    assert report.missing_count == 1
    assert report.missing_ids == ("20260804_机器人_1",)
    assert database.engine.connection.statements == []


def test_reconciliation_compares_cross_table_ids_with_explicit_collation():
    database = FakeDatabase([
        ("source_count", [{"source_count": 0, "target_count": 0}]),
        ("GROUP BY", []),
        ("NOT EXISTS", []),
    ])

    reconcile_jiuyan_data(database=database)

    missing_sql = next(sql for sql, _params, _fetch in database.queries if "NOT EXISTS" in sql)
    assert missing_sql.count("COLLATE utf8mb4_bin") == 2


def test_reconciliation_rejects_duplicate_legacy_business_keys():
    database = FakeDatabase([
        ("source_count", [{"source_count": 2, "target_count": 1}]),
        ("GROUP BY", [{"data_id": "duplicate", "row_count": 2}]),
    ])

    with pytest.raises(DuplicateJiuyanSourceKeys, match="duplicate"):
        reconcile_jiuyan_data(database=database, write=True)

    assert database.engine.connection.statements == []


def test_reconciliation_writes_only_missing_rows_and_is_idempotent():
    database = FakeDatabase([
        ("source_count", [{"source_count": 1, "target_count": 0}]),
        ("GROUP BY", []),
        ("NOT EXISTS", [{
            "data_id": "20260804_机器人_1",
            "date": 20260804,
            "板块": "机器人",
            "板块个股数量": 8,
            "股票代码": 1,
            "股票名称": "平安银行",
            "code": "000001",
            "涨停时间": None,
            "几天几板": "首板",
            "涨幅": 10.0,
            "涨停解析": "测试",
        }]),
    ])

    report = reconcile_jiuyan_data(database=database, write=True)

    assert report.written_count == 1
    statement, rows = database.engine.connection.statements[0]
    assert "jiuyan_actions" in statement
    assert rows[0]["stock_code"] == "000001"
    assert rows[0]["trade_date"] == 20260804


def test_recalculates_only_dates_with_current_and_previous_jiuyan_data():
    database = FakeDatabase([
        ("FROM `index_daily`", [{"trade_date": 20260803}, {"trade_date": 20260804}, {"trade_date": 20260805}]),
        ("FROM `jiuyan_actions`", [{"trade_date": 20260803}, {"trade_date": 20260804}]),
    ])
    calls = []

    report = recalculate_complete_hot_board_emotion(
        database=database,
        emotion_runner=lambda current, previous: calls.append((current, previous)) or 1,
    )

    assert calls == [(20260804, 20260803)]
    assert report.recalculated_dates == [20260804]
    assert report.skipped_dates == [{"trade_date": 20260805, "reason": "missing Jiuyan action rows"}]


def test_reconciliation_is_idempotent_after_first_write():
    source_row = {
        "data_id": "20260804_机器人_1",
        "date": 20260804,
        "板块": "机器人",
        "板块个股数量": 8,
        "股票代码": 1,
        "股票名称": "平安银行",
        "code": "000001",
        "涨停时间": None,
        "几天几板": "首板",
        "涨幅": 10.0,
        "涨停解析": "测试",
    }

    class Connection:
        def __init__(self, target_ids):
            self.target_ids = target_ids

        def execute(self, _statement, rows):
            self.target_ids.update(row["data_id"] for row in rows)

    class Engine:
        def __init__(self, target_ids):
            self.connection = Connection(target_ids)
            self.begin_count = 0

        def begin(self):
            self.begin_count += 1
            return FakeBegin(self.connection)

    class Database:
        def __init__(self):
            self.target_ids = set()
            self.engine = Engine(self.target_ids)

        def query(self, sql, params=None, fetch=False):
            if "source_count" in sql:
                return [{"source_count": 1, "target_count": len(self.target_ids)}]
            if "GROUP BY" in sql:
                return []
            if "NOT EXISTS" in sql:
                return [] if source_row["data_id"] in self.target_ids else [source_row]
            raise AssertionError(f"Unexpected SQL: {sql}")

    database = Database()

    first = reconcile_jiuyan_data(database=database, write=True)
    second = reconcile_jiuyan_data(database=database, write=True)

    assert first.written_count == 1
    assert second.missing_count == 0
    assert second.written_count == 0
    assert database.engine.begin_count == 1


def test_parity_verification_returns_remaining_missing_ids():
    database = FakeDatabase([
        ("NOT EXISTS", [{"data_id": "missing-id"}]),
        ("duplicate_target_ids", [{"duplicate_target_ids": 0, "invalid_emotion_json": 0}]),
    ])

    assert verify_jiuyan_parity(database) == ["missing-id"]


@pytest.mark.parametrize(
    ("validation", "message"),
    [
        ({"duplicate_target_ids": 1, "invalid_emotion_json": 0}, "duplicate data_id"),
        ({"duplicate_target_ids": 0, "invalid_emotion_json": 1}, "invalid decision_reasons_json"),
    ],
)
def test_parity_verification_rejects_invalid_canonical_state(validation, message):
    database = FakeDatabase([
        ("NOT EXISTS", []),
        ("duplicate_target_ids", [validation]),
    ])

    with pytest.raises(RuntimeError, match=message):
        verify_jiuyan_parity(database)
