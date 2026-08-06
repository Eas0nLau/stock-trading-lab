# Final Listener And Base Guard Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make fund-flow listener shutdown fit the worker join budget, guarantee page cleanup on navigation failure, and prevent approved research base names from being rebound before class creation.

**Architecture:** Poll listener responses in short bounded slices while retaining the existing overall response deadline. Fund-flow obtains and stores the page before navigating, then closes it on navigation failure. Research validates all module-level bindings before compilation and permits only immutable builtin class bases.

**Tech Stack:** Python 3.12, threading, monotonic deadlines, Python AST, pytest.

## Global Constraints

- Stop during listener wait completes in less than one second.
- Navigation failure closes the owned page exactly once and preserves the navigation exception.
- Protected class-base names cannot be rebound by assignments, imports, functions, or classes.
- All 57 catalogued strategies continue to execute in the existing offline suite.
- Leave the pre-existing untracked `data/` directory untouched.

---

### Task 1: Stop-Aware Listener Polling And Page Ownership

**Files:** Modify `src/stock_lab/modules/fund_flow/source.py`, `src/stock_lab/infrastructure/browser/client.py`; test `tests/unit/modules/fund_flow/test_collector.py`, `tests/unit/infrastructure/test_browser_client.py`.

- [ ] Add a failing listener test that starts collection, signals stop during an empty listener wait, and joins in under one second.
- [ ] Add a failing initialization test where navigation raises and page close is called exactly once without changing the raised error.
- [ ] Replace the five-second listener call with short polls under one overall deadline.
- [ ] Create/store the fund-flow page without a URL before source-owned navigation and cleanup.
- [ ] Run focused browser, fund-flow, and worker tests.

### Task 2: Protected Research Base Names

**Files:** Modify `src/stock_lab/modules/research/source_runtime.py`; test `tests/test_research_source_runtime.py`; update `docs/research-backtesting.md`.

- [ ] Add a failing `Evil.__init_subclass__` plus `object = Evil` payload test and verify no marker is created.
- [ ] Add binding-form tests for assignment, import alias, function definition, and class definition rebinding.
- [ ] Reject protected-name bindings before import injection or module compilation.
- [ ] Restrict class bases to no base or `object`, `tuple`, and `frozenset` names.
- [ ] Run source-runtime, research-family, and all-57 registry tests.

### Task 3: Full Verification And Commit

**Files:** All files above and documentation.

- [ ] Run full pytest, compileall, frontend tests/build, startup smoke, and diff checks.
- [ ] Inspect status/diff/log, stage only intended files, and commit the fixes.
- [ ] Report commit, test evidence, and residual third-party limitations.
