# 项目模块化基础设施与启动 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立 `src/stock_lab` 正式包，迁移配置、基础设施和 FastAPI 启动边界，并保持旧入口在第一阶段可调用。

**Architecture:** 新包负责正式实现，旧的 `config.py`、`app.py` 和基础设施导入路径作为薄兼容层。配置对象只负责解析环境变量；MySQL 和 Redis 客户端由 infrastructure 工厂按需创建，业务代码通过依赖注入使用它们。FastAPI 应用由工厂创建，后台 worker 由生命周期统一启动和停止。

**Tech Stack:** Python 3.12、FastAPI、Pydantic 2、python-dotenv、SQLAlchemy、mysql-connector-python、Redis、pytest、Vue 3、Vite。

## Global Constraints

- 所有工作只发生在 `refactor/modularize-project` 分支。
- 第一阶段不迁移业务表数据；新版代码和新增契约必须使用英文命名。
- 兼容模块只转发，不复制业务实现。
- 正式 Python 包的目录、文件、类、函数、方法和变量使用英文命名；中文只允许出现在界面文案、日志、领域展示值和兼容层。
- 后续模块必须通过版本化 SQL 将数据库表列和 API JSON 字段迁移为英文，包含迁移前后校验与回滚步骤。
- 不在 Web 进程默认启动通达信工具。
- MySQL、Redis、浏览器和外部数据源不得在模块导入时执行不可控的网络连接。
- 后台 worker 必须有单实例保护，关闭时可停止；异常必须记录。
- 每项代码变更先写失败测试，再实现最小行为，再运行目标测试。
- 本阶段不重写策略研究脚本和情绪业务逻辑。

---

### Task 1: 建立包结构与配置对象

**Files:**
- Create: `src/stock_lab/__init__.py`
- Create: `src/stock_lab/config/__init__.py`
- Create: `src/stock_lab/config/settings.py`
- Create: `src/stock_lab/config/defaults.py`
- Modify: `config.py`
- Modify: `pyproject.toml`
- Create: `tests/unit/config/test_settings.py`

**Interfaces:**
- Produces `stock_lab.config.settings.Settings` with `from_env()`, `project_root`, MySQL fields, token list, optional integration fields, and existing monitoring defaults.
- Produces `stock_lab.config.get_settings()` returning a cached `Settings` instance.
- Legacy `config.py` continues exporting `mysql_localhost_host`, `mysql_localhost_port`, `ts_token`, `tdx_root` and existing Chinese configuration names.
- New settings properties and default keys use English names; Chinese configuration names exist only in the root compatibility module.

- [ ] **Step 1: Write failing tests for typed settings and legacy exports**

```python
def configure_required_env(monkeypatch):
    values = {
        "MYSQL_HOST": "localhost",
        "MYSQL_PORT": "3306",
        "MYSQL_USER": "root",
        "MYSQL_PASSWORD": "root",
        "MYSQL_DATABASE": "stock_trading_lab",
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)


def test_settings_from_env_parses_required_and_optional_values(monkeypatch):
    monkeypatch.setenv("MYSQL_HOST", "db.internal")
    monkeypatch.setenv("MYSQL_PORT", "4406")
    monkeypatch.setenv("MYSQL_USER", "stock_user")
    monkeypatch.setenv("MYSQL_PASSWORD", "secret")
    monkeypatch.setenv("MYSQL_DATABASE", "stocks")
    monkeypatch.setenv("TUSHARE_TOKENS", " token-a, token-b ")

    settings = Settings.from_env()

    assert settings.mysql.port == 4406
    assert settings.tushare_tokens == ["token-a", "token-b"]


def test_legacy_config_exports_new_settings(monkeypatch):
    configure_required_env(monkeypatch)
    import config

    reloaded = importlib.reload(config)
    assert reloaded.mysql_localhost_host == "localhost"
```

