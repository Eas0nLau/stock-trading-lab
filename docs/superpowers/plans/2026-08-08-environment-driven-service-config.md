# Environment-Driven Service Configuration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace deployment-specific MySQL, Redis, backend, frontend, Docker, and Windows-service literals with validated root `.env` configuration.

**Architecture:** Extend the existing immutable `Settings` object as the Python configuration authority. Vite loads the same root `.env`, Docker Compose substitutes the same variables, and the PowerShell launcher reads only service names from that file. External market-data provider URLs remain unchanged.

**Tech Stack:** Python 3.12, dataclasses, python-dotenv, FastAPI/Uvicorn, Vue 3, Vite 8, Docker Compose YAML, PowerShell 5.1, pytest, Node test runner.

## Global Constraints

- The root `.env` is the single operator-owned deployment configuration source.
- `.env` remains ignored and existing credentials/secrets must not be printed or committed.
- `.env.example` documents every supported deployment variable.
- External provider URLs are outside scope.
- No drive-letter path or backend/frontend port literal remains in active deployment code.
- Only intentionally edited files are staged; do not create a repository-wide EOL normalization commit.

---

### Task 1: Typed Python Service Settings

**Files:**
- Modify: `src/stock_lab/config/settings.py`
- Modify: `src/stock_lab/config/defaults.py`
- Modify: `tests/unit/config/test_settings.py`

**Interfaces:**
- Produces: `ServiceSettings(app_host: str, app_port: int, frontend_host: str, frontend_port: int, frontend_proxy_target: str, mysql_service_name: str, redis_service_name: str, redis_data_dir: str)`.
- Produces: `Settings.services: ServiceSettings`.

- [ ] **Step 1: Write failing settings tests**

  Add tests that set all service variables and assert exact typed values, then set `APP_PORT=0` and assert `RuntimeError("环境变量 APP_PORT 必须是正整数")`.

- [ ] **Step 2: Verify RED**

  Run: `uv run pytest --import-mode=importlib tests/unit/config/test_settings.py -q`

  Expected: failure because `Settings.services` does not exist.

- [ ] **Step 3: Implement minimal typed settings**

  Add defaults:

  ```python
  DEFAULT_APP_HOST = "0.0.0.0"
  DEFAULT_APP_PORT = 8527
  DEFAULT_FRONTEND_HOST = "0.0.0.0"
  DEFAULT_FRONTEND_PORT = 9527
  DEFAULT_FRONTEND_PROXY_TARGET = "http://127.0.0.1:8527"
  DEFAULT_MYSQL_SERVICE_NAME = "MySQL80"
  DEFAULT_REDIS_SERVICE_NAME = "Redis"
  DEFAULT_REDIS_DATA_DIR = "./data"
  ```

  Add `_optional_positive_int_env()` and build `ServiceSettings` from the corresponding variables.

- [ ] **Step 4: Verify GREEN**

  Run the focused settings suite and confirm all tests pass.

- [ ] **Step 5: Commit**

  Commit message: `集中服务地址环境变量配置`.

### Task 2: Python Entrypoints Consume Settings

**Files:**
- Modify: `app.py`
- Modify: `front_run.py`
- Modify: `src/stock_lab/bootstrap/frontend.py`
- Modify: `tests/unit/bootstrap/test_frontend.py`
- Modify: `tests/test_config.py`

**Interfaces:**
- Consumes: `Settings.services` from Task 1.
- Produces: `FrontendProcess.build_command(project_root, *, host, port)` and `FrontendProcess.start(project_root, *, host, port)`.

- [ ] **Step 1: Write failing command tests**

  Assert a configured host and port produce:

  ```python
  assert command.args[-4:] == ["--", "--host", "127.0.0.1", "--port", "8990"]
  ```

  Add a static contract that `app.py` contains no `host="0.0.0.0"` or `port=8527` literal.

- [ ] **Step 2: Verify RED**

  Run the focused frontend/config tests; expect the current default-argument API and Uvicorn literals to fail.

- [ ] **Step 3: Implement entrypoint consumption**

  `app.py` loads settings once and passes `settings.services.app_host/app_port` to Uvicorn. `front_run.run()` loads settings and passes `frontend_host/frontend_port`. `FrontendProcess` always appends explicit `--host` and `--port` arguments.

- [ ] **Step 4: Verify GREEN**

  Run the focused tests.

- [ ] **Step 5: Commit**

  Commit message: `使用环境变量启动前后端服务`.

### Task 3: Vite, Compose, PowerShell, And Env Contracts

