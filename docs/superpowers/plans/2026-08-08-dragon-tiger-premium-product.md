# Dragon Tiger Premium Product Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users trigger the complete龙虎榜 data refresh and游资溢价 analysis from the Vue page through an asynchronous API job, then remove the old Chinese wrappers.

**Architecture:** A one-shot `DragonTigerCollectionJobManager` runs the four collection/analysis stages in a bounded background executor. Redis stores job state and the active-job lock; FastAPI exposes create/status endpoints; Vue polls status and renders the final result. The analytics function remains pure over canonical repositories.

**Tech Stack:** Python 3.12, FastAPI, Redis, MySQL repositories, `concurrent.futures`, Vue 3, Node test runner, pytest.

## Global Constraints

- Page requests return HTTP 202 and never wait for external collection pages.
- Duplicate active collection requests return HTTP 409.
- Failed stages store non-secret errors and stop later stages.
- Canonical source tables are `dragon_tiger`, `broker_listing_history`, `brokers`, `broker_top_stats`, and `daily_quotes`.
- Analysis results are returned in the job status response and are not persisted in a new result table.
- The old `游资溢价分析/` directory is removed only after new entrypoints and tests pass.

---

### Task 1: Date-Range Collection And Job Manager

**Files:**
- Create: `src/stock_lab/modules/dragon_tiger/jobs.py`
- Modify: `src/stock_lab/modules/dragon_tiger/repository.py`
- Modify: `src/stock_lab/modules/dragon_tiger/runtime.py`
- Test: `tests/unit/modules/dragon_tiger/test_jobs.py`
- Test: `tests/unit/modules/dragon_tiger/test_repository.py`

**Interfaces:**
- Produces `DragonTigerCollectionJobManager.start(start_date: int, latest_date: int) -> dict`.
- Produces `DragonTigerCollectionJobManager.get(job_id: str) -> dict | None`.
- Job status shape: `jobId`, `status`, `stage`, `startDate`, `latestDate`, `selectedCount`, `selectedCodes`, `sourceTables`, `error`.

- [ ] **Step 1: Write failing tests**

  Test date-bounded `trading_dates(start_date, end_date)`, Redis active-lock rejection, stage order `listings -> broker_directory -> broker_history -> analysis`, success state, and failed-stage state.

- [ ] **Step 2: Run RED**

  Run `uv run pytest --import-mode=importlib tests/unit/modules/dragon_tiger/test_jobs.py tests/unit/modules/dragon_tiger/test_repository.py -q` and confirm missing job manager/date-range behavior.

- [ ] **Step 3: Implement the manager**

  Use a single-worker `ThreadPoolExecutor`. Store JSON status under `stock_lab:dragon_tiger:job:{job_id}` and acquire `stock_lab:dragon_tiger:active` with an expiry. Update status before each stage; release the lock in `finally`; serialize all errors without credentials or external response bodies.

- [ ] **Step 4: Verify GREEN**

  Run the focused job/repository tests.

- [ ] **Step 5: Commit**

  Commit message: `增加龙虎榜异步采集任务管理`.

### Task 2: FastAPI Collection And Analysis Routes

**Files:**
- Create: `src/stock_lab/modules/dragon_tiger/api.py`
- Modify: `src/stock_lab/api/routes.py`
- Modify: `src/stock_lab/modules/dragon_tiger/__init__.py`
- Test: `tests/unit/modules/dragon_tiger/test_api.py`

**Interfaces:**
- Produces `POST /api/v1/dragon-tiger/collection-jobs` with `{startDate, latestDate}` and HTTP 202.
- Produces `GET /api/v1/dragon-tiger/collection-jobs/{job_id}`.
- Produces `GET /api/v1/dragon-tiger/premium?start_date=&latest_date=` for read-only analysis.

- [ ] **Step 1: Write failing API tests**

  Test valid 202 creation, invalid date 422, duplicate 409, status lookup, empty analysis response, and database failure mapped to 500 without raw exception details.

- [ ] **Step 2: Run RED**

  Run the focused API tests and confirm routes are absent.

- [ ] **Step 3: Implement route registration**

  Register the module from `src/stock_lab/api/routes.py`. Inject database/Redis clients once per route registration, construct repositories and job manager, and return the exact response contract from the design spec.

- [ ] **Step 4: Verify GREEN**

  Run focused API tests and existing application route tests.

