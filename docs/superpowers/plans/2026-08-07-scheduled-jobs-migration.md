# Scheduled Jobs Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace legacy daily-update and missing premarket scheduling behavior with official, injected, idempotent English jobs and thin compatibility wrappers.

**Architecture:** A reusable token-owned Redis lock guards both jobs. Official job modules own orchestration and deterministic extraction while lazily assembled adapters provide Redis, market collection, emotion analysis, source content, and INI output; the realtime scheduler dispatches official runners only.

**Tech Stack:** Python 3.12, Redis-compatible client protocol, pathlib, dataclasses, pytest

## Global Constraints

- Official modules use English identifiers and V1 Redis keys.
- Importing official jobs or compatibility wrappers performs no network, database, or Redis operation.
- Tests use injected fakes and must not contact a real website, database, or Redis instance.
- Premarket collection with no configured source returns `disabled` without setting completion state.
- Completion state is written only after all work succeeds; every acquired lock is released in `finally`.
- Existing `task/每日更新.py` and documented `task/盘前纪要.py` direct calls remain thin delegates.

---

### Task 1: Token-Owned Redis Lock

**Files:**
- Create: `src/stock_lab/infrastructure/cache/locks.py`
- Modify: `src/stock_lab/infrastructure/cache/__init__.py`
- Test: `tests/unit/infrastructure/test_job_locks.py`

**Interfaces:**
- Consumes: a Redis-compatible object with `set`, `get`, and `delete`.
- Produces: `RedisJobLock(client, key, ttl_seconds, token_factory=None)`, `acquire() -> bool`, `release() -> bool`, and context-manager methods.

- [ ] **Step 1: Write failing tests** for `SET key token NX EX ttl`, lock contention, token-matched release, foreign-token preservation, positive TTL validation, and release after a context-body exception.
- [ ] **Step 2: Run** `pytest tests/unit/infrastructure/test_job_locks.py -q` and verify the missing-module failure.
- [ ] **Step 3: Implement the lock** with a UUID token by default, one acquisition per instance, and compare-before-delete release behavior compatible with the existing decoded-string Redis client.
- [ ] **Step 4: Run** `pytest tests/unit/infrastructure/test_job_locks.py -q` and verify all tests pass.

### Task 2: Official Daily Update Job

**Files:**
- Create: `src/stock_lab/jobs/daily_update.py`
- Test: `tests/unit/jobs/test_daily_update.py`

**Interfaces:**
- Consumes: `DailyUpdateCollector` methods `trading_dates(limit)`, `update_index_daily(start_date, end_date)`, `update_securities()`, `update_daily_quotes(start_date, end_date)`, and `collect_board_actions(trade_date)`; injected hot-board/index emotion callables; Redis-compatible state client.
- Produces: `run_daily_update(trade_date, collector=None, state=None, run_hot_board=None, run_index=None) -> dict`, `backfill_daily_updates(days, ...) -> dict`, `DAILY_UPDATE_LOCK_KEY`, and `daily_update_completion_key(trade_date)`.

- [ ] **Step 1: Write failing tests** for normalized dates, source-before-analysis order, missing-index seeding, previous trading date selection, V1 completion TTL, idempotent skip, lock contention, no completion after failure, and lock release after failure.
- [ ] **Step 2: Run** `pytest tests/unit/jobs/test_daily_update.py -q` and verify missing imports.
- [ ] **Step 3: Implement injected orchestration** preserving the six existing active steps and lazy defaults that adapt `task.data_sources`, `_5_韭研公社异动`, official emotion jobs, and `utils.db.redis_con_localhost` only when called.
- [ ] **Step 4: Implement backfill** so each date reports `success`, `skipped`, or `failed` and the aggregate is `failed` if any date fails.
- [ ] **Step 5: Run** `pytest tests/unit/jobs/test_daily_update.py -q` and verify all tests pass.

### Task 3: Official Premarket Extraction And Job

**Files:**
- Create: `src/stock_lab/jobs/premarket_summary.py`
- Test: `tests/unit/jobs/test_premarket_summary.py`

**Interfaces:**
- Consumes: a source callable/object yielding summary text and canonical security rows, an injected INI writer, an output root, and Redis-compatible state.
- Produces: immutable `SecurityMention(stock_code, stock_name)`, `extract_security_mentions(text, securities) -> list[SecurityMention]`, `write_premarket_ini(mentions, output_root, trade_date) -> Path`, `run_premarket_summary(trade_date, source=None, state=None, writer=None, output_root=None) -> dict`, `PREMARKET_LOCK_KEY`, and `premarket_completion_key(trade_date)`.

