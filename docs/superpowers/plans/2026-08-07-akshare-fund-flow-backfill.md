# AkShare Fund-Flow Backfill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Backfill one calendar year of industry and concept board fund-flow history through installed AkShare APIs without fabricating data on source failures.

**Architecture:** Add a focused task module with a lazy injectable AkShare adapter, pure frame normalization, and a newest-to-oldest coordinator over the existing index-backed trading calendar. Reuse the existing Redis snapshot writer so API consumers receive the same record and key contract as live collection.

**Tech Stack:** Python 3.12, AkShare 1.17.54, pandas, Redis, pytest, uv.

## Global Constraints

- Use `stock_sector_fund_flow_rank` to enumerate both industry and concept board names.
- Use `stock_sector_fund_flow_hist` to fetch daily history per board.
- Normalize f62-like source amounts from yuan to canonical `net_inflow_100m` values in 100 million yuan.
- Walk trading dates newest to oldest within the previous 365 calendar days.
- Report failed dates and never write fabricated records.
- Tests must inject a fake AkShare module and fake retry/rate-delay functions; tests must not access the network.
- Do not execute migration `003`.
- Produce one final commit after full backend and frontend verification.

---

### Task 1: Adapter, Normalization, and Aggregation

**Files:**
- Create: `task/fund_flow_backfill.py`
- Test: `tests/test_fund_flow_backfill.py`

**Interfaces:**
- Produces: `AkShareFundFlowSource(akshare_module=None, sleep=time.sleep)` with lazy module loading.
- Produces: `normalize_history_rows(frame, board, flow_type) -> list[dict]`.
- Produces: `collect_fund_flow_records(source, flow_type) -> dict[int, list[dict]]`.

- [ ] **Step 1: Write failing tests for lazy injection, board enumeration, source-column aliases, date normalization, metadata, and yuan-to-100-million conversion.**
- [ ] **Step 2: Run `uv run --frozen pytest tests/test_fund_flow_backfill.py -q` and verify the new module is missing.**
- [ ] **Step 3: Implement the adapter and pure normalization with explicit required-column errors and deterministic board/date aggregation.**
- [ ] **Step 4: Run the focused tests and verify they pass.**

### Task 2: One-Year Job and Redis Persistence

**Files:**
- Modify: `task/fund_flow_backfill.py`
- Test: `tests/test_fund_flow_backfill.py`

**Interfaces:**
- Produces: `backfill_fund_flow(trading_dates=None, source=None, now=None, retries=2, retry_delay=1.0, rate_delay=0.2, sleep=time.sleep) -> dict`.
- Produces: CLI `python -m task.fund_flow_backfill --days 365`.

- [ ] **Step 1: Add failing tests asserting inclusive 365-calendar-day bounds, newest-to-oldest writes, both source types, retries, injected retry/rate delays, and failed-date reporting without writes.**
- [ ] **Step 2: Run the focused tests and verify orchestration assertions fail.**
- [ ] **Step 3: Implement bounded retries around source calls, aggregate complete date snapshots, write through `_写入资金流向redis`, and return nonzero CLI status when any date fails.**
- [ ] **Step 4: Run focused tests and verify they pass without network access.**

### Task 3: Operations Documentation and Verification

**Files:**
- Modify: `README.md`

**Interfaces:**
- Documents: `uv run --frozen python -m task.fund_flow_backfill --days 365`.
- Documents: current AkShare source availability and explicit failure behavior.

- [ ] **Step 1: Add the exact command and availability note to the fund-flow section.**
- [ ] **Step 2: Run `uv run --frozen pytest -q`.**
- [ ] **Step 3: Run `uv run --frozen python -m compileall task tests`.**
- [ ] **Step 4: Run the frontend test and build scripts from `front/package.json`.**
- [ ] **Step 5: Run `git diff --check`, inspect status/diff/log, and commit only the intended files.**
