import task.data_sources as data_sources


def test_trading_dates_skip_weekends_and_return_ascending(monkeypatch):
    monkeypatch.setattr(
        data_sources,
        "_read_index_dates",
        lambda limit: [20260807, 20260806, 20260805],
    )

    assert data_sources.交易日期列表(2) == [20260806, 20260807]


def test_index_payload_maps_akshare_columns():
    row = {
        "date": "2026-08-05",
        "open": 1,
        "close": 2,
        "high": 3,
        "low": 0,
        "volume": 4,
        "amount": 5,
        "amplitude": 6,
        "pct_chg": 7,
    }

    payload = data_sources.标准化指数行(row)

    assert payload["trade_date"] == 20260805
    assert payload["change_pct"] == 7


def test_stock_daily_upsert_key_is_date_and_code():
    row = {
        "ts_code": "600000.SH",
        "trade_date": 20260805,
        "open": 1,
        "high": 2,
        "low": 0.9,
        "close": 1.5,
        "pre_close": 1.4,
        "pct_chg": 7.14,
        "amount": 10,
    }

    payload = data_sources.股票日线记录(row)

    assert payload["ts_code"] == "600000.SH"
    assert payload["data_id"] == "600000.SH_20260805"
