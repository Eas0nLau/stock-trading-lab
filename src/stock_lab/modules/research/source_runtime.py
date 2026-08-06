import ast
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
from loguru import logger

from stock_lab.modules.dragon_tiger.analytics import analyze_broker_premium
from stock_lab.modules.market_data.helpers import normalize_symbol, normalize_ts_code

from .context import ResearchConfigurationError, ResearchExecutionError
from .results import SelectionResult


LEGACY_DAILY_COLUMNS = (
    "ts_code", "trade_date", "open", "high", "low", "close", "pre_close",
    "change", "pct_chg", "vol", "amount", "stock_name", "total_mv", "circ_mv",
)


class SequentialPool:
    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def map(self, function, values):
        return [function(value) for value in values]

    def imap_unordered(self, function, values):
        return iter(self.map(function, values))


class CommonProxy:
    def __init__(self, context):
        self.context = context

    def load_daily_quotes_data(self, filtered_codes, start_date, target_date):
        rows = self.context.market_data.daily_quotes(filtered_codes, start_date, target_date)
        projected = []
        for row in rows:
            projected.append({
                "ts_code": normalize_ts_code(row.get("ts_code")),
                "trade_date": int(row.get("trade_date")),
                "open": row.get("open_price"), "high": row.get("high_price"),
                "low": row.get("low_price"), "close": row.get("close_price"),
                "pre_close": row.get("previous_close"), "change": row.get("change_amount"),
                "pct_chg": row.get("change_pct"), "vol": row.get("volume"),
                "amount": row.get("turnover"), "stock_name": row.get("stock_name"),
                "total_mv": row.get("total_market_value"), "circ_mv": row.get("circulating_market_value"),
            })
        return pd.DataFrame(projected, columns=LEGACY_DAILY_COLUMNS)

    normalize_symbol = staticmethod(normalize_symbol)
    normalize_ts_code = staticmethod(normalize_ts_code)

    @staticmethod
    def stock_code_literals(codes):
        normalized = sorted({normalize_ts_code(code) for code in codes})
        return "(" + ", ".join(f"'{code}'" for code in normalized) + ")" if normalized else "(NULL)"

    load_stock_daily_data = load_daily_quotes_data

    def load_stock_pool(self):
        return self.context.market_data.security_codes()

    def load_stock_pool_symbol(self):
        return [normalize_symbol(code) for code in self.context.market_data.security_codes()]

    def load_stock_symbol_ts_code_dict(self):
        return {
            normalize_symbol(row["ts_code"]): normalize_ts_code(row["ts_code"])
            for row in self.context.market_data.securities()
        }

    def get_next_date(self, target_date):
        dates = self.context.market_data.market_data.trading_dates(10000)
        return next((date for date in dates if int(date) > int(target_date)), None)

    @staticmethod
    def timer_statistics(function):
        return function


class DbProxy:
    def __init__(self, provider):
        self._provider = provider
        self.engine = provider.engine
        self.redis_con_localhost = getattr(provider, "cache", OfflineRedisProxy())

    def mysql_localhost(self, sql=None, params=None, fetch=False, commit=False):
        return self._provider.query(sql, params=params, fetch=fetch, commit=commit)


class OfflineRedisProxy:
    def get(self, key):
        return None

    def lrange(self, key, start, end):
        return []


class PremiumAnalysisProxy:
    def __init__(self, context):
        self.context = context

    def main(self, start_date, latest_date):
        return analyze_broker_premium(
            start_date,
            latest_date,
            self.context.dragon_tiger,
            self.context.market_data.market_data,
        )


def run_source_selector(strategy_id, display_name, source_path, context):
    if context.target_date is None:
        raise ResearchConfigurationError("target_date is required")
    namespace = _load_selector_namespace(Path(source_path), context)
    strategy = namespace.get("strategy")
    if not callable(strategy):
        raise ResearchConfigurationError(f"{source_path} does not define strategy(filtered_codes, target_date)")
    codes = context.market_data.security_codes()
    try:
        selected = strategy(codes, int(context.target_date))
    except Exception as error:
        raise ResearchExecutionError(f"strategy {strategy_id} failed: {error}") from error
    frame = selected if isinstance(selected, pd.DataFrame) else pd.DataFrame(selected or [])
    rows = frame.where(frame.notna(), None).to_dict("records") if not frame.empty else []
    for row in rows:
        if row.get("ts_code") is not None:
            row["ts_code"] = normalize_ts_code(row["ts_code"])
    return SelectionResult(strategy_id, display_name, int(context.target_date), rows)


def _load_selector_namespace(path, context):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    functions = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    reachable = _reachable_functions(functions, "strategy")
    body = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in reachable:
            body.append(node)
        elif isinstance(node, ast.ClassDef):
            body.append(node)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)) and _is_safe_assignment(node):
            body.append(node)
    module = ast.fix_missing_locations(ast.Module(body=body, type_ignores=[]))
    common = CommonProxy(context)
    account = SimpleNamespace(holding_stocks={}, next_date_pre_selection_stocks={"selected_stocks": None, "target_date": None})
    namespace = {
        "__builtins__": __builtins__, "__file__": str(path), "Path": Path,
        "pd": pd, "np": np, "logger": logger,
        "datetime": datetime, "timedelta": timedelta, "Pool": SequentialPool,
        "tqdm": lambda values, **kwargs: values, "common": common,
        "timer_statistics": common.timer_statistics,
        "db": DbProxy(context.query_provider), "account": account,
        "溢价分析": PremiumAnalysisProxy(context),
        "normalize_symbol": normalize_symbol, "normalize_ts_code": normalize_ts_code,
    }
    exec(compile(module, str(path), "exec"), namespace)
    return namespace


def _is_safe_assignment(node):
    safe_roots = {
        "bool", "datetime", "dict", "float", "frozenset", "int", "list",
        "max", "min", "Path", "round", "set", "str", "timedelta", "tuple",
    }
    for call in (item for item in ast.walk(node.value) if isinstance(item, ast.Call)):
        root = call.func
        while isinstance(root, ast.Attribute):
            root = root.value
        if not isinstance(root, ast.Name) or root.id not in safe_roots:
            return False
    return True


def _reachable_functions(functions, root):
    reachable = set()
    pending = [root]
    while pending:
        name = pending.pop()
        if name in reachable or name not in functions:
            continue
        reachable.add(name)
        called = {
            node.id
            for node in ast.walk(functions[name])
            if isinstance(node, ast.Name) and node.id in functions
        }
        pending.extend(called - reachable)
    return reachable