- [ ] **Step 5: Commit**

  Commit message: `增加龙虎榜采集与溢价分析接口`.

### Task 3: Vue Product Page

**Files:**
- Create: `front/src/modules/dragon-tiger/api.js`
- Create: `front/src/views/DragonTigerPremium.vue`
- Modify: `front/src/App.vue`
- Modify: `front/src/components/AppHeader.vue`
- Modify: `tests/test_cutover_contracts.py`
- Test: `front/src/modules/dragon-tiger/api.test.js`

**Interfaces:**
- `createDragonTigerCollectionJob(startDate, latestDate)` returns `{jobId}`.
- `getDragonTigerCollectionJob(jobId)` returns the status shape from Task 1.
- `analyzeDragonTigerPremium(startDate, latestDate)` returns the analysis response.

- [ ] **Step 1: Write failing frontend API tests**

  Assert URL/query construction for all three API calls and JSON parsing.

- [ ] **Step 2: Run RED**

  Run `npm test --prefix front` and confirm the module/page is absent.

- [ ] **Step 3: Implement page**

  Add date inputs, a single `采集并分析` action, stage/status text, loading/error/empty states, selected code table, count, date range, and source-table note. Poll status every 1 second until `succeeded` or `failed`; stop polling on unmount. Use the existing tab pattern and no new frontend dependency.

- [ ] **Step 4: Register navigation**

  Add `DragonTigerPremium` import/dispatch and a `龙虎榜溢价` header button.

- [ ] **Step 5: Verify GREEN**

  Run `npm test --prefix front` and `npm run build --prefix front`.

- [ ] **Step 6: Commit**

  Commit message: `增加龙虎榜溢价分析页面`.

### Task 4: Product Documentation And Legacy Removal

**Files:**
- Create: `docs/products/dragon-tiger-premium-analysis.md`
- Delete: `游资溢价分析/溢价分析.py`
- Delete: `游资溢价分析/采集/龙虎榜数据采集.py`
- Delete: `游资溢价分析/采集/营业部数据采集.py`
- Delete: `游资溢价分析/采集/游资数据采集.py`
- Delete: `游资溢价分析/__init__.py`
- Delete: `游资溢价分析/采集/__init__.py`
- Delete: `tests/unit/modules/dragon_tiger/test_compatibility.py`
- Modify: `tests/test_cutover_contracts.py`
- Modify: `README.md`
- Modify: `docs/database-migrations.md`
- Modify: `docs/development.md`

**Interfaces:**
- Product documentation states old triggers, new page/API trigger, four collection stages, canonical data tables, result visibility, empty-data behavior, and troubleshooting.

- [ ] **Step 1: Write failing removal/documentation contracts**

  Assert all old files are absent, no active code references `游资溢价分析`, README contains the new page/API path, and the product doc contains the old/new trigger and five canonical table names.

- [ ] **Step 2: Run RED**

  Run the focused contracts and confirm legacy files/references remain.

- [ ] **Step 3: Write the product guide and update operator docs**

  Explain that the old script used hardcoded `20260404`/`20260803` dates and only returned a Python list; the new page creates an async job, refreshes data, and displays selected stock codes. Include SQL examples for inspecting the five source tables.

- [ ] **Step 4: Delete old wrappers and compatibility tests**

  Remove only the six listed wrapper/package files and their dedicated compatibility test. Keep the registered `strategy/龙虎榜_明日遴选.py` until the research-strategy migration is separately approved.

- [ ] **Step 5: Verify GREEN**

  Run the focused contracts and search active code/docs for stale executable references.

- [ ] **Step 6: Commit**

  Commit message: `退役游资溢价分析旧入口并补充产品说明`.

### Task 5: Full Verification And Main Integration

**Files:**
- All files from Tasks 1-4.

- [ ] **Step 1: Run complete tests**

  Run `uv run pytest --import-mode=importlib -q`, `npm test --prefix front`, `npm run build --prefix front`, and `git diff --check`.

- [ ] **Step 2: Run a live local smoke test**

  With local MySQL/Redis from `.env`, create a test job against an empty/fixture repository or a controlled date range, verify status transitions and confirm no secrets are logged.

- [ ] **Step 3: Inspect final status**

  Confirm no deleted legacy files are referenced, no unrelated files are staged, and the product documentation path is tracked.
