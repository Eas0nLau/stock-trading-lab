# Final Review Fix Wave Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve the six final-review findings while preserving official job behavior and legacy compatibility contracts.

**Architecture:** Keep scheduling policy in `realtime_monitor`, with a durable in-process per-job/per-date claim registry and injectable timer/runner seams. Pass one explicit `Settings` object through bootstrap route and worker factories. Put MySQL query/retry and bulk insert behavior in `infrastructure.database`, leaving `utils.db` as forwarding compatibility names. Treat migration 002 as a durable state machine and make startup validate its terminal state.

**Tech Stack:** Python, pytest, FastAPI, MySQL SQL, pandas, existing infrastructure factories.

## Global Constraints

- Do not connect to or mutate a user database during tests.
- Preserve official job idempotency and compatibility wrapper behavior.
- Strategy source is trusted application code, but class bodies must be behaviorless and execution builtins must be explicitly allowlisted.
- Retry loops are finite and must not recurse.

---

### Task 1: Durable Scheduler Dispatch

**Files:** Modify `src/stock_lab/jobs/realtime_monitor.py`; test `tests/unit/jobs/test_realtime_monitor.py`.

- [ ] Add a lock-protected per-process claim set keyed by official job id and trade date.
- [ ] Make repeated eligible calls for the same date schedule each official job once, while different dates remain dispatchable.
- [ ] Add a repeated-tick test using the existing capturing timer and retain the official runner arguments.

### Task 2: Interruptible Fund-Flow Lifecycle

**Files:** Modify `src/stock_lab/modules/fund_flow/source.py`, `collector.py`; test `tests/unit/modules/fund_flow/test_collector.py`.

- [ ] Add `stop_event` propagation to waits and collection lifecycle methods.
- [ ] Use `Event.wait(timeout)` when available, and close page/listener resources in a `finally` block.
- [ ] Test a long configured interval exits promptly after stop and an owned page is closed.

### Task 3: Migration State and Startup Gate

**Files:** Modify `db/migrations/002_migrate_legacy_data.sql`, `src/stock_lab/bootstrap/application.py`, migration docs; test `tests/integration/database/test_schema_migration.py` plus startup unit coverage.

- [ ] Record `running` before migration DML, update to `failed` on SQL exception, and write `succeeded` only after all parity gates.
- [ ] Use transactional DML where MySQL permits it without changing DDL/procedure semantics.
- [ ] Add static/disposable SQL assertions for durable states and a startup rejection test for incomplete migration state without using a user database.

### Task 4: Explicit Settings Composition

**Files:** Modify `src/stock_lab/bootstrap/application.py`, `api/routes.py`, module route/service factories and worker factory call sites; test `tests/unit/bootstrap/test_application.py` and focused service tests.

- [ ] Make route and worker composition accept the supplied settings object.
- [ ] Ensure services and infrastructure clients are built from that object, with no silent fallback to global settings inside `create_app`.
- [ ] Verify custom interval/top-N/timeout settings reach constructed services.

### Task 5: Research Runtime Policy

**Files:** Modify `src/stock_lab/modules/research/source_runtime.py`; test `tests/test_research_source_runtime.py`; update research docs.

- [ ] Reject class bodies containing executable statements while preserving declarations needed by trusted strategies.
- [ ] Replace `__builtins__` exposure with a small explicit harmless allowlist required by existing sources.
- [ ] Add a side-effect class regression test and retain existing source/import tests.

### Task 6: Database Service Extraction

**Files:** Modify `src/stock_lab/infrastructure/database/client.py`; add focused database service module if needed; reduce `utils/db.py` to forwarding projections; test infrastructure database tests and a compatibility contract scan.

- [ ] Move finite MySQL disconnect retry/query execution and pandas bulk insert into the official database service.
- [ ] Ensure errors are re-raised after the configured finite attempts and bulk insertion cannot recurse indefinitely.
- [ ] Keep legacy names forwarding to the service and assert production code no longer owns the implementation.

### Task 7: Full Verification and Commit

**Files:** Update relevant architecture/migration/research docs.

- [ ] Run focused tests after each task, then full `pytest`, Python compile checks, frontend tests/build, diff/contract scans, and startup smoke.
- [ ] Inspect `git status`, `git diff`, and recent log; stage only intended files and commit with a concise fix message.
- [ ] Report commit, tests, and any environmental concerns.
