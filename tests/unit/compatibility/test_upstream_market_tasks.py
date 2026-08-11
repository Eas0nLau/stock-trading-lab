import importlib


def test_upstream_daily_task_forwards_exact_range(monkeypatch):
    module = importlib.import_module("task._1_日k数据更新")
    calls = []
    monkeypatch.setattr(
        module,
        "update_securities",
        lambda: calls.append("securities") or 1,
    )
    monkeypatch.setattr(
        module,
        "update_daily_quotes",
        lambda start, end, force=False: calls.append((start, end, force)) or 2,
    )

    assert module.main(20260801, 20260807, force=True) == {
        "securities": 1,
        "daily_quotes": 2,
    }
    assert calls == ["securities", (20260801, 20260807, True)]


def test_upstream_index_task_forwards_exact_range(monkeypatch):
    module = importlib.import_module("task._4_上证指数日k")
    calls = []
    monkeypatch.setattr(
        module,
        "update_index_daily",
        lambda start, end: calls.append((start, end)) or 3,
    )

    assert module.update(20260801, 20260807) == 3
    assert calls == [(20260801, 20260807)]
    assert module.main is module.update