- [ ] **Step 2: Run the focused tests and verify they fail because the new package is absent**

Run: `python -m pytest tests/unit/config/test_settings.py -q`

Expected: FAIL with an import error for `stock_lab.config.settings`.

- [ ] **Step 3: Implement `Settings` using small nested dataclasses**

Use `Settings.from_env()` to load `.env` once, parse required MySQL values, split `TUSHARE_TOKENS`, and preserve optional empty values. Put non-secret business defaults in `defaults.py`; do not duplicate the long exclusion list in the compatibility module.

- [ ] **Step 4: Convert `config.py` into a compatibility projection**

Import the new settings object and assign legacy names from it. Preserve the current import-time error messages for missing MySQL environment variables so existing tests remain meaningful.

- [ ] **Step 5: Add package discovery configuration and run tests**

Configure the project so `src/stock_lab` is importable in development, then run:

```powershell
python -m pytest tests/unit/config/test_settings.py tests/test_config.py -q
```

Expected: all focused configuration tests pass.

- [ ] **Step 6: Commit the configuration boundary**

```powershell
git add src/stock_lab/config config.py pyproject.toml tests/unit/config/test_settings.py
git commit -m "重构配置边界"
```

### Task 2: 抽离 Redis 与 MySQL 基础设施

**Files:**
- Create: `src/stock_lab/shared/errors.py`
- Create: `src/stock_lab/infrastructure/__init__.py`
- Create: `src/stock_lab/infrastructure/cache/__init__.py`
- Create: `src/stock_lab/infrastructure/cache/redis_client.py`
- Create: `src/stock_lab/infrastructure/database/__init__.py`
- Create: `src/stock_lab/infrastructure/database/mysql.py`
- Modify: `utils/redis_base.py`
- Modify: `utils/mysql_base.py`
- Modify: `utils/db.py`
- Create: `tests/unit/infrastructure/test_clients.py`

**Interfaces:**
- Produces `create_redis_client(settings)`, returning a Redis client without connecting during module import.
- Produces `MysqlResources` with `engine`, `pool`, and `execute()` behavior equivalent to current `utils.db.mysql_localhost`.
- Legacy `utils.db.redis_con_localhost`, `mysql_localhost_pool`, and `engine` remain available through lazy compatibility access.

- [ ] **Step 1: Write tests proving imports do not connect to external services**

```python
def fake_settings():
    return SimpleNamespace(
        redis=SimpleNamespace(host="127.0.0.1", port=6379, database=0),
        mysql=SimpleNamespace(
            host="localhost",
            port=3306,
            user="stock_user",
            password="secret",
            database="stocks",
        ),
    )


def test_redis_factory_does_not_ping_on_creation(monkeypatch):
    client = create_redis_client(fake_settings())
    assert client.connection_pool.connection_kwargs["host"] == "127.0.0.1"


def test_mysql_resources_builds_connection_strings_without_connecting(monkeypatch):
    resources = MysqlResources.from_settings(fake_settings())
    assert resources.url.startswith("mysql+pymysql://stock_user:")
```

- [ ] **Step 2: Run focused tests and verify the new factories are missing**

Run: `python -m pytest tests/unit/infrastructure/test_clients.py -q`

Expected: FAIL with an import error for the new infrastructure modules.

- [ ] **Step 3: Implement Redis and MySQL factories**

Move connection construction and retry constants into the new modules. Keep retry behavior finite and preserve the existing SQL execution contract. Do not instantiate a connection pool at import time.

- [ ] **Step 4: Update legacy utility modules to delegate**

Expose compatibility accessors that construct resources on first use. Keep existing callers working while removing direct configuration imports from the new infrastructure code.

- [ ] **Step 5: Run infrastructure and existing tests**

Run: `python -m pytest tests/unit/infrastructure/test_clients.py tests/test_config.py tests/test_driver_chrome.py -q`

Expected: all tests pass without requiring a live MySQL or Redis service.

