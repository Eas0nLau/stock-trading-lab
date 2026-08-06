from stock_lab.modules.market_data.helpers import (
    daily_quote_from_source,
    index_daily_from_source,
    normalize_symbol,
    normalize_trade_date,
    normalize_ts_code,
    security_from_source,
)


def test_normalize_ts_code_preserves_exchange_and_leading_zeroes():
    assert normalize_ts_code(" 000001.sz ") == "000001.SZ"
    assert normalize_ts_code(1) == "000001"


def test_normalize_symbol_returns_six_digit_code_without_exchange():
    assert normalize_symbol("1.SZ") == "000001"
    assert normalize_symbol("000300") == "000300"


def test_normalize_trade_date_accepts_source_date_values():
    assert normalize_trade_date("2026-08-05") == 20260805


def test_security_from_source_returns_canonical_columns():
    assert security_from_source({"ts_code": "1.SZ", "symbol": 1, "name": "A", "list_date": "20260805"}) == {
        "ts_code": "000001.SZ",
        "symbol": "000001",
        "name": "A",
        "area": None,
        "industry": None,
        "market": None,
        "list_date": 20260805,
        "list_status": None,
    }


def test_daily_quote_from_source_returns_canonical_columns():
    row = daily_quote_from_source(
        {"ts_code": "600000.SH", "trade_date": 20260805, "open": 10, "pre_close": 9.5, "close": 10.2},
        stock_name="Bank",
    )
    assert row["ts_code"] == "600000.SH"
    assert row["open_price"] == 10.0
    assert row["previous_close"] == 9.5
    assert row["data_id"] == "600000.SH_20260805"
    assert row["stock_name"] == "Bank"


def test_index_daily_from_source_returns_canonical_columns():
    row = index_daily_from_source({"date": "2026-08-05", "open": 1, "close": 2, "pct_chg": 3})
    assert row == {
        "trade_date": 20260805,
        "open_price": 1.0,
        "close_price": 2.0,
        "high_price": None,
        "low_price": None,
        "volume": None,
        "turnover": None,
        "amplitude_pct": None,
        "change_pct": 3.0,
        "change_amount": None,
        "turnover_rate": None,
    }
