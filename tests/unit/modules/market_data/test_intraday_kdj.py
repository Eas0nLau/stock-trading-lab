import pytest

from stock_lab.modules.market_data.indicators import calculate_kdj
from stock_lab.modules.market_data.parsing import normalize_intraday_bar
from stock_lab.modules.market_data.repository import MarketDataRepository
from stock_lab.shared.errors import DataValidationError


def test_intraday_bar_normalizes_source_types_and_identity():
    row = normalize_intraday_bar({
        "date": "2026-08-06", "time": "20260806093500000", "code": "sz.000001",
        "open": "10.1", "high": "10.8", "low": "9.9", "close": "10.5",
        "volume": "100", "amount": "1030.5", "adjustflag": "3",
    })

    assert row == {
        "data_id": "000001_202608060935_3", "trade_date": 20260806,
        "trade_time": 202608060935, "stock_code": "000001",
        "open_price": 10.1, "high_price": 10.8, "low_price": 9.9,
        "close_price": 10.5, "volume": 100.0, "turnover": 1030.5,
        "adjustment_flag": 3,
    }


def test_intraday_bar_uses_same_identity_for_minute_and_baostock_timestamp():
    base = {
        "date": "2026-08-06", "code": "sz.000001",
        "open": "10", "high": "11", "low": "9", "close": "10.5",
        "volume": "100", "amount": "1050", "adjustflag": "3",
    }

    minute = normalize_intraday_bar({**base, "time": "202608060935"})
    full = normalize_intraday_bar({**base, "time": "20260806093500000"})

    assert minute["trade_time"] == full["trade_time"] == 202608060935
    assert minute["data_id"] == full["data_id"] == "000001_202608060935_3"


@pytest.mark.parametrize("changes", [
    {"time": "bad"},
    {"code": ""},
    {"close": "not-a-number"},
])
def test_intraday_bar_rejects_malformed_required_values(changes):
    source = {
        "date": "2026-08-06", "time": "20260806093500000", "code": "sz.000001",
        "open": "10", "high": "11", "low": "9", "close": "10",
        "volume": "100", "amount": "1000", "adjustflag": "3",
    }
    source.update(changes)

    with pytest.raises(DataValidationError):
        normalize_intraday_bar(source)


def test_calculate_kdj_uses_per_symbol_rolling_rsv_and_standard_smoothing():
    rows = [
        {"ts_code": "000001.SZ", "trade_date": 20260804, "low_price": 0, "high_price": 10, "close_price": 5},
        {"ts_code": "000001.SZ", "trade_date": 20260805, "low_price": 0, "high_price": 10, "close_price": 8},
        {"ts_code": "000001.SZ", "trade_date": 20260806, "low_price": 0, "high_price": 10, "close_price": 2},
    ]

    result = calculate_kdj(rows, period=3)

    assert result[0] == {
        "data_id": "000001.SZ_20260804", "ts_code": "000001.SZ", "trade_date": 20260804,
        "k_value": 50.0, "d_value": 50.0, "j_value": 50.0,
    }
    assert result[-1]["k_value"] == pytest.approx(46.6666667)
    assert result[-1]["d_value"] == pytest.approx(51.1111111)
    assert result[-1]["j_value"] == pytest.approx(37.7777778)


def test_calculate_kdj_rejects_incomplete_price_rows():
    with pytest.raises(DataValidationError):
        calculate_kdj([{"ts_code": "000001.SZ", "trade_date": 20260806}])


class Connection:
    def __init__(self):
        self.calls = []

    def execute(self, statement, rows=None):
        self.calls.append((str(statement), rows))


class Transaction:
    def __init__(self, connection):
        self.connection = connection

    def __enter__(self):
        return self.connection

    def __exit__(self, *_):
        return None


class Engine:
    def __init__(self):
        self.connection = Connection()

    def begin(self):
        return Transaction(self.connection)


def test_repository_upserts_each_dataset_by_canonical_data_id():
    engine = Engine()
    repository = MarketDataRepository(lambda *_args, **_kwargs: [], engine)

    repository.upsert_intraday_bars_5m([{"data_id": "bar-1", "trade_date": 20260806}])
    repository.upsert_kdj_indicators([{"data_id": "kdj-1", "trade_date": 20260806}])

    first_sql, first_rows = engine.connection.calls[0]
    second_sql, second_rows = engine.connection.calls[1]
    assert "INSERT INTO `intraday_bars_5m`" in first_sql
    assert "`data_id` = VALUES(`data_id`)" not in first_sql
    assert first_rows == [{"data_id": "bar-1", "trade_date": 20260806}]
    assert "INSERT INTO `kdj_indicators`" in second_sql
    assert "`data_id` = VALUES(`data_id`)" not in second_sql
    assert second_rows == [{"data_id": "kdj-1", "trade_date": 20260806}]


def test_repository_returns_legacy_intraday_shape_from_english_table():
    calls = []

    def query(sql, params=None, fetch=False):
        calls.append((sql, params, fetch))
        return [{"date": 20260806, "time": 20260806093500000, "code": "000001", "close": 10.5}]

    rows = MarketDataRepository(query).intraday_bars_5m_legacy(20260806, "000001.SZ")

    assert rows[0]["close"] == 10.5
    assert "FROM `intraday_bars_5m`" in calls[0][0]
    assert "`close_price` AS `close`" in calls[0][0]
    assert calls[0][1] == (20260806, "000001")
