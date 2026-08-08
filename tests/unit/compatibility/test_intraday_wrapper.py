import importlib
import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest


class Source:
    def fetch_5m_bars(self, start_date, end_date, ts_code):
        return [{
            "date": "2026-08-06", "time": "20260806093500000", "code": "sz.000001",
            "open": "10", "high": "11", "low": "9", "close": "10.5",
            "volume": "100", "amount": "1050", "adjustflag": "3",
        }]


def test_missing_chinese_task_import_returns_historical_list_shape():
    module = importlib.import_module("task._2_分时数据获取_5分k")

    rows = module.get_data(20260806, 20260806, "000001.SZ", source=Source())

    assert rows == [["10", "10.5", "2026-08-06", "20260806093500000", "sz.000001", "11", "9", "100", "1050", "3"]]


def test_active_stock_keyword_consumer_uses_historical_signature():
    module = importlib.import_module("task._2_分时数据获取_5分k")

    rows = module.get_data(
        start_date=20260806,
        end_date=20260806,
        stock="430001.BJ",
        source=Source(),
    )

    assert rows[0][4] == "bj.430001"


def test_wrapper_rejects_ambiguous_code_and_stock_arguments():
    module = importlib.import_module("task._2_分时数据获取_5分k")

    with pytest.raises(TypeError, match="code or stock"):
        module.get_data(20260806, 20260806, "000001.SZ", stock="600000.SH", source=Source())


def test_active_strategy_calls_wrapper_stock_keyword_with_injected_source(monkeypatch):
    root = Path(__file__).parents[3]
    fake_common = SimpleNamespace(
        load_stock_symbol_ts_code_dict=lambda: {"000001.SZ": "000001.SZ"},
        get_next_date=lambda _date: 20260807,
        stock_code_literals=lambda codes: "(" + ", ".join(f"'{code}'" for code in codes) + ")",
    )
    fake_account = SimpleNamespace(
        next_date_pre_selection_stocks={
            "selected_stocks": __import__("pandas").DataFrame([{"stock_name": "A", "ts_code": "000001.SZ"}]),
            "target_date": 20260806,
        },
        holding_stocks={},
        available_amount=10000.0,
        market_value=0.0,
        min_available_amount=10000.0,
        计算最大可买手数=lambda **_kwargs: 1,
    )
    fake_utils = ModuleType("utils")
    fake_utils.db = SimpleNamespace(engine=object())
    fake_utils.common = fake_common
    fake_utils.account = fake_account
    monkeypatch.setitem(sys.modules, "utils", fake_utils)

    path = root / "strategy" / "20250113_量价齐升_近20日无跌停.py"
    spec = importlib.util.spec_from_file_location("active_strategy_for_contract", path)
    strategy = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, strategy)
    spec.loader.exec_module(strategy)

    calls = []

    def fake_fetch(start_date, end_date, ts_code, source=None):
        calls.append((start_date, end_date, ts_code, source))
        return [{
            "trade_date": 20260807, "trade_time": 20260807093500000,
            "stock_code": "000001", "open_price": 10.0, "high_price": 11.0,
            "low_price": 9.0, "close_price": 10.5, "volume": 100.0,
            "turnover": 1050.0, "adjustment_flag": 3,
        }]

    monkeypatch.setattr(strategy._2_分时数据获取_5分k, "fetch_intraday_bars_5m", fake_fetch)
    monkeypatch.setattr(
        strategy.pd,
        "read_sql",
        lambda *_args, **_kwargs: __import__("pandas").DataFrame([
            {
                "ts_code": "000001.SZ", "trade_date": 20260806, "close": 10.0,
                "stock_name": "A", "open": 9.5, "pre_close": 9.5,
                "high": 10.5, "low": 9.0,
            },
            {
                "ts_code": "000001.SZ", "trade_date": 20260807, "close": 10.5,
                "stock_name": "A", "open": 10.0, "pre_close": 9.5,
                "high": 11.0, "low": 9.0,
            },
        ]),
    )

    strategy.simulated_buy()

    assert calls == [(20260807, 20260807, "000001.SZ", None)]