- [ ] **Step 6: Commit the infrastructure boundary**

```powershell
git add src/stock_lab/infrastructure src/stock_lab/shared/errors.py utils/redis_base.py utils/mysql_base.py utils/db.py tests/unit/infrastructure/test_clients.py
git commit -m "抽离数据库和缓存基础设施"
```

### Task 3: 建立 FastAPI 应用工厂与生命周期

**Files:**
- Create: `src/stock_lab/bootstrap/__init__.py`
- Create: `src/stock_lab/bootstrap/application.py`
- Create: `src/stock_lab/bootstrap/lifecycle.py`
- Create: `src/stock_lab/bootstrap/workers.py`
- Create: `src/stock_lab/api/__init__.py`
- Create: `src/stock_lab/api/routes.py`
- Modify: `app.py`
- Create: `tests/unit/bootstrap/test_application.py`

**Interfaces:**
- Produces `create_app(settings=None, worker_manager=None) -> FastAPI`.
- Produces `WorkerManager.register(name, target)`, `start_all()`, and `stop_all()` with duplicate-start protection.
- Legacy `app.app` remains the application object used by `uvicorn app:app`.

- [ ] **Step 1: Write failing tests for app creation and worker lifecycle**

```python
class FakeWorkerManager:
    def register(self, _name, _target):
        pass


def test_create_app_registers_routes_once():
    app = create_app(worker_manager=FakeWorkerManager())
    paths = [route.path for route in app.routes]
    assert paths.count("/api/emotion/current") == 1


def test_worker_manager_does_not_start_a_worker_twice():
    manager = WorkerManager()
    target = Mock()
    manager.register("sample", target)
    manager.start_all()
    manager.start_all()
    assert target.call_count == 1
```

- [ ] **Step 2: Run focused tests and verify failure**

Run: `python -m pytest tests/unit/bootstrap/test_application.py -q`

Expected: FAIL because `create_app` and `WorkerManager` do not exist.

- [ ] **Step 3: Implement the worker manager and lifespan**

Move route registration into one function. Register current monitoring routes exactly once. The lifespan starts registered workers on startup and calls `stop_all()` on shutdown. Use daemon threads only for the existing long-running workers.

- [ ] **Step 4: Replace root `app.py` with a compatibility entry point**

Keep the `app` variable and `if __name__ == "__main__"` behavior, but delegate application creation and worker setup to `stock_lab.bootstrap`. Remove direct route registration and task imports from the root entry point.

- [ ] **Step 5: Verify import, API route count, and existing tests**

Run:

```powershell
python -m pytest tests/unit/bootstrap/test_application.py tests/test_optional_task_modules.py tests/test_config.py -q
python -c "import app; print(app.app.title)"
```

Expected: focused tests pass and the import command prints the FastAPI title without starting a server.

- [ ] **Step 6: Commit the application boundary**

```powershell
git add src/stock_lab/bootstrap src/stock_lab/api app.py tests/unit/bootstrap/test_application.py
git commit -m "建立应用工厂和生命周期"
```

### Task 4: Separate frontend process startup and document phase one

**Files:**
- Create: `src/stock_lab/bootstrap/frontend.py`
- Modify: `front_run.py`
- Modify: `启动项目.ps1`
- Modify: `README.md`
- Modify: `环境安装.md`
- Create: `docs/architecture.md`
- Create: `docs/development.md`
- Create: `docs/migration.md`
- Create: `docs/database-migrations.md`
- Create: `tests/unit/bootstrap/test_frontend.py`

**Interfaces:**
- Produces `FrontendProcess.start(project_root, port=8990)` and `stop()` with an explicit process handle.
- Legacy `front_run.run()` delegates to `FrontendProcess.start()` and keeps the current working-directory behavior.

- [ ] **Step 1: Write failing tests for project-root resolution and missing npm handling**

