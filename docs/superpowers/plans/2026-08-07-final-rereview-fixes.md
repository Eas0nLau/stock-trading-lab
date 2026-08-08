# Final Re-Review Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the remaining cooperative shutdown, browser settings composition, and research class-header validation findings.

**Architecture:** Thread the worker stop event through the fund-flow source contract and check it at every bounded browser/listener boundary. Bind the composed `Settings` into browser factories rather than resolving globals. Validate the complete class definition header and body before retaining it in the compiled strategy module.

**Tech Stack:** Python 3.12, threading events, FastAPI composition, Python AST, pytest.

## Global Constraints

- Cleanup is idempotent, tolerates partial initialization, and never masks the primary collection error.
- Composed browser paths do not call global `get_settings`.
- Class header expressions with executable calls are rejected before `exec`.
- Leave the pre-existing untracked `data/` directory untouched.

---

### Task 1: Cooperative Fund-Flow Shutdown

**Files:** Modify `src/stock_lab/modules/fund_flow/source.py`, `collector.py`; test `tests/unit/modules/fund_flow/test_collector.py` and `tests/unit/jobs/test_realtime_monitor.py`.

- [ ] Add failing tests proving a stop event releases a blocking fake collection and `WorkerManager.stop_all()` leaves no live thread.
- [ ] Add cleanup tests for uninitialized, partially initialized, repeated-close, listener-close failures, and primary-error preservation.
- [ ] Pass `stop_event` through initialize, collect, and collect-all operations and check before/after bounded browser calls.
- [ ] Run focused fund-flow and worker tests.

### Task 2: Explicit Browser Settings

**Files:** Modify `src/stock_lab/infrastructure/browser/client.py` and composed source factories; test a new focused browser client suite.

- [ ] Add failing tests showing custom `project_root` controls the Chrome profile and custom `browser_close_old_tabs` controls tab cleanup.
- [ ] Add explicit `settings` parameters to browser/page factories and bind settings in fund-flow and strategy-pick composition.
- [ ] Run browser, fund-flow, and strategy-pick tests.

### Task 3: Safe Research Class Headers

**Files:** Modify `src/stock_lab/modules/research/source_runtime.py`; test `tests/test_research_source_runtime.py`; update research documentation.

- [ ] Add failing tests for call-based bases, class decorators, and metaclass/keyword expressions.
- [ ] Permit only approved `Name`/`Attribute` base expressions and reject class keywords/decorators before compilation.
- [ ] Run source-runtime, research-family, and registry tests.

### Task 4: Verification and Commit

**Files:** All files above and relevant docs.

- [ ] Run full pytest, compileall, frontend tests/build, startup smoke, and diff checks.
- [ ] Inspect status/diff/log, stage only intended files, and create a new fix commit.
- [ ] Report commit, test evidence, and remaining environmental concerns.
