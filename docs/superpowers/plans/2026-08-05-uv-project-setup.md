# uv Project Setup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `pyproject.toml` and `uv.lock` the authoritative, reproducible Python 3.12 environment for the application.

**Architecture:** Define the application with PEP 621 metadata and disable package installation because the repository is executed from its root. Preserve all currently pinned dependencies, separate development tools into uv's `dev` group, replace the unavailable DrissionPage patch release, and export a UTF-8 compatibility requirements file from the lock.

**Tech Stack:** Python 3.12, uv 0.11+, PEP 621, TOML

## Global Constraints

- Python must remain `>=3.12,<3.13`.
- The repository is an application, so `[tool.uv] package = false` is required.
- DrissionPage must be pinned to the verified available version `4.1.1.4`.
- `pyproject.toml` and `uv.lock` are authoritative; `requirements.txt` is generated from the lock.
- Existing application source code is not modified in this plan.

---

### Task 1: Define the uv Project

**Files:**
- Create: `pyproject.toml`

**Interfaces:**
- Consumes: the exact dependency pins currently stored in `requirements.txt`
- Produces: PEP 621 project metadata consumed by `uv lock`, `uv sync`, and the optional-task implementation plan

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[project]
name = "stock-trading-lab"
version = "0.1.0"
description = "Local A-share research, monitoring, and analysis tools"
readme = "README.md"
requires-python = ">=3.12,<3.13"
dependencies = [
  "aiohappyeyeballs==2.6.1",
  "aiohttp==3.12.15",
  "aiosignal==1.4.0",
  "akshare==1.17.54",
  "annotated-doc==0.0.4",
  "annotated-types==0.7.0",
  "anyio==4.13.0",
  "attrs==25.3.0",
  "baostock==0.9.1",
  "beautifulsoup4==4.13.5",
  "bs4==0.0.2",
  "certifi==2025.8.3",
  "charset-normalizer==3.4.3",
  "choreographer==1.1.2",
  "click==8.3.2",
  "colorama==0.4.6",
  "cssselect==1.4.0",
  "datarecorder==3.6.2",
  "decorator==5.2.1",
  "downloadkit==2.0.7",
  "drissionpage==4.1.1.4",
  "et-xmlfile==2.0.0",
  "fastapi==0.136.1",
  "filelock==3.25.2",
  "frozenlist==1.7.0",
  "fsspec==2026.3.0",
  "greenlet==3.2.4",
  "h11==0.16.0",
  "html5lib==1.1",
  "huggingface-hub==0.36.2",
  "idna==3.10",
  "jsonpath==0.82.2",
  "kaleido==1.1.0",
  "logistro==1.1.0",
  "loguru==0.7.3",
  "lxml==6.0.1",
  "mini-racer==0.12.4",
  "multidict==6.6.4",
  "mysql-connector-python==9.4.0",
  "narwhals==2.7.0",
  "nest-asyncio==1.6.0",
  "numpy==2.3.3",
  "openpyxl==3.1.5",
  "orjson==3.11.3",
  "packaging==25.0",
  "pandas==2.3.2",
  "plotly==6.3.1",
  "propcache==0.3.2",
  "psutil==7.2.2",
  "pydantic==2.13.3",
  "pydantic-core==2.46.3",
  "pymysql==1.1.2",
  "python-dateutil==2.9.0.post0",
  "pytz==2025.2",
  "pyyaml==6.0.3",
  "redis==6.4.0",
  "requests==2.32.5",
  "requests-file==3.0.1",
  "simplejson==3.20.1",
  "six==1.17.0",
  "soupsieve==2.8",
  "sqlalchemy==2.0.43",
  "starlette==1.0.0",
  "tabulate==0.9.0",
  "tldextract==5.3.1",
  "tokenizers==0.19.1",
  "tqdm==4.67.1",
  "tushare==1.4.24",
  "typing-extensions==4.15.0",
  "typing-inspection==0.4.2",
  "tzdata==2025.2",
  "urllib3==2.5.0",
  "uvicorn==0.46.0",
  "webencodings==0.5.1",
  "websocket-client==1.8.0",
  "win32-setctime==1.2.0",
  "xlrd==2.0.2",
  "yarl==1.20.1",
]

[dependency-groups]
dev = [
  "iniconfig==2.1.0",
  "pandas-stubs==3.0.0.260204",
  "pip-chill==1.0.3",
  "pluggy==1.6.0",
  "pygments==2.19.2",
  "pytest==8.4.2",
  "pytest-timeout==2.4.0",
  "setuptools==78.1.1",
  "wheel==0.45.1",
]

[tool.uv]
package = false
```

- [ ] **Step 2: Validate TOML and dependency resolution**

Run:

```powershell
uv lock --dry-run
```

Expected: exit code 0; resolution includes `drissionpage==4.1.1.4` and reports no unsatisfiable dependency.

### Task 2: Lock, Synchronize, and Export the Environment

**Files:**
- Create: `uv.lock`
- Modify: `requirements.txt`
- Create locally: `.venv/` (untracked environment)

**Interfaces:**
- Consumes: `pyproject.toml` from Task 1
- Produces: a synchronized Python 3.12 environment used by tests and application startup

- [ ] **Step 1: Generate the lock file**

Run:

```powershell
uv lock
uv lock --check
```

Expected: both commands exit 0 and `uv.lock` exists.

- [ ] **Step 2: Synchronize all dependency groups**

Run:

```powershell
uv sync --all-groups --frozen
```

Expected: exit code 0 and `.venv\Scripts\python.exe` exists.

- [ ] **Step 3: Verify the interpreter and critical dependency**

Run:

```powershell
uv run --frozen python --version
uv run --frozen python -c "import DrissionPage; print(DrissionPage.__version__)"
```

Expected: Python reports `3.12.x`; DrissionPage reports `4.1.1.4`.

- [ ] **Step 4: Export pip-compatible requirements**

Run:

```powershell
uv export --format requirements-txt --all-groups --no-hashes --no-emit-project --output-file requirements.txt
```

Expected: exit code 0; `requirements.txt` is UTF-8 and contains `drissionpage==4.1.1.4`.

- [ ] **Step 5: Verify backend core imports and local services**

Run:

```powershell
$env:PYTHONIOENCODING = "utf-8"
uv run --frozen python -c "from utils import db; from 实时监控 import 资金流向, 策略选股, 情绪周期, 热门板块情绪; print('REDIS', db.redis_con_localhost.ping()); print('MYSQL', db.mysql_localhost('SELECT VERSION() AS version', fetch=True)); print('CORE_IMPORTS_OK')"
```

Expected: Redis is `True`, MySQL reports version `8.0.45`, and `CORE_IMPORTS_OK` is printed.
