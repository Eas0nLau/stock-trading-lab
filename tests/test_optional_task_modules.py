import importlib
import sys
from types import ModuleType, SimpleNamespace

import pytest


def _stub_app_dependencies(monkeypatch):
    redis = SimpleNamespace(exists=lambda _key: False, delete=lambda _key: None)
    db = SimpleNamespace(redis_con_localhost=redis)

    utils = ModuleType("utils")
    utils.db = db
    utils.driver_chrome = SimpleNamespace()
    monkeypatch.setitem(sys.modules, "utils", utils)

    front_run = ModuleType("front_run")
    front_run.run = lambda: None
    monkeypatch.setitem(sys.modules, "front_run", front_run)

    monitoring = ModuleType("实时监控")
    for name in ("资金流向", "策略选股", "情绪周期", "热门板块情绪"):
        module = SimpleNamespace(注册接口=lambda _app: None)
        setattr(monitoring, name, module)
    monkeypatch.setitem(sys.modules, "实时监控", monitoring)


def _import_app(monkeypatch):
    _stub_app_dependencies(monkeypatch)
    sys.modules.pop("app", None)
    return importlib.import_module("app")


def test_app_imports_without_unpublished_task_package(monkeypatch, capsys):
    for name in ("task", "task.每日更新", "task.盘前纪要"):
        monkeypatch.delitem(sys.modules, name, raising=False)

    app_module = _import_app(monkeypatch)
    captured = capsys.readouterr()

    assert app_module.每日更新 is not None
    assert app_module.盘前纪要 is None
    assert "已禁用每日更新和盘前纪要定时任务" not in captured.err


def test_app_uses_original_task_modules_when_present(monkeypatch):
    task = ModuleType("task")
    daily = ModuleType("task.每日更新")
    premarket = ModuleType("task.盘前纪要")
    task.每日更新 = daily
    task.盘前纪要 = premarket
    monkeypatch.setitem(sys.modules, "task", task)
    monkeypatch.setitem(sys.modules, "task.每日更新", daily)
    monkeypatch.setitem(sys.modules, "task.盘前纪要", premarket)

    app_module = _import_app(monkeypatch)

    assert app_module.每日更新 is daily
    assert app_module.盘前纪要 is premarket


def test_app_does_not_hide_dependency_errors_inside_task(monkeypatch, tmp_path):
    package = tmp_path / "task"
    package.mkdir()
    (package / "__init__.py").write_text(
        "from . import 每日更新, 盘前纪要\n", encoding="utf-8"
    )
    (package / "每日更新.py").write_text(
        "import missing_task_dependency\n", encoding="utf-8"
    )
    (package / "盘前纪要.py").write_text("", encoding="utf-8")
    monkeypatch.syspath_prepend(tmp_path)
    for name in ("task", "task.每日更新", "task.盘前纪要"):
        monkeypatch.delitem(sys.modules, name, raising=False)

    with pytest.raises(ModuleNotFoundError, match="missing_task_dependency"):
        _import_app(monkeypatch)
