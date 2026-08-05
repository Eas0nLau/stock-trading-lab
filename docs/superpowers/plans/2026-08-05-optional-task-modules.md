# Optional Task Modules Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow the public application to start without the unpublished `task` package and automatically enable the original scheduler when that package is later supplied.

**Architecture:** Keep task loading in `app.py`, catch only the absence of the top-level `task` package, and represent unavailable modules as `None`. Guard the two scheduling branches and startup lock cleanup while preserving every other route, service, and monitoring path.

**Tech Stack:** Python 3.12, FastAPI, pytest, uv

## Global Constraints

- Missing top-level `task` is optional; errors inside an existing package must propagate.
- Both original task modules are one capability and must become available together.
- Restoring a complete `task/` directory and restarting must automatically restore scheduling.
- Do not create placeholder task implementations or infer unpublished behavior.
- Preserve real-time monitoring, FastAPI routes, Redis, MySQL, and frontend startup behavior.

---

### Task 1: Add Import-Behavior Tests

**Files:**
- Create: `tests/test_optional_task_modules.py`

**Interfaces:**
- Consumes: module-level names `每日更新` and `盘前纪要` from `app.py`
- Produces: regression tests defining absent, present, and broken-package behavior

- [ ] **Step 1: Create isolated app-import helpers and failing tests**

```python
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

    assert app_module.每日更新 is None
    assert app_module.盘前纪要 is None
    assert "已禁用每日更新和盘前纪要定时任务" in captured.err


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
```

- [ ] **Step 2: Run the tests to verify the current hard import fails**

Run:

```powershell
$env:PYTHONIOENCODING = "utf-8"
uv run --frozen python -m pytest tests/test_optional_task_modules.py -v
```

Expected: the absent-package test fails with `ModuleNotFoundError: No module named 'task'`; do not proceed unless this failure is observed.

### Task 2: Make Scheduled Tasks Optional

**Files:**
- Modify: `app.py:9-12`
- Modify: `app.py:57-66`
- Modify: `app.py:91-95`
- Test: `tests/test_optional_task_modules.py`

**Interfaces:**
- Consumes: optional modules `task.每日更新` and `task.盘前纪要`
- Produces: module references of the imported module type or `None`

- [ ] **Step 1: Replace the unconditional task import**

Move the existing Loguru import above task loading, then use this exact behavior:

```python
from loguru import logger

try:
    from task import 每日更新, 盘前纪要
except ModuleNotFoundError as error:
    if error.name != "task":
        raise
    每日更新 = None
    盘前纪要 = None
    logger.warning("未找到可选 task 包，已禁用每日更新和盘前纪要定时任务")
```

- [ ] **Step 2: Guard each scheduled branch**

Change the two conditions in `start_scraper()` so module availability is checked first:

```python
if 每日更新 is not None and now.weekday() < 5 and datetime.time(17, 35) <= now.time():
```

```python
if 盘前纪要 is not None and now.weekday() < 5 and datetime.time(8, 0) <= now.time():
```

Keep the existing Redis checks and `Timer` calls inside each guarded branch unchanged.

- [ ] **Step 3: Guard startup lock cleanup**

Replace unconditional deletes in the `__main__` block with:

```python
if 每日更新 is not None:
    db.redis_con_localhost.delete("run_check:每日更新.py")
if 盘前纪要 is not None:
    db.redis_con_localhost.delete("run_check:盘前纪要.py")
```

Keep frontend and Uvicorn startup unchanged.

- [ ] **Step 4: Run the focused tests**

Run:

```powershell
$env:PYTHONIOENCODING = "utf-8"
uv run --frozen python -m pytest tests/test_optional_task_modules.py -v
```

Expected: 3 tests pass.

### Task 3: Verify the Public Checkout Startup Boundary

**Files:**
- Verify: `app.py`
- Verify: `pyproject.toml`
- Verify: `uv.lock`

**Interfaces:**
- Consumes: synchronized `.venv`, local MySQL 8.0, and local Redis
- Produces: verified importable FastAPI application without `task/`

- [ ] **Step 1: Verify the real application import**

Run:

```powershell
$env:PYTHONIOENCODING = "utf-8"
uv run --frozen python -c "import app; print(app.app.title); print(app.每日更新, app.盘前纪要)"
```

Expected: warning about the missing optional task package, title `stock_trading_lab_api`, and `None None`.

- [ ] **Step 2: Run all available tests**

Run:

```powershell
uv run --frozen python -m pytest -v
```

Expected: all tests pass.

- [ ] **Step 3: Build the frontend before starting services**

Run:

```powershell
Push-Location front
npm ci
npm run build
Pop-Location
```

Expected: npm exits 0 and creates `front/dist/`.

- [ ] **Step 4: Start the application for manual verification**

Run from the repository root:

```powershell
$env:PYTHONIOENCODING = "utf-8"
uv run --frozen python app.py
```

Expected: FastAPI listens on `http://localhost:8051`, Vite listens on `http://localhost:8990`, and startup does not fail because `task/` is absent. Browser monitoring may still require correcting `config.project_path` before the lifespan is exercised.
