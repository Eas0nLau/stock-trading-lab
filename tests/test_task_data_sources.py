import pandas as pd

import task.data_sources as legacy_data_sources
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
    import sys
    import types

    calls = []

    class Repository:
        def upsert_index_daily(self, rows):
            calls.append(rows)
            return len(rows)

    monkeypatch.setattr(data_sources, "create_default_repository", lambda: Repository())
    monkeypatch.setitem(sys.modules, "akshare", types.SimpleNamespace(
        stock_zh_index_daily=lambda symbol: pd.DataFrame([{"date": "2026-08-05", "close": 2}])
    ))

    assert data_sources.update_index_daily(20260805, 20260805) == 1
    assert calls[0][0]["trade_date"] == 20260805


def test_legacy_market_data_names_forward_to_official_functions(monkeypatch):
    monkeypatch.setattr(legacy_data_sources, "trading_dates", lambda limit: [limit])

    assert legacy_data_sources.交易日期列表(7) == [7]
