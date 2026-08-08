from pathlib import Path
import ast
import json
import re

import pandas as pd
import pytest

from stock_lab.modules.research.context import ResearchContext, ResearchSafetyError
from stock_lab.modules.research.data import ResearchData
from stock_lab.modules.research.backtest import aggregate_results, next_trade_date, position_size, summarize_returns


ROOT = Path(__file__).parents[1]
LEGACY_TABLES = tuple(json.loads((ROOT / "db" / "schema_mapping.json").read_text(encoding="utf-8"))["tables"])
LEGACY_SQL_MIGRATION_TABLES = {
    Path("src/stock_lab/jobs/jiuyan_reconciliation.py"): {"t_韭研公社异动解析"},
}


def test_active_sql_contains_no_legacy_table_names():
    files = [
        path for path in ROOT.rglob("*.py")
        if "tests" not in path.parts and "__pycache__" not in path.parts and ".venv" not in path.parts
    ]
    offenders = []
    for path in files:
        source = path.read_text(encoding="utf-8")
        source = re.sub(r"(?m)#.*$", "", source)
        for table in LEGACY_TABLES:
            if table in LEGACY_SQL_MIGRATION_TABLES.get(path.relative_to(ROOT), set()):
                continue
            if re.search(rf"\b(?:from|join|update|into|table)\s+[`\"']?{re.escape(table)}\b", source, re.I):
                offenders.append(f"{path.relative_to(ROOT)}: {table}")
    assert offenders == [], "legacy SQL references:\n" + "\n".join(offenders)


def test_daily_quote_security_joins_normalize_qualified_code_to_symbol():
    offenders = []
    for path in (ROOT / "strategy").glob("*.py"):
        source = path.read_text(encoding="utf-8")
        if re.search(r"JOIN\s+securities\s+\w+\s+ON\s+\w+\.ts_code\s*=\s*\w+\.symbol", source, re.I):
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []


def test_strategy_launchers_do_not_convert_stock_codes_to_integers():
    patterns = (
        r"\[['\"](?:ts_code|stock_code|股票代码)['\"]\]\s*=\s*[^\n]*\.astype\(int\)",
        r"(?:codes_series|\.str\.extract\([^\n]+)\.astype\(int\)",
        r"int\((?:ts_code|stock_code|code|i)\)",
        r"int\([^\n)]*\[['\"]ts_code['\"]\]\)",
        r"\[int\(i\)\s+for\s+i\s+in\s+selected_stocks",
        r"int\([^\n)]*(?:\[['\"]股票代码['\"]\]|\.ts_code|str\(ts_code)",
        r"return\s+set\([^\n]*代码序列\.astype\(int\)",
        r"to_numeric\([^\n]*(?:symbol|ts_code)",
    )
    offenders = []
    for path in (ROOT / "strategy").glob("*.py"):
        source = path.read_text(encoding="utf-8")
        source = re.sub(r"(?m)#.*$", "", source)
        for pattern in patterns:
            if re.search(pattern, source):
                offenders.append(f"{path.relative_to(ROOT)}: {pattern}")
    assert offenders == [], "integer stock codes:\n" + "\n".join(offenders)


def test_official_selector_call_graphs_do_not_render_literal_code_filters():
    offenders = []
    for path in (ROOT / "strategy").glob("*.py"):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        functions = {
            node.name: node for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        pending = ["strategy"]
        reachable = set()
        while pending:
            name = pending.pop()
            if name in reachable or name not in functions:
                continue
            reachable.add(name)
            pending.extend(
                node.id for node in ast.walk(functions[name])
                if isinstance(node, ast.Name) and node.id in functions
            )
        reachable_source = "\n".join(
            ast.get_source_segment(source, functions[name]) or ""
            for name in reachable
        )
        if "stock_code_literals(" in reachable_source or "str(tuple(" in reachable_source:
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == [], "literal filters in official selectors:\n" + "\n".join(offenders)


def test_research_runtime_has_no_literal_stock_code_sql_helper():
    source = (ROOT / "src" / "stock_lab" / "modules" / "research" / "source_runtime.py").read_text(encoding="utf-8")
    assert "stock_code_literals" not in source


def test_market_value_selector_uses_bound_date_and_threshold_parameters():
    source = (ROOT / "strategy" / "20260616_市值100亿前日成交额360日新高策略.py").read_text(encoding="utf-8")
    assert "WHERE trade_date <= {int(end_date)}" not in source
    assert "WHERE trade_date = {mv_date}" not in source
    assert "total_market_value > {市值阈值_万元}" not in source


def test_strategy_launchers_do_not_interpolate_ts_code_in_tuples():
    offenders = []
    pattern = r"ts_code\s+IN\s+\{[^\n}]*str\(tuple"
    for path in (ROOT / "strategy").glob("*.py"):
        if re.search(pattern, path.read_text(encoding="utf-8"), re.I):
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == [], "literal ts_code filters:\n" + "\n".join(offenders)


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


def test_research_data_disables_missing_dragon_tiger_repository():
    data = ResearchData(FakeMarketData())
    with pytest.raises(ResearchSafetyError, match="dragon_tiger"):
        data.dragon_tiger_listings()


def test_test_context_preserves_falsy_injected_repository():
    class FalsyMarketData:
        def __bool__(self):
            return False

    repository = FalsyMarketData()
    assert ResearchContext.test_context(market_data=repository).market_data is repository


def test_backtest_primitives_preserve_trading_date_and_return_semantics():
    rows = pd.DataFrame({"trade_date": [20260101, 20260102], "entry": [10, 11], "exit": [11, 10]})
    assert next_trade_date([20260101, 20260102], 20260101) == 20260102
    result = summarize_returns(rows, "entry", "exit")
    assert result["returns"] == [10.0, -9.090909090909092]
    assert result["win_rate"] == 0.5


def test_position_size_uses_board_lots_and_allocation_limit():
    assert position_size(100_000, 12.5) == 8_000
    assert position_size(100_000, 12.5, max_allocation=0.25) == 2_000
    assert position_size(99, 12.5) == 0
    with pytest.raises(ValueError):
        position_size(100_000, 0)


def test_aggregate_results_handles_none_and_compounds_returns():
    assert aggregate_results([None, {"returns": [10.0, -5.0]}, {"returns": []}]) == {
        "trade_count": 2,
        "win_count": 1,
        "win_rate": 0.5,
        "average_return": 2.5,
        "compounded_return": pytest.approx(4.5),
    }
    assert aggregate_results([])["win_rate"] == 0.0
