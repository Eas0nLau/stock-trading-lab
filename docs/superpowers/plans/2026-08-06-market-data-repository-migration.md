# Market Data Repository Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish canonical English market-data repositories and migrate shared utilities and data jobs to `securities`, `daily_quotes`, and `index_daily` while preserving legacy utility result shapes.

**Architecture:** `stock_lab.modules.market_data` owns models, normalization, SQL contracts, and repository persistence/query methods. `task/data_sources.py`, emotion jobs, and shared utilities consume that boundary; only `utils/common.py` and `utils/account.py` translate canonical rows to legacy keys required by existing callers. Strategy and TDX files remain deferred consumers.

**Tech Stack:** Python 3.12, pandas, SQLAlchemy text queries, pytest, MySQL schema contracts, npm/Vite frontend.

## Global Constraints

- Do not touch untracked `data/` or any real database.
- Use canonical English repository outputs only.
- Preserve leading zeros and exchange suffixes in identifiers.
- Do not rewrite the 57 strategy files or TDX monitor files.
- Use TDD: failing focused test, minimal implementation, focused pass, then broader verification.
- Keep compatibility logic thin and at existing utility boundaries.

---

### Task 1: Canonical Market-Data Contracts

**Files:**
- Create: `src/stock_lab/modules/market_data/__init__.py`
- Create: `src/stock_lab/modules/market_data/models.py`
- Create: `src/stock_lab/modules/market_data/helpers.py`
- Test: `tests/unit/modules/market_data/test_helpers.py`

**Interfaces:**
- `normalize_ts_code(value) -> str`
- `normalize_symbol(value) -> str`
- `normalize_trade_date(value) -> int`
- `security_from_source(row) -> dict`
- `daily_quote_from_source(row, stock_name=None) -> dict`
- `index_daily_from_source(row) -> dict`
- dataclasses `Security`, `DailyQuote`, `IndexDaily`

- [ ] Write failing tests for `000001`, `000001.SZ`, `1.SZ`, dates, and canonical source-field mapping.
- [ ] Run `pytest tests/unit/modules/market_data/test_helpers.py -q` and verify failure.
- [ ] Implement the dataclasses and helpers with string-preserving code normalization and canonical column names.
- [ ] Run the focused tests and verify pass.
- [ ] Commit `feat: add canonical market data contracts`.

### Task 2: English Market-Data Repositories

**Files:**
- Create: `src/stock_lab/modules/market_data/repository.py`
- Test: `tests/unit/modules/market_data/test_repository.py`

**Interfaces:**
- `MarketDataRepository(query, engine=None)`
- `trading_dates(limit=160) -> list[int]`
- `securities()`, `security_codes(market=None)`, `symbol_ts_code_map()`
- `daily_quotes(stock_codes, start_date=None, end_date=None) -> list[dict]`
- `daily_quotes_for_date(trade_date, stock_codes) -> list[dict]`
- `index_daily(start_date=None, end_date=None, limit=None) -> list[dict]`
- `upsert_securities(rows)`, `upsert_daily_quotes(rows)`, `upsert_index_daily(rows)`, `replace_securities(rows)`

- [ ] Write fake-query tests asserting only `securities`, `daily_quotes`, and `index_daily` table/column references and parameterized filters.
- [ ] Run focused repository tests and verify failure.
- [ ] Implement the repository SQL and batched upsert/replace writer using existing database conventions.
- [ ] Run focused repository tests and verify pass.
- [ ] Commit `feat: add market data repositories`.

### Task 3: Migrate Data Sources and Emotion Consumption

**Files:**
- Modify: `task/data_sources.py`
- Modify: `src/stock_lab/modules/emotion/repository.py`
- Modify: `src/stock_lab/modules/emotion/jobs.py`
- Test: `tests/test_task_data_sources.py`
- Test: `tests/unit/modules/emotion/test_repository.py`
- Test: `tests/unit/modules/emotion/test_jobs.py`

- [ ] Add tests for data-source canonical adapters and repository writer calls.
- [ ] Run the focused task/emotion tests and verify failure.
- [ ] Delegate data-source normalization, date reads, and writes to `MarketDataRepository`; preserve Chinese task entry points.
- [ ] Inject/use the market-data repository in emotion reads while retaining the existing algorithm translation boundary.
- [ ] Run focused tests and verify pass.
- [ ] Commit `refactor: route market data jobs through repositories`.

### Task 4: Migrate Shared Utility and Account Query Adapters

**Files:**
- Modify: `utils/common.py`
- Modify: `utils/account.py`
- Test: `tests/unit/utils/test_common_market_data.py`
- Test: `tests/unit/utils/test_account_market_data.py`

- [ ] Add fake repository/database tests for pool loading, backtesting, index checks, date iteration, daily loading, and account open/close/sell query paths.
- [ ] Run focused utility tests and verify failure.
- [ ] Replace shared utility legacy SQL with repository calls or canonical English SQL; map canonical fields to existing utility DataFrame keys only at the adapter boundary.
- [ ] Keep `fetch_stock_basic`/`filter_stock_basic` as legacy entry points while sourcing data through the canonical contract and retaining CSV fallback behavior without writing outside the existing cache path.
- [ ] Run focused tests and verify pass.
- [ ] Commit `refactor: migrate shared market data utility reads`.

### Task 5: Documentation and Contract Scans

**Files:**
- Modify: `docs/migration.md`
- Modify: `docs/database-migrations.md`
- Modify: `docs/architecture.md`
- Test: `tests/unit/modules/market_data/test_contracts.py`

- [ ] Add a contract test that rejects legacy table references in shared utilities and requires the public repository exports.
- [ ] Run the contract test and verify failure.
- [ ] Update migration ownership, canonical column mappings, identifier rules, compatibility adapters, and deferred strategy/TDX scope.
- [ ] Run the contract test and verify pass.
- [ ] Commit `docs: document market data repository migration`.

### Task 6: Full Verification and Final Commit

- [ ] Run `pytest -q` with no database/network-dependent test substitutions.
- [ ] Run `python -m compileall -q src task utils tests`.
- [ ] Inspect `front/package.json`, run its declared frontend test command(s), and run `npm run build` from `front`.
- [ ] Scan tracked shared code for `stock_basic`, `stock_daily`, and `akshare_sh000001`; confirm any remaining references are outside the requested shared utility boundary or explicitly deferred.
- [ ] Inspect `git diff`, `git status`, and recent log; confirm `data/` is still untracked and untouched.
- [ ] Commit any final fixes with a focused message and report the final SHA, tests, and concerns.
