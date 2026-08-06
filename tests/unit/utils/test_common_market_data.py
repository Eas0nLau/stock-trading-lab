from pathlib import Path

import config

config.ts_token_list = ["test-token"]
import utils.common as common


def test_shared_common_queries_use_english_market_data_tables():
    source = Path(common.__file__).read_text(encoding="utf-8")

    assert "FROM stock_basic" not in source
    assert "FROM stock_daily" not in source
    assert "FROM akshare_sh000001" not in source
    assert "daily_quotes" in source
    assert "index_daily" in source


def test_load_stock_daily_data_adapts_canonical_columns(monkeypatch):
    captured = {}

    def fake_query(sql, params=None, fetch=False):
        captured["sql"] = sql
        return [{"ts_code": "000001.SZ", "trade_date": 20260806, "open": 10}]

    monkeypatch.setattr(common.db, "mysql_localhost", fake_query)

    result = common.load_stock_daily_data(["000001.SZ"], 20260801, 20260806)

    assert result.iloc[0]["ts_code"] == "000001.SZ"
    assert "daily_quotes" in captured["sql"]
    assert "stock_daily" not in captured["sql"]


def test_load_stock_daily_data_matches_bare_pool_symbol_to_qualified_code(monkeypatch):
    captured = {}

    def fake_query(sql, params=None, fetch=False):
        captured["sql"] = sql
        return [{"ts_code": "000001.SZ", "trade_date": 20260806, "open": 10}]

    monkeypatch.setattr(common.db, "mysql_localhost", fake_query)

    common.load_stock_daily_data(["000001"], 20260801, 20260806)

    assert "SUBSTRING_INDEX(`ts_code`, '.', 1)" in captured["sql"]
    assert "LPAD(" in captured["sql"]
