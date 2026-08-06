# Research Backtest Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Provide an official English research/backtest module with repository-backed data primitives, a safe uniform strategy registry/CLI, and zero active legacy SQL table references.

**Architecture:** `stock_lab.modules.research` owns immutable research context, data-access protocols, backtest primitives, strategy discovery, and CLI. Legacy scripts remain compatibility launchers; registry adapters load them only on explicit selection and pass an injected context whose production repositories are explicit and whose test context has no network/database capability. Existing result calculations remain in place wherever possible.

**Tech Stack:** Python 3.12, pandas, SQLAlchemy, pytest, argparse, existing `MarketDataRepository` and `DragonTigerRepository` interfaces.

## Global Constraints

- No real database or network access in tests.
- Preserve Chinese strategy display names; official identifiers and module APIs are English.
- Active strategy SQL uses canonical English tables and columns or official repositories.
- Importing packages and listing strategies must not execute strategies, connect to services, or fetch data.
- Verify with pytest, compileall, frontend tests/build, and a legacy-reference diff scan before committing.

### Task 1: Establish Contract Tests

**Files:**
- Create: `tests/test_research_contracts.py`
- Create: `tests/test_research_registry.py`
- Create: `tests/test_research_cli.py`

- [ ] Write failing tests for legacy-table scanning, no side effects on importing/listing, canonical quote/KDJ/5m/dragon-tiger access, representative adapter selection, and CLI `list`/`run` behavior with an injected fake context.
- [ ] Run the focused tests and confirm they fail because the research package does not exist.

### Task 2: Add Research Data Contracts and Primitives

**Files:**
- Create: `src/stock_lab/modules/research/__init__.py`
- Create: `src/stock_lab/modules/research/context.py`
- Create: `src/stock_lab/modules/research/data.py`
- Create: `src/stock_lab/modules/research/backtest.py`

- [ ] Implement typed `ResearchContext` with explicit market-data, dragon-tiger, account, and optional network capability fields; provide a no-side-effect test factory.
- [ ] Implement canonical data access helpers that return normalized DataFrames/records from injected repositories and expose daily quotes, securities, index daily, KDJ, 5m bars, and dragon-tiger data.
- [ ] Implement small pure backtest primitives for next-trading-date lookup, entry/exit return calculation, position sizing, and result aggregation without global account state.
- [ ] Run the contract tests for these interfaces and make them pass.

### Task 3: Add Strategy Discovery, Safe Adapters, and CLI

**Files:**
- Create: `src/stock_lab/modules/research/strategies.py`
- Create: `src/stock_lab/modules/research/cli.py`
- Create: `src/stock_lab/modules/research/__main__.py`

- [ ] Build a static registry containing all active strategy files, English identifiers, Chinese display names, source paths, and adapter metadata; ensure discovery does not import legacy modules.
- [ ] Implement lazy loading and a uniform `run(context) -> result` adapter that supports known legacy entrypoint shapes and reports unsupported shapes without executing at import time.
- [ ] Make CLI `list` print identifiers/display names and CLI `run <id>` require an explicit context/provider, rejecting default live access in tests.
- [ ] Run registry and CLI tests with fake repositories and assert no network/DB calls.

### Task 4: Migrate Legacy Strategy Data Access

**Files:**
- Modify: all active files under `strategy/`
- Modify: `游资溢价分析/*.py` and collectors where active SQL remains
- Modify: `utils/common.py`, `utils/account.py`, and shared legacy market-data helpers as needed

- [ ] Apply a structured/mechanical table and column transformation using `db/schema_mapping.json` and the existing repository APIs: `stock_daily` -> `daily_quotes`, `stock_basic` -> `securities`, `akshare_sh000001` -> `index_daily`, `stock_kdj` -> `kdj_indicators`, `t_stock_5_min_k` -> `intraday_bars_5m`, and every `t_龙虎榜*` table -> its English counterpart.
- [ ] Preserve aliases expected by strategy calculations (`close`, `open`, `high`, `low`, `pre_close`, `pct_chg`, etc.) while using canonical source columns.
- [ ] Remove import-time token/API/database initialization and direct execution; place work behind functions and retain Chinese launchers as thin compatibility calls.
- [ ] Run the contract scanner and compile all migrated Python files; fix every reported active reference.

### Task 5: Complete Tests and Documentation

**Files:**
- Modify: `tests/test_research_contracts.py`, `tests/test_research_registry.py`, `tests/test_research_cli.py`
- Modify: `README.md`
- Create or modify: `docs/research-backtesting.md`

- [ ] Add representative strategy selection/import/backtest tests and verify Chinese display names plus English identifiers.
- [ ] Document official package imports, injected repository context, CLI examples, compatibility launchers, and test safety guarantees.
- [ ] Run full Python tests, compileall, frontend tests/build, and final legacy-reference scan.

### Task 6: Self-Review and Commit

- [ ] Inspect `git diff --check`, `git diff`, and `git status`; preserve unrelated `data/` changes.
- [ ] Review for import-time execution, network/database defaults, semantic alias changes, incomplete strategy registry entries, and accidental non-ASCII churn.
- [ ] Commit only intended migration files with a concise repository-style message.
