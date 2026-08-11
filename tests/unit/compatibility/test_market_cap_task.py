import importlib


def test_market_cap_task_forwards_upstream_names(monkeypatch):
    module = importlib.import_module("task._7_市值信息每日更新")
    calls = []
    monkeypatch.setattr(
        module,
        "_update_market_cap",
        lambda start, end, force=False: calls.append((start, end, force)) or {"status": "success"},
    )

    assert module.更新(20260801, 20260807, only_missing=True) == {"status": "success"}
    assert module.主函数(20260801, 20260807, force=True) == {"status": "success"}
    assert calls == [
        (20260801, 20260807, False),
        (20260801, 20260807, True),
    ]
    assert module.update is module.更新
    assert module.main is module.主函数
