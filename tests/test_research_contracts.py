from pathlib import Path
import json
import re

import pandas as pd

from stock_lab.modules.research.context import ResearchContext
from stock_lab.modules.research.data import ResearchData
from stock_lab.modules.research.backtest import next_trade_date, summarize_returns


ROOT = Path(__file__).parents[1]
LEGACY_TABLES = tuple(json.loads((ROOT / "db" / "schema_mapping.json").read_text(encoding="utf-8"))["tables"])


def test_active_sql_contains_no_legacy_table_names():
    files = list((ROOT / "strategy").glob("*.py"))
    files += list((ROOT / "游资溢价分析").rglob("*.py"))
    files += [ROOT / "utils" / "common.py", ROOT / "utils" / "account.py"]
    offenders = []
    for path in files:
        source = path.read_text(encoding="utf-8")
        source = re.sub(r"(?m)#.*$", "", source)
        for table in LEGACY_TABLES:
            if re.search(rf"\b(?:from|join|update|into|table)\s+[`\"']?{re.escape(table)}\b", source, re.I):
                offenders.append(f"{path.relative_to(ROOT)}: {table}")
    assert offenders == [], "legacy SQL references:\n" + "\n".join(offenders)


class FakeMarketData:
    def daily_quotes(self, *args, **kwargs):
        return [{"ts_code": "000001.SZ", "trade_date": 20260102, "close_price": 11}]

    def index_daily(self, *args, **kwargs):
        return [{"trade_date": 20260101}, {"trade_date": 20260102}]

    def securities(self, *args, **kwargs):
        return [{"ts_code": "000001.SZ", "symbol": "000001", "name": "平安银行"}]

    def kdj_indicators(self, *args, **kwargs):
        return [{"ts_code": "000001.SZ", "trade_date": 20260102, "k_value": 1, "d_value": 2, "j_value": 3}]

    def intraday_bars_5m(self, *args, **kwargs):
        return [{"stock_code": "000001", "trade_time": 930}]


def test_research_data_exposes_canonical_sources_without_side_effects():
    data = ResearchData(FakeMarketData(), dragon_tiger=None)
    assert data.daily_quotes()[0]["close_price"] == 11
    assert data.kdj_indicators()[0]["j_value"] == 3
    assert data.intraday_bars_5m()[0]["trade_time"] == 930


def test_backtest_primitives_preserve_trading_date_and_return_semantics():
    rows = pd.DataFrame({"trade_date": [20260101, 20260102], "entry": [10, 11], "exit": [11, 10]})
    assert next_trade_date([20260101, 20260102], 20260101) == 20260102
    result = summarize_returns(rows, "entry", "exit")
    assert result["returns"] == [10.0, -9.090909090909092]
    assert result["win_rate"] == 0.5
