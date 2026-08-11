import pandas as pd

from stock_lab.modules.market_data import collectors as data_sources


def test_trading_dates_skip_weekends_and_return_ascending(monkeypatch):
    monkeypatch.setattr(
        data_sources,
        "create_default_collector",
        lambda: type("Collector", (), {"trading_dates": lambda self, limit: [20260805, 20260806, 20260807]})(),
    )

    assert data_sources.trading_dates(2) == [20260806, 20260807]


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

    payload = data_sources.normalize_index_row(row)

    assert payload["trade_date"] == 20260805
    assert payload["change_pct"] == 7


def test_index_payload_maps_baostock_columns():
    payload = data_sources.normalize_index_row({
        "date": "2026-08-05",
        "close": 2,
        "pctChg": 7,
        "turn": 1.5,
    })

    assert payload["trade_date"] == 20260805
    assert payload["change_pct"] == 7
    assert payload["turnover_rate"] == 1.5


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

    payload = data_sources.normalize_daily_quote(row)

    assert payload["ts_code"] == "600000.SH"
    assert payload["data_id"] == "600000.SH_20260805"


def test_update_index_daily_delegates_canonical_rows_to_repository(monkeypatch):
    calls = []

    class Repository:
        def upsert_index_daily(self, rows):
            calls.append(rows)
            return len(rows)

    collector = data_sources.MarketDataCollector(
        Repository(),
        index_source=lambda start, end: calls.append((start, end)) or [
            {"date": "2026-08-05", "close": 2}
        ],
        security_source=lambda: pd.DataFrame(),
        quote_source=lambda _date: pd.DataFrame(),
    )

    assert collector.update_index_daily(20260805, 20260805) == 1
    assert calls[0] == (20260805, 20260805)
    assert calls[1][0]["trade_date"] == 20260805
