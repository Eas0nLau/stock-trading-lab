# Executable Research Adapters Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make all 57 research registry entries execute single-date selection through injected local or offline repositories and provide shared date-range backtesting.

**Architecture:** A source-selector runtime compiles legacy selector functions and literal configuration without executing imports or top-level code, then injects context-bound compatibility proxies. Static metadata dispatches 56 selector sources and one Dragon Tiger premium adapter; CLI provider factories create either configured local repositories or canonical in-memory fixtures.

**Tech Stack:** Python 3.12, AST, pandas, SQLite, existing market-data/Dragon Tiger repositories, argparse, pytest.

## Global Constraints

- `run(context)` performs selection only for `context.target_date`.
- No registry entry may be blocked or unresolved.
- Offline tests must not access MySQL, Redis, browsers, or network APIs.
- Preserve Chinese display names and source-specific literal configuration.
- Canonical stock identifiers are strings; qualified and bare values normalize at repository boundaries.
- Legacy launchers must contain no integer stock-code casts or literal `ts_code IN` tuple SQL.

---

### Task 1: Context, Results, And Offline Provider

**Files:**
- Modify: `src/stock_lab/modules/research/context.py`
- Create: `src/stock_lab/modules/research/results.py`
- Create: `src/stock_lab/modules/research/providers.py`
- Test: `tests/test_research_providers.py`

**Interfaces:**
- Produces: `ResearchContext.target_date`, `SelectionResult`, `OfflineResearchProvider.context(target_date)`, `configured_local_context(target_date)`.

- [ ] Write failing tests proving built-in/JSON fixtures create canonical repositories, normalize symbols, and make no live resource calls.
- [ ] Run `uv run pytest tests/test_research_providers.py -q` and verify missing provider APIs fail.
- [ ] Implement SQLite fixture query/repository adapters and explicit configured-local composition.
- [ ] Run provider tests and verify they pass.

### Task 2: Source-Preserving Selector Runtime

**Files:**
- Create: `src/stock_lab/modules/research/source_runtime.py`
- Create: `src/stock_lab/modules/research/compatibility.py`
- Test: `tests/test_research_source_runtime.py`

**Interfaces:**
- Consumes: `ResearchContext`, query provider, `ResearchData`.
- Produces: `run_source_selector(metadata, context) -> SelectionResult`.

- [ ] Write failing tests using small source modules to prove imports/top-level calls are skipped, literal parameters survive, qualified codes remain strings, and injected daily/5m/Dragon Tiger data is used.
- [ ] Run the focused tests and verify source runtime APIs are absent.
- [ ] Implement AST filtering, safe imports/globals, sequential Pool, pandas/query/common/account/task proxies, and normalized result projection.
- [ ] Run source-runtime tests and verify they pass without live calls.

### Task 3: Resolve The Full Registry

**Files:**
- Modify: `src/stock_lab/modules/research/strategies.py`
- Modify: `tests/test_research_registry.py`
- Test: `tests/test_research_families.py`

**Interfaces:**
- Produces: 56 `source_selector` entries and one `dragon_tiger_premium` entry; every `StrategyEntry.run(context)` returns `SelectionResult`.

- [ ] Replace blocked-status tests with a failing exhaustive test that runs every catalog entry in an offline context.
- [ ] Add representative family fixture tests for volume/price, trend, new-high, KDJ, Dragon Tiger, and premium selection.
- [ ] Implement exact family dispatch and per-entry adapter parameters.
- [ ] Run registry/family tests and verify all 57 resolve.

### Task 4: Shared Backtest Orchestration

**Files:**
- Modify: `src/stock_lab/modules/research/backtest.py`
- Test: `tests/test_research_backtest_runner.py`

**Interfaces:**
- Produces: `run_backtest(entry, context_factory, start_date, end_date) -> BacktestResult`.

- [ ] Write a failing multi-date fixture test asserting selector reuse, next-session returns, and aggregation.
- [ ] Implement orchestration over repository trading dates without legacy account state.
- [ ] Run focused backtest tests and verify they pass.

### Task 5: Canonical Launcher Cleanup

**Files:**
- Modify: active files under `strategy/`
- Modify: `src/stock_lab/modules/market_data/helpers.py`
- Modify: `src/stock_lab/modules/market_data/repository.py`
- Modify: `tests/test_research_contracts.py`

**Interfaces:**
- Produces: normalized string-code repository results and parameterized launcher filters.

- [ ] Add failing scans for code `.astype(int)`, `int(code)` list construction, and literal `ts_code IN` SQL in launchers.
- [ ] Normalize repository outputs and mechanically replace incompatible launcher filters with `normalize_symbol`, `normalize_ts_code`, and `stock_code_filter`.
- [ ] Run scans, compileall, and representative imports.

### Task 6: Usable CLI And Documentation

**Files:**
- Modify: `src/stock_lab/modules/research/cli.py`
- Modify: `tests/test_research_cli.py`
- Modify: `docs/research-backtesting.md`
- Modify: `README.md`

**Interfaces:**
- Produces: `list`, `run --provider local`, `run --offline [--fixture PATH]`, and `backtest` commands.

- [ ] Write failing CLI tests for offline run/backtest output and controlled local-provider errors.
- [ ] Implement provider options and JSON-safe result output.
- [ ] Update docs with executable examples and provider guarantees.
- [ ] Run CLI tests and manual offline commands.

### Task 7: Verification And Commit

- [ ] Run full `uv run pytest -q`.
- [ ] Run compileall across official and compatibility Python sources.
- [ ] Run frontend tests and build.
- [ ] Run legacy table/code/join scans and `git diff --check`.
- [ ] Review staged diff, preserve untracked `data/`, and commit only intended files.
