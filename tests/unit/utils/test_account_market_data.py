from pathlib import Path

import config

config.ts_token_list = ["test-token"]
import utils.account as account


def test_account_shared_queries_use_english_daily_quotes_table():
    source = Path(account.__file__).read_text(encoding="utf-8")

    assert "FROM stock_daily" not in source
    assert "daily_quotes" in source


def test_sync_close_market_adapts_canonical_close_column(monkeypatch):
    account.holding_stocks = {
        "000001.SZ": {
            "lots": 100,
            "成本价": 900,
            "market_value": 900,
            "持仓最高市值": 900,
            "持仓最高回撤": 0,
            "盈亏比": 0,
            "盈亏": 0,
            "持股天数": 1,
            "close_price": 9,
        }
    }
    account.market_value = 900
    monkeypatch.setattr(account.pd, "read_sql", lambda *args, **kwargs: account.pd.DataFrame([{
        "ts_code": "000001.SZ", "close": 10, "pre_close": 9, "open": 9.5, "high": 10, "low": 9,
    }]))

    account.sync_close_market(20260806)

    assert account.holding_stocks["000001.SZ"]["close_price"] == 10


def test_account_open_close_and_sell_paths_match_bare_holdings(monkeypatch):
    def make_holding(days=2):
        return {
            "000001": {
                "lots": 100,
                "成本价": 900,
                "market_value": 900,
                "持仓最高市值": 900,
                "持仓最高回撤": 0,
                "盈亏比": 0,
                "盈亏": 0,
                "持股天数": days,
                "close_price": 9,
                "name": "Bank",
            }
        }

    captured = []

    def fake_read_sql(sql, *args, **kwargs):
        captured.append(sql)
        return account.pd.DataFrame([
            {"ts_code": "000001.SZ", "close": 10, "pre_close": 9, "open": 9.5, "high": 10, "low": 9, "pct_chg": 1}
        ] * 3)

    monkeypatch.setattr(account.pd, "read_sql", fake_read_sql)
    account.holding_stocks = make_holding()
    account.sync_open_market_before(20260806)
    account.holding_stocks = make_holding()
    account.sync_close_market(20260806)
    account.holding_stocks = make_holding(days=1)
    account.simulated_sell(now_date=20260806)

    assert len(captured) == 3
    assert all("LPAD(SUBSTRING_INDEX(`ts_code`, '.', 1), 6, '0')" in sql for sql in captured)
