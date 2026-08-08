# Direct Fund-Flow Backfill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `stock_lab.jobs.fund_flow_backfill` the canonical live fund-flow backfill using EastMoney's direct daily-kline endpoint, with the task module retained as a thin compatibility CLI.

**Architecture:** The official job will enumerate distinct board metadata from MySQL snapshots and records, query `push2his.eastmoney.com` using each persisted board code, parse `f51`/`f52`, and write canonical records newest-to-oldest. Default composition creates MySQL and Redis repositories; MySQL snapshot existence is checked before Redis fallback, and Redis is updated only after a successful MySQL write. The injected AkShare source remains available for tests and explicit fallback.

**Tech Stack:** Python 3.12, pandas, requests, MySQL DB-API repository, Redis repository, pytest, uv.

## Global Constraints

- Use `https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get` with `secid=90.<board_code>` for board history.
- Send browser-like `User-Agent`, `Referer`, and `Accept` headers.
- Convert `f52` yuan to `net_inflow_100m` by dividing by `100_000_000` exactly once.
- Enumerate distinct `board_code`, `board_name`, and `leader` per `flow_type` from `fund_flow_snapshots` joined to `fund_flow_records`.
- Backfill available historical dates newest-to-oldest within the previous 365 calendar days.
- Preserve injected AkShare adapter behavior and compatibility exports from `task.fund_flow_backfill`.
- Do not execute migration `003`.
- Prevent duplicate canonical writes through MySQL snapshot checks and repository idempotency.

---

### Task 1: Direct Source and Catalog Contract

**Files:**
- Modify: `src/stock_lab/jobs/fund_flow_backfill.py`
- Test: `tests/unit/jobs/test_fund_flow_backfill.py`

**Interfaces:**
- Produces `EastMoneyFundFlowSource(mysql_repository, session=None)`, `list_boards(flow_type)`, `board_history(board)`, and pure response parsing helpers.
- Keeps `ConfiguredFundFlowDailySource` and its `fetch` contract for injected callers.

- [ ] Write failing tests for the catalog SQL, direct endpoint URL/params/headers, `f51`/`f52` parsing, yuan conversion, and malformed response errors.
- [ ] Run the focused tests and confirm they fail because the official source and parser are absent.
- [ ] Implement the source with lazy requests import/session injection, MySQL catalog query, strict response validation, and normalized records.
- [ ] Run the focused source tests and confirm they pass.

### Task 2: Canonical Orchestration and Re-Exports

**Files:**
- Modify: `src/stock_lab/jobs/fund_flow_backfill.py`
- Modify: `task/fund_flow_backfill.py`
- Test: `tests/test_fund_flow_backfill.py`
- Test: `tests/unit/jobs/test_fund_flow_backfill.py`

**Interfaces:**
- Produces `backfill_fund_flow(trading_dates=None, source=None, now=None, days=365, ...) -> dict` in the official module.
- Task module re-exports public classes/functions and provides `main(argv=None)` only.

- [ ] Add failing tests for newest-to-oldest dates, 365-day bounds, MySQL-first skip, Redis fallback, no duplicate writes, AkShare injection, and official default repository composition.
- [ ] Run focused tests and confirm the orchestration assertions fail.
- [ ] Implement the coordinator and writer composition, preserving failure reporting and writing Redis only after MySQL succeeds.
- [ ] Replace duplicated task implementation with imports/re-exports and a thin CLI.
- [ ] Run both focused test files and confirm all pass.

### Task 3: Verification and Commit

**Files:**
- Review: changed backend/tests/docs only; do not touch migration `003`.

- [ ] Run focused tests.
- [ ] Run the full backend test suite.
- [ ] Run `python -m compileall` for backend packages and task modules.
- [ ] Run frontend tests and build from `front/package.json`.
- [ ] Run `git diff --check`, inspect status and diff, and verify no unrelated dirty files are staged.
- [ ] Commit the intended changes with a concise fund-flow backfill message.