- [ ] **Step 1: Write failing extraction tests** for name/code matching, body order, first-occurrence deduplication, six-digit normalization, overlapping stock names, unrelated text, and empty input rejection.
- [ ] **Step 2: Write failing job tests** for established INI lines/path/name, disabled source behavior, V1 completion TTL, repeated-run skip, lock contention, and release/no completion on source and writer failures.
- [ ] **Step 3: Run** `pytest tests/unit/jobs/test_premarket_summary.py -q` and verify missing imports.
- [ ] **Step 4: Implement pure extraction** by finding each canonical code and name occurrence, sorting candidates by source position and stable universe order, and deduplicating normalized codes.
- [ ] **Step 5: Implement orchestration and writer** with no default external source, lazy Redis/output defaults, explicit `disabled`, and completion only after a non-empty INI is written.
- [ ] **Step 6: Run** `pytest tests/unit/jobs/test_premarket_summary.py -q` and verify all tests pass.

### Task 4: Scheduler And Compatibility Cutover

**Files:**
- Modify: `src/stock_lab/jobs/realtime_monitor.py`
- Modify: `task/每日更新.py`
- Create: `task/盘前纪要.py`
- Modify: `task/emotion_analysis.py`
- Modify: `tests/unit/jobs/test_realtime_monitor.py`
- Modify: `tests/test_daily_update.py`
- Modify: `tests/test_optional_task_modules.py`
- Modify: `tests/test_emotion_analysis.py`

**Interfaces:**
- Consumes: official `run_daily_update`, `run_premarket_summary`, and emotion job functions.
- Produces: scheduler dispatch after 17:35/08:00 on weekdays; wrapper functions `tasks`, `backfill`, `韭研公社盘前纪要采集`, `落库指数周期`, and `落库热门板块情绪`.

- [ ] **Step 1: Rewrite/add failing tests** to assert official scheduler delegates, no weekend/early dispatch, optional premarket source forwarding, thin wrapper forwarding, and import-time I/O absence.
- [ ] **Step 2: Add a source scan assertion** that `task/emotion_analysis.py` contains no SQLAlchemy import, `_upsert`, or legacy emotion table names.
- [ ] **Step 3: Run the four affected test files** and verify failures against legacy loading and implementations.
- [ ] **Step 4: Cut scheduler over** to official runners and injected optional source loading; remove startup lock deletion because expiring token-owned locks must not be deleted by another process.
- [ ] **Step 5: Replace Chinese task bodies with lazy thin delegates** and retain existing CLI behavior for daily update.
- [ ] **Step 6: Replace stale emotion-analysis code with official delegates** and update compatibility tests to canonical behavior.
- [ ] **Step 7: Run affected tests plus `tests/unit/modules/emotion/test_jobs.py`** and verify all pass.

### Task 5: Documentation And Full Verification

**Files:**
- Modify: `README.md`
- Modify: `docs/migration.md`
- Modify: `src/stock_lab/jobs/__init__.py` if stable exports are needed

**Interfaces:**
- Produces: accurate scheduler, source configuration, V1 state-key, output, and migration ownership documentation.

- [ ] **Step 1: Correct README claims** to list the actual six-step daily pipeline, official entry points, injected/disabled premarket source behavior, retained INI extraction/output behavior, and no claim of automatic Jiuyan collection without an adapter.
- [ ] **Step 2: Update migration mapping** so daily update, premarket summary, locks, scheduler, and emotion wrappers point to official owners.
- [ ] **Step 3: Run** `pytest -q` with environment safeguards that prevent real external services.
- [ ] **Step 4: Run** `python -m compileall -q src task tests`.
- [ ] **Step 5: Run frontend scripts declared by `front/package.json`**, including tests when present and the production build.
- [ ] **Step 6: Run source checks** for old scheduler keys, legacy emotion table writes, and Chinese identifiers in newly created official files; inspect every result and justify allowed display/output literals.
- [ ] **Step 7: Run** `git diff --check`, inspect `git status --short`, `git diff --stat`, the complete diff, and recent log; leave the unrelated untracked `data/` untouched.
- [ ] **Step 8: Commit intended implementation, tests, and docs** with a concise migration message, then report both design and implementation commit IDs, verification output, and residual external-source concern.