```python
def test_frontend_command_uses_front_directory(tmp_path):
    front = tmp_path / "front"
    front.mkdir()
    process = FrontendProcess.build_command(tmp_path)
    assert process.cwd == front
    assert process.args[-2:] == ["run", "dev"]


def test_missing_npm_raises_clear_error(monkeypatch, tmp_path):
    monkeypatch.setattr(shutil, "which", lambda *_args: None)
    with pytest.raises(RuntimeError, match="Node.js|npm"):
        FrontendProcess.build_command(tmp_path)
```

- [ ] **Step 2: Run the focused tests and verify failure**

Run: `python -m pytest tests/unit/bootstrap/test_frontend.py -q`

Expected: FAIL because `FrontendProcess` does not exist.

- [ ] **Step 3: Implement frontend process ownership**

Move Windows npm resolution and subprocess creation into the new class. Use the repository root rather than the caller's current directory. Keep stdout forwarding and clear errors, but do not call `exit()` from library code.

- [ ] **Step 4: Update the PowerShell launcher and legacy wrapper**

Make `启动项目.ps1` invoke the documented Python application entry point. Make `front_run.run()` delegate to the new process owner without changing existing user-facing commands.

- [ ] **Step 5: Write the architecture, development, and migration documentation**

Document the dependency direction, new package layout, English naming rules, local setup, test commands, old-to-new module mapping, database migration protocol, branch workflow, and the fact that the current phase does not move business algorithms or business tables.

- [ ] **Step 6: Run phase-one verification**

Run:

```powershell
python -m pytest -q
python -m compileall -q src app.py config.py front_run.py
Push-Location front
npm install
npm run build
Pop-Location
```

Expected: Python tests pass, compilation exits successfully, and the Vue production build completes. If dependency installation is unavailable, report the exact missing command and do not claim the build passed.

- [ ] **Step 7: Commit phase-one foundation**

```powershell
git add src front_run.py 启动项目.ps1 README.md 环境安装.md docs/architecture.md docs/development.md docs/migration.md docs/database-migrations.md tests
git commit -m "完成模块化基础启动改造"
```

### Task 5: Rebuild the database schema with English contracts

**Files:**
- Create: `db/migrations/001_create_english_schema.sql`
- Create: `db/migrations/002_migrate_legacy_data.sql`
- Create: `db/migrations/003_drop_legacy_schema.sql`
- Create: `db/migrations/README.md`
- Create: `init/stock_trading_lab_v2.sql`
- Create: `tests/integration/database/test_schema_migration.py`
- Modify: `docs/database-migrations.md`
- Modify: `pyproject.toml`

**Interfaces:**
- Produces an English schema version tracked by `schema_migrations(version, applied_at)`.
- Produces explicit table and column mapping data used by the migration verification tests.
- The application uses only the new English table and column names after each business module is migrated.
- Legacy tables are retained during the staged rollout and dropped only by the explicit `003_drop_legacy_schema.sql` script after all module cutovers pass.

**Table mapping:**

| Legacy table | New table |
| --- | --- |
| `akshare_sh000001` | `index_daily` |
| `t_指数情绪周期_市场宽度` | `index_market_breadth` |
| `t_指数情绪周期_每日分析` | `index_emotion_daily` |
| `t_热门板块情绪_每日分析` | `hot_board_emotion_daily` |
| `stock_basic` | `stock_basic` |
| `stock_daily` | `stock_daily` |
| `stock_kdj` | `stock_kdj` |
| `t_stock_5_min_k` | `stock_5min` |
| `t_韭研公社异动解析` | `jiuyan_actions` |
| `t_龙虎榜` | `dragon_tiger` |
| `t_龙虎榜_营业部_上榜历史数据` | `broker_listing_history` |
| `t_龙虎榜_营业部_上榜次数最多` | `broker_top_stats` |
| `t_龙虎榜_营业部_全部` | `brokers` |
| `t_同花顺板块列表` | `ths_boards` |
| `t_同花顺板块成分股` | `ths_board_constituents` |
| `t_同花顺股票板块概念对应关系` | `ths_stock_relations` |

