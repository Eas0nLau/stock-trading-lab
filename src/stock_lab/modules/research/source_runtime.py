import ast
import builtins
import importlib
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
from loguru import logger

from stock_lab.modules.dragon_tiger.analytics import analyze_broker_premium
from stock_lab.modules.fund_flow.repository import FundFlowRepository
from stock_lab.modules.market_data.helpers import normalize_symbol, normalize_ts_code, stock_code_filter

from .context import ResearchConfigurationError, ResearchExecutionError
from .results import SelectionResult


LEGACY_DAILY_COLUMNS = (
    "ts_code", "trade_date", "open", "high", "low", "close", "pre_close",
    "change", "pct_chg", "vol", "amount", "stock_name", "total_mv", "circ_mv",
)
SAFE_IMPORTS = {"datetime", "decimal", "json", "math", "pathlib"}
SAFE_BUILTIN_NAMES = {
    "ArithmeticError", "AssertionError", "AttributeError", "Exception", "IndexError",
    "KeyError", "LookupError", "NameError", "RuntimeError", "StopIteration",
    "TypeError", "ValueError", "ZeroDivisionError", "__build_class__", "abs", "all",
    "any", "bool", "callable", "classmethod", "dict", "enumerate", "filter", "float",
    "frozenset", "getattr", "hasattr", "hash", "int", "isinstance", "issubclass",
    "iter", "len", "list", "map", "max", "min", "next", "object", "pow",
    "property", "range", "repr", "reversed", "round", "set", "setattr", "slice",
    "sorted", "staticmethod", "str", "sum", "super", "tuple", "type", "zip",
}
SAFE_BUILTINS = {name: getattr(builtins, name) for name in SAFE_BUILTIN_NAMES}
SAFE_RUNTIME_IMPORTS = SAFE_IMPORTS | {"_strptime", "calendar", "locale", "time"}


def _safe_import(name, globals=None, locals=None, fromlist=(), level=0):
    if level or name.split(".", 1)[0] not in SAFE_RUNTIME_IMPORTS:
        raise ImportError(f"strategy runtime import is not allowed: {name}")
    return builtins.__import__(name, globals, locals, fromlist, level)


SAFE_BUILTINS["__import__"] = _safe_import


class StrategyDateTime(datetime):
    @classmethod
    def strptime(cls, value, format):
        if format != "%Y%m%d":
            raise ValueError("strategy runtime only supports %Y%m%d date parsing")
        value = str(value)
        if len(value) != 8 or not value.isdigit():
            raise ValueError(f"time data {value!r} does not match format {format!r}")
        return cls(int(value[:4]), int(value[4:6]), int(value[6:8]))


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

    stock_code_filter = staticmethod(stock_code_filter)

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

    def read_sql(self, sql, params=None):
        return self._provider.read_sql(sql, params=params)


class OfflineRedisProxy:
    def get(self, key):
        return None

    def lrange(self, key, start, end):
        return []


class IniOutputProxy:
    @staticmethod
    def write_ini_list(*args, **kwargs):
        return None


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
    except NameError:
        raise
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
            _validate_class_body(node, path)
            body.append(node)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)) and _is_safe_assignment(node):
            body.append(node)
    module = ast.fix_missing_locations(ast.Module(body=body, type_ignores=[]))
    common = CommonProxy(context)
    account = SimpleNamespace(holding_stocks={}, next_date_pre_selection_stocks={"selected_stocks": None, "target_date": None})
    namespace = {
        "__builtins__": dict(SAFE_BUILTINS), "__file__": str(path), "__name__": "__strategy__", "Path": Path,
        "pd": pd, "np": np, "logger": logger,
        "datetime": StrategyDateTime, "timedelta": timedelta, "Pool": SequentialPool,
        "tqdm": lambda values, **kwargs: values, "common": common,
        "timer_statistics": common.timer_statistics,
        "db": DbProxy(context.query_provider), "account": account,
        "ini_util": IniOutputProxy(),
        "premium_analysis": PremiumAnalysisProxy(context),
        "fund_flow_repository": FundFlowRepository(getattr(context.query_provider, "cache", OfflineRedisProxy())),
        "normalize_symbol": normalize_symbol, "normalize_ts_code": normalize_ts_code,
    }
    _inject_safe_imports(tree, namespace)
    if namespace.get("datetime") is datetime:
        namespace["datetime"] = StrategyDateTime
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


def _validate_class_body(node, path):
    for statement in node.body:
        harmless = isinstance(statement, ast.Pass)
        harmless = harmless or (
            isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef))
            and not statement.decorator_list
            and not any(
                isinstance(item, (ast.Call, ast.Await, ast.Lambda, ast.NamedExpr))
                for expression in (*statement.args.defaults, *statement.args.kw_defaults)
                if expression is not None
                for item in ast.walk(expression)
            )
        )
        harmless = harmless or (
            isinstance(statement, ast.Expr)
            and isinstance(statement.value, ast.Constant)
            and isinstance(statement.value.value, str)
        )
        harmless = harmless or (
            isinstance(statement, (ast.Assign, ast.AnnAssign))
            and _is_safe_assignment(statement)
            and not any(
                isinstance(item, (ast.Call, ast.Await, ast.Lambda, ast.NamedExpr, ast.comprehension))
                for item in ast.walk(statement.value)
            )
        )
        if not harmless:
            raise ResearchExecutionError(
                f"{path} class body contains executable statement in {node.name}"
            )


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


def _inject_safe_imports(tree, namespace):
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name not in SAFE_IMPORTS:
                    continue
                namespace[alias.asname or alias.name] = importlib.import_module(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module in SAFE_IMPORTS:
            module = importlib.import_module(node.module)
            for alias in node.names:
                if alias.name == "*":
                    continue
                namespace[alias.asname or alias.name] = getattr(module, alias.name)
