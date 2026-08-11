import importlib

import pandas as pd


def test_dde_task_projects_single_stock_rows_to_dataframe(monkeypatch):
    module = importlib.import_module("task._10_开盘啦dde读取")

    class Source:
        def fetch_daily_dde(self, stock_code, **kwargs):
            assert stock_code == "000001.SZ"
            assert kwargs["count"] == 2
            return [{"stock_code": "000001", "trade_date": 20260807, "dde": 3.0}]

    monkeypatch.setattr(module, "KplDdeSource", Source)

    result = module.读取历史日K_DDE("000001.SZ", count=2)

    assert isinstance(result, pd.DataFrame)
    assert result.to_dict("records") == [
        {"stock_code": "000001", "trade_date": 20260807, "dde": 3.0}
    ]


def test_dde_task_forwards_update_aliases(monkeypatch):
    module = importlib.import_module("task._10_开盘啦dde读取")
    calls = []
    monkeypatch.setattr(
        module,
        "_update_dde",
        lambda start, end, **kwargs: calls.append((start, end, kwargs)) or {"status": "success"},
    )

    assert module.更新(20260801, 20260807, only_missing=True) == {"status": "success"}
    assert module.主函数(20260801, 20260807, force=True) == {"status": "success"}
    assert calls[0][2]["force"] is False
    assert calls[1][2]["force"] is True
    assert module.update is module.更新
    assert module.main is module.主函数