The rebuild must also normalize existing Chinese columns. Examples that must be applied consistently include `日期 -> trade_date`, `板块 -> board_name`, `股票代码 -> stock_code`, `股票名称 -> stock_name`, `创建时间 -> created_at`, `更新时间 -> updated_at`, `综合状态 -> overall_status`, and all dragon-tiger buy/sell columns to `buy_1_broker_id`, `buy_1_broker_name`, `buy_1_buy_amount`, `buy_1_sell_amount`, `buy_1_net_amount` and their `sell_1_*` equivalents.

- [ ] **Step 1: Write a schema inventory test before writing SQL**

```python
def test_schema_mapping_contains_all_legacy_tables():
    mapping = load_schema_mapping()
    assert mapping["t_指数情绪周期_每日分析"] == "index_emotion_daily"
    assert mapping["t_同花顺板块成分股"] == "ths_board_constituents"
    assert len(mapping) == 16


def test_new_schema_contains_no_non_ascii_identifiers():
    for identifier in all_new_schema_identifiers():
        assert identifier.isascii()
```

- [ ] **Step 2: Run the inventory tests and verify they fail**

Run: `python -m pytest tests/integration/database/test_schema_migration.py -q`

Expected: FAIL because the English schema mapping and migration metadata do not exist.

- [ ] **Step 3: Create the English schema from the existing definitions**

Write `001_create_english_schema.sql` with `CREATE TABLE` statements, primary keys, unique keys, indexes, JSON columns, comments, and explicit numeric types. Do not use `CREATE TABLE ... LIKE` because that would preserve bad legacy names and types. Add `schema_migrations` and a transaction-safe version record.

- [ ] **Step 4: Add data-copy SQL with source-to-target column lists**

Write `002_migrate_legacy_data.sql` using explicit `INSERT INTO new_table (english_columns) SELECT chinese_columns FROM legacy_table` statements. Every table must have a row-count check query and duplicate-key policy. Do not use `SELECT *`.

- [ ] **Step 5: Add validation and rollback procedures**

`db/migrations/README.md` must require a database backup, list execution order, compare row counts and key aggregates, and explain that rollback restores the backup or renames the new tables back only before application cutover. `003_drop_legacy_schema.sql` must be separate and must not run during initial migration.

- [ ] **Step 6: Produce a clean initialization dump**

Generate `init/stock_trading_lab_v2.sql` from the English schema so a new environment never creates Chinese identifiers. The dump must include all 16 mapped tables and omit legacy tables.

- [ ] **Step 7: Add migration tests that run without a live database**

Parse the SQL text and assert every mapped table is created, all identifiers are ASCII, every legacy table has a copy statement, no migration uses `SELECT *`, and the drop script is not referenced by the initial setup script.

- [ ] **Step 8: Commit the schema rebuild artifacts**

```powershell
git add db init/stock_trading_lab_v2.sql docs/database-migrations.md pyproject.toml tests/integration/database/test_schema_migration.py
git commit -m "重建英文数据库表结构"
```

## Spec Coverage Review

- Architecture and dependency direction: Tasks 1-3.
- Compatibility wrappers: Tasks 1-4.
- Lazy infrastructure initialization: Task 2.
- Single worker startup and shutdown: Task 3.
- Frontend module/process boundary: Task 4.
- Error and runtime policies: Tasks 2-3.
- Test layering and verification commands: Tasks 1-4.
- README, setup, architecture, development, and migration documentation: Task 4.
- Full table and column rebuild with verification and rollback protocol: Task 5.
- English code naming starts in Tasks 1-4; API and database field migration is enforced in each later business-module plan.
- Research and business algorithm migration is intentionally deferred to the next independently testable plans, as required by the non-goals.
