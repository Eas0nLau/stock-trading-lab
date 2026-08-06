# Strategy Pick Module Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move strategy-pick V1 storage, contracts, REST/SSE access, worker ownership, and frontend consumption into the official English module while retaining only targeted legacy compatibility.

**Architecture:** `stock_lab.modules.strategy_pick` owns English camelCase contracts, ASCII Redis V1 keys, repository, service, API routes, and a collector adapter around the legacy browser/parser implementation. The adapter double-writes legacy keys only for active direct consumers during migration. The frontend module owns V1 requests, SSE handling, and normalization; views retain Chinese display labels and domain values.

**Tech Stack:** Python 3.12, FastAPI, Redis client interfaces, pytest, Vue 3, Node test runner, Vite.

## Global Constraints

- New Python identifiers, API fields, SSE fields, and Redis keys are English ASCII.
- Chinese strings remain allowed as UI labels, strategy names, stock values, source field labels, and explicit legacy adapter identifiers.
- Official repository writes use `strategy_pick:v1:*` keys; legacy writes happen only through an explicit adapter for active consumers.
- Do not execute browser collection or connect to real Redis during tests.
- Remove old `/api/strategy-pick/*` route registration after frontend migration.

---

### Task 1: Contracts and repository

**Files:**
- Modify: `src/stock_lab/modules/strategy_pick/contracts.py`
- Create: `src/stock_lab/modules/strategy_pick/repository.py`
- Create: `src/stock_lab/modules/strategy_pick/legacy_adapter.py`
- Test: `tests/unit/modules/strategy_pick/test_contracts.py`
- Test: `tests/unit/modules/strategy_pick/test_repository.py`

**Interfaces:**
- `translate_legacy_strategy_pick(value)` recursively maps the legacy snapshot, strategy, stock, event, and configuration keys to camelCase English keys.
- `StrategyPickRepository(redis, legacy_reader=None)` provides `strategies`, `save_strategies`, `latest`, `history`, `events`, `dates`, `save_snapshot`, `save_events`, `save_selected_state`, `publish_snapshot`, `stream_events`, and `stream_subscriber_count`.
- `LegacyStrategyPickReadAdapter` and `LegacyStrategyPickWriteAdapter` isolate old Redis keys and translate data at the boundary.

- [x] Write failing recursive contract, V1-key, legacy fallback, write, and subscriber cleanup tests.
- [x] Run the focused tests and confirm failures are caused by missing behavior.
- [x] Implement minimal English translation, repository key builders, persistence, and in-process broker.
- [x] Run focused tests until green, then refactor only while green.

### Task 2: Service, REST/SSE API, and route ownership

**Files:**
- Create: `src/stock_lab/modules/strategy_pick/service.py`
- Modify: `src/stock_lab/modules/strategy_pick/api.py`
- Modify: `src/stock_lab/api/routes.py`
- Test: `tests/api/test_strategy_pick_v1.py`

**Interfaces:**
- Routes: `/api/v1/strategy-pick/strategies`, `/strategies/{id}`, `/latest`, `/history/{date}`, `/events/{date}`, `/dates`, `/refresh`, `/refresh-all`, and `/stream`.
- `StrategyPickService` validates strategy IDs, delegates CRUD/read behavior to the repository, and delegates refresh calls to an injected collector.

- [x] Write failing API tests for full CRUD/read/refresh/refresh-all, English payloads, SSE events, and absence of legacy paths.
- [x] Run the focused API tests and confirm expected failures.
- [x] Implement service/API registration with injected repository and collector dependencies.
- [x] Remove legacy route registration and run API/application route tests.

### Task 3: Collector adapter and worker migration

**Files:**
- Create: `src/stock_lab/modules/strategy_pick/collector.py`
- Modify: `src/stock_lab/jobs/realtime_monitor.py`
- Test: `tests/unit/modules/strategy_pick/test_collector.py`
- Test: `tests/unit/jobs/test_realtime_monitor.py`

**Interfaces:**
- `LegacyStrategyPickCollectorAdapter` delegates initialization and collection scheduling to `实时监控/策略选股.py` without moving browser parsing.
- `StrategyPickCollector` translates collector results, persists through the repository, publishes SSE events, and exposes `refresh(strategy_id)` and `refresh_all()`.
- `run_strategy_pick_monitor(stop_event=None, collector=None)` delegates to the official collector runner and remains injectable for tests.

- [x] Write failing adapter/worker tests using fake modules and stop events.
- [x] Run focused tests and confirm they fail before implementation.
- [x] Implement adapter delegation and official worker wiring.
- [x] Run focused tests and the existing worker manager tests.

### Task 4: Frontend API, normalizers, and views

**Files:**
- Create: `front/src/modules/strategy-pick/api.js`
- Create: `front/src/modules/strategy-pick/normalizers.js`
- Create: `front/src/modules/strategy-pick/normalizers.test.js`
- Modify: `front/src/views/StrategyPickMonitor.vue`
- Modify: `front/src/App.vue`

**Interfaces:**
- API helpers cover strategy CRUD, latest/history/events/dates, refresh, refresh-all, and `openStrategyPickStream()`.
- Normalizers expose camelCase view models while retaining Chinese display values and field labels.

- [x] Write failing normalizer tests for strategies, snapshots, stocks/events, sparse values, and SSE payloads.
- [x] Run Node tests and confirm the new tests fail for missing exports/behavior.
- [x] Implement API helpers and normalizers, then migrate both consumers and EventSource cleanup.
- [x] Run the full frontend test script and Vite build.

### Task 5: Documentation, full verification, review, and commit

**Files:**
- Modify: `README.md`
- Modify: `docs/architecture.md`
- Modify: `docs/migration.md`
- Modify: `docs/superpowers/plans/2026-08-06-strategy-pick-module-migration.md`

- [x] Update architecture, migration mapping, Redis key ownership, routes, compatibility consumers, and frontend module documentation.
- [x] Run `uv pytest`, `uv run python -m compileall -q src`, `npm --prefix front test`, and `npm --prefix front run build`.
- [x] Inspect diff/status, request code review, address critical/important findings, and rerun affected verification.
- [ ] Commit only intended migration files with a concise migration commit message.
