# Fund Flow Module Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move fund-flow Redis storage, REST/SSE contracts, worker ownership, and Vue data access into English official modules.

**Architecture:** `stock_lab.modules.fund_flow` owns English contracts, Redis repository, service, collector adapter, and `/api/v1/fund-flow` routes. Legacy browser parsing remains isolated behind an adapter until its large collector is split. Frontend requests and SSE move to `front/src/modules/fund-flow`; visible Chinese labels remain unchanged.

**Tech Stack:** Python 3.12, FastAPI, Redis, pytest, Vue 3, ECharts, Node test runner, Vite.

## Global Constraints

- New identifiers, Redis keys, REST fields, and SSE fields use English.
- Legacy Redis data is read once through an explicit adapter; all new writes use `fund_flow:v1:*` keys.
- Unknown Chinese API keys fail contract validation instead of leaking through V1.
- Browser collection behavior and sampling cadence remain unchanged.
- Old `/api/zijin/*` routes are removed after the frontend and worker use V1.

---

### Task 1: Contracts and Redis repository

**Files:**
- Create: `src/stock_lab/modules/fund_flow/__init__.py`
- Create: `src/stock_lab/modules/fund_flow/contracts.py`
- Create: `src/stock_lab/modules/fund_flow/repository.py`
- Test: `tests/unit/modules/fund_flow/test_contracts.py`
- Test: `tests/unit/modules/fund_flow/test_repository.py`

**Interfaces:**
- `translate_legacy_fund_flow(value)` recursively maps snapshot, board, leader, date, time, amount, and flow-type keys.
- `FundFlowRepository` uses `fund_flow:v1:{flow_type}:dates`, `history:{date}`, and `stream` channels with injected Redis.

- [ ] Write failing recursive contract and fake-Redis repository tests.
- [ ] Implement explicit English key translation and V1 Redis key builders.
- [ ] Verify history ordering, date indexing, publish payloads, and no non-ASCII V1 keys.
- [ ] Commit with `建立资金流向英文存储契约`.

### Task 2: Service, routes, and collector adapter

**Files:**
- Create: `src/stock_lab/modules/fund_flow/service.py`
- Create: `src/stock_lab/modules/fund_flow/api.py`
- Create: `src/stock_lab/modules/fund_flow/collector.py`
- Modify: `src/stock_lab/api/routes.py`
- Modify: `src/stock_lab/jobs/realtime_monitor.py`
- Test: `tests/api/test_fund_flow_v1.py`
- Test: `tests/unit/modules/fund_flow/test_collector.py`

**Interfaces:**
- Routes: `/api/v1/fund-flow/{flow_type}/dates`, `/history/{date}`, and `/stream`.
- `run_fund_flow_monitor(stop_event)` delegates collection through the official adapter and writes V1 snapshots.

- [ ] Write failing API and collector tests with fake service/legacy collector.
- [ ] Implement English service and SSE generator.
- [ ] Register V1 routes and switch worker ownership.
- [ ] Stop registering `/api/zijin/*` once contract tests pass.
- [ ] Commit with `迁移资金流向后端模块`.

### Task 3: Frontend module and view migration

**Files:**
- Create: `front/src/modules/fund-flow/api.js`
- Create: `front/src/modules/fund-flow/normalizers.js`
- Create: `front/src/modules/fund-flow/normalizers.test.js`
- Modify: `front/src/views/FundFlow.vue`
- Modify: `front/package.json`

**Interfaces:**
- `fetchFundFlowDates(flowType)`, `fetchFundFlowHistory(flowType, date)`, and `openFundFlowStream()` use V1.
- View model fields use camelCase; Chinese remains only in displayed labels and source values.

- [ ] Write failing normalizer tests for snapshots, boards, leaders, null amounts, and sparse chart data.
- [ ] Implement V1 API/SSE client and camel-case normalizer.
- [ ] Convert the view's member fields and remove direct legacy URLs.
- [ ] Run Node tests and Vite build.
- [ ] Commit with `迁移资金流向前端模块`.

### Task 4: Verification and documentation

**Files:**
- Modify: `README.md`
- Modify: `docs/migration.md`

- [ ] Run full Python tests, compileall, frontend tests, and Vite build.
- [ ] Confirm official Python/JS modules contain no Chinese identifiers.
- [ ] Document V1 routes, Redis key migration, and remaining strategy-pick dependency.
- [ ] Commit with `完成资金流向模块迁移`.