**Files:**
- Modify: `front/vite.config.js`
- Modify: `front/src/views/FundFlow.vue`
- Modify: `init/docker/mysql/docker-compose.yml`
- Modify: `init/docker/redis/docker-compose.yml`
- Modify: `启动项目.ps1`
- Modify: `.env.example`
- Modify locally, do not stage: `.env`
- Create: `tests/test_service_configuration.py`

**Interfaces:**
- Consumes the variable names defined in Task 1.
- Produces deployment files with no hardcoded local addresses.

- [ ] **Step 1: Write failing static contracts**

  Assert:

  ```python
  assert "loadEnv" in vite_config
  assert "FRONTEND_PROXY_TARGET" in vite_config
  assert 'target: \'http://127.0.0.1:8527\'' not in vite_config
  assert "G:\\docker" not in redis_compose
  assert "${REDIS_PORT" in redis_compose
  assert "${MYSQL_PORT" in mysql_compose
  assert "MYSQL_SERVICE_NAME" in launcher
  assert "REDIS_SERVICE_NAME" in launcher
  ```

  Also assert `.env.example` contains every variable from the design spec and `FundFlow.vue` does not display port `8527`.

- [ ] **Step 2: Verify RED**

  Run: `uv run pytest --import-mode=importlib tests/test_service_configuration.py -q`

- [ ] **Step 3: Implement Vite and deployment files**

  Vite uses `loadEnv(mode, path.resolve(process.cwd(), '..'), '')`, validates `FRONTEND_PORT`, and reads `FRONTEND_HOST` plus `FRONTEND_PROXY_TARGET`.

  Compose uses:

  ```yaml
  ports:
    - "${REDIS_PORT:-6379}:6379"
  volumes:
    - "${REDIS_DATA_DIR:-./data}:/data"
  ```

  and MySQL uses `${MYSQL_PORT:-3306}` plus `${MYSQL_DATABASE:-stock_trading_lab}`.

  PowerShell parses `MYSQL_SERVICE_NAME` and `REDIS_SERVICE_NAME` from `.env` without echoing the file or any credentials.

- [ ] **Step 4: Update env files**

  Add all documented variables to `.env.example`. Add the local non-secret values to ignored `.env`, preserving existing MySQL credentials and API keys.

- [ ] **Step 5: Verify live local services**

  Use the application settings to call MySQL `SELECT 1` and Redis `PING`. Print only booleans/version metadata, never credentials.

- [ ] **Step 6: Verify GREEN**

  Run the focused contracts, `npm test`, and `npm run build`.

- [ ] **Step 7: Commit tracked files**

  Commit message: `移除部署服务硬编码地址`.

### Task 4: EOL Policy And Documentation

**Files:**
- Modify: `.gitattributes`
- Modify: `README.md`
- Modify: `docs/development.md`
- Modify: `环境安装.md`
- Test: `tests/test_service_configuration.py`

**Interfaces:**
- Produces: documented root `.env` startup contract and stable LF repository text policy.

- [ ] **Step 1: Extend failing contracts**

  Assert `.gitattributes` includes `* text=auto eol=lf` and docs name `APP_PORT`, `FRONTEND_PORT`, `MYSQL_SERVICE_NAME`, and `REDIS_SERVICE_NAME` instead of claiming fixed ports.

- [ ] **Step 2: Verify RED**

  Run the service configuration tests.

- [ ] **Step 3: Implement policy and docs**

  Add the text policy before existing LFS rules. Document startup through `.env` and note the detected local services `MySQL80` and `Redis` only as example values.

- [ ] **Step 4: Verify no mass normalization**

  Run `git diff --stat` and confirm only intentionally edited files are present.

- [ ] **Step 5: Commit**

  Commit message: `统一文本行尾与环境配置文档`.

### Task 5: Merge Final Legacy Cutover And Verify Main

**Files:**
- Merge commit from branch: `migration/final-legacy-cutover`

**Interfaces:**
- Consumes commits from Tasks 1-4 and cutover commit `d721ce1`.
- Produces final `main` with environment configuration and legacy database retirement code.

- [ ] **Step 1: Merge the cutover branch**

  Run: `git merge migration/final-legacy-cutover`

  Resolve only genuine conflicts; preserve all environment configuration commits already on `main`.

- [ ] **Step 2: Run full verification**

  Run:

  ```powershell
  uv run pytest --import-mode=importlib -q
  npm --prefix front test
  npm --prefix front run build
  git diff --check
  ```

- [ ] **Step 3: Recheck database cutover state**

  Verify zero legacy tables, one `003_drop_legacy_schema` version row, and 16 latest successful containment detail rows with zero missing/mismatch/lost counts.

- [ ] **Step 4: Clean the feature worktree**

  Remove `.worktrees/final-legacy-cutover`, prune worktrees, and delete `migration/final-legacy-cutover` only after merged verification passes.
