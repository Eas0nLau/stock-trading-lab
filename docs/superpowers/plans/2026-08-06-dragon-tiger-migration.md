# Dragon-Tiger and Broker Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace production legacy dragon-tiger and broker code with a tested English module backed only by canonical schema tables.

**Architecture:** Canonical dataclasses and pure source parsers feed an injected repository and collector layer. Premium analytics consume the dragon-tiger repository and `MarketDataRepository`; old executable paths only assemble dependencies and delegate.

**Tech Stack:** Python 3.12, dataclasses, BeautifulSoup, SQLAlchemy, pandas compatibility outputs, pytest

## Global Constraints

- Official code uses English identifiers and only `dragon_tiger`, `broker_listing_history`, `broker_top_stats`, `brokers`, and `daily_quotes`.
- Chinese source and visible values are allowed only at adapter boundaries.
- Tests must not call real websites, Redis, or databases.
- Preserve existing filters, amount units, date windows, identities, and selection results.

---

### Task 1: Canonical Models and Listing Parser

**Files:**
- Create: `src/stock_lab/modules/dragon_tiger/__init__.py`
- Create: `src/stock_lab/modules/dragon_tiger/models.py`
- Create: `src/stock_lab/modules/dragon_tiger/parsing.py`
- Test: `tests/unit/modules/dragon_tiger/test_parsing.py`

**Interfaces:**
- Produces: `DragonTigerListing`, `Broker`, `BrokerListingHistory`, `BrokerTopStats`; `parse_amount(value) -> float`; `parse_listing_page(html, trade_date) -> list[DragonTigerListing]`; `listing_brokers(listings) -> list[Broker]`; `listing_history(listings) -> list[BrokerListingHistory]`.

- [ ] **Step 1: Write failing parser tests** covering `亿`/`万`/percent conversion, five buy and sell seats, missing broker IDs, broker deduplication, and stable history IDs from a local HTML fixture.
- [ ] **Step 2: Run** `pytest tests/unit/modules/dragon_tiger/test_parsing.py -q` and verify import/expectation failures.
- [ ] **Step 3: Implement immutable schema-shaped dataclasses and pure BeautifulSoup parsers**. Keep source labels such as `明细：`, `合计买入：`, and `今日龙虎榜暂未公布` as constants in `parsing.py`; emit no records for unpublished pages and raise `ValueError` for malformed published pages.
- [ ] **Step 4: Run** `pytest tests/unit/modules/dragon_tiger/test_parsing.py -q` and verify pass.

### Task 2: Repository and Collector Adapters

**Files:**
- Create: `src/stock_lab/modules/dragon_tiger/repository.py`
- Create: `src/stock_lab/modules/dragon_tiger/collectors.py`
- Test: `tests/unit/modules/dragon_tiger/test_repository.py`
- Test: `tests/unit/modules/dragon_tiger/test_collectors.py`

**Interfaces:**
- Consumes: canonical dataclasses and parser functions from Task 1.
- Produces: `DragonTigerRepository(query, engine=None)` methods `trading_dates(start_date)`, `listings(trade_date=None, start_date=None, end_date=None, stock_codes=None)`, `brokers()`, `broker_history(start_date=None, end_date=None, broker_ids=None)`, `broker_top_stats()`, and typed upserts; `collect_listings(start_date, repository, fetch_page)`; `collect_brokers(repository, fetch_page)`; `collect_broker_history(repository, fetch_page, cache=None)`.

- [ ] **Step 1: Write failing repository tests** asserting bound parameters, canonical columns, ordering, dynamic stock/broker filters, empty writes, and SQLAlchemy upsert table/key behavior.
- [ ] **Step 2: Write failing collector tests** using fake fetchers/repositories to verify URL-independent orchestration, unpublished-page skips, broker deduplication, and no ambient I/O.
- [ ] **Step 3: Run** `pytest tests/unit/modules/dragon_tiger/test_repository.py tests/unit/modules/dragon_tiger/test_collectors.py -q` and verify failures.
- [ ] **Step 4: Implement repository and collectors** with dependency injection and explicit row conversion via `dataclasses.asdict`; use `daily_quotes` for distinct trading dates.
- [ ] **Step 5: Run the two test files** and verify pass.

### Task 3: Canonical Premium Analysis

**Files:**
- Create: `src/stock_lab/modules/dragon_tiger/analytics.py`
- Test: `tests/unit/modules/dragon_tiger/test_analytics.py`

**Interfaces:**
- Consumes: `DragonTigerRepository.listings`, `DragonTigerRepository.broker_history`, and `MarketDataRepository.daily_quotes`.
- Produces: `analyze_broker_premium(start_date, latest_date, repository, market_data_repository, net_buy_threshold=2000, average_return_threshold=2, minimum_samples=3) -> list[int]`.

- [ ] **Step 1: Write failing analysis tests** with in-memory fake repositories for excluded connect seats, net-buy threshold, fewer-than-three quote rows, next-two-session open return, minimum sample count, buy-side latest-date matching, lineup deduplication, thresholding, and result ordering.
- [ ] **Step 2: Run** `pytest tests/unit/modules/dragon_tiger/test_analytics.py -q` and verify failure.
- [ ] **Step 3: Implement the analysis** using English local names and canonical fields while preserving the legacy algorithm, including its 20-calendar-day quote window and latest-date cap.
- [ ] **Step 4: Run the analysis tests** and verify pass.

### Task 4: Compatibility and Active Consumer Cutover

**Files:**
- Modify: `游资溢价分析/溢价分析.py`
- Modify: `游资溢价分析/采集/龙虎榜数据采集.py`
- Modify: `游资溢价分析/采集/营业部数据采集.py`
- Modify: `游资溢价分析/采集/游资数据采集.py`
- Modify: `strategy/*.py` files containing active `t_龙虎榜` SQL
- Test: `tests/unit/modules/dragon_tiger/test_compatibility.py`

**Interfaces:**
- Consumes: official collectors, repository, analytics, market-data repository, and existing `utils.db` dependencies.
- Produces: legacy `main(...)` call signatures and unchanged strategy result columns.

- [ ] **Step 1: Write failing compatibility tests** that import each old path without I/O, monkeypatch official delegates, verify argument/result forwarding, and scan active Python source for legacy dragon-tiger table SQL outside schema migration artifacts.
- [ ] **Step 2: Run** `pytest tests/unit/modules/dragon_tiger/test_compatibility.py -q` and verify failure.
- [ ] **Step 3: Replace old production bodies with thin guarded launchers** and preserve their concrete command-line defaults.
- [ ] **Step 4: Change every active strategy dragon-tiger query in place** from `t_龙虎榜`, `date`, and Chinese column aliases to `dragon_tiger`, `trade_date`, and canonical columns; preserve aliases where downstream DataFrames still expect Chinese labels.
- [ ] **Step 5: Run compatibility tests and the complete dragon-tiger unit directory** and verify pass.

### Task 5: Documentation and Full Verification

**Files:**
- Modify: `docs/migration.md`
- Modify: `docs/database-migrations.md`

**Interfaces:**
- Produces: an accurate module ownership map and a legacy-drop blocker list that no longer names migrated dragon-tiger/broker code.

- [ ] **Step 1: Update migration documentation** with canonical ownership, adapter status, strategy cutover, and remaining unrelated legacy blockers.
- [ ] **Step 2: Run** `pytest -q`.
- [ ] **Step 3: Run** `python -m compileall -q src task strategy 游资溢价分析`.
- [ ] **Step 4: Run frontend tests and build** using the scripts declared in `front/package.json`.
- [ ] **Step 5: Run source diff checks** for legacy table references, Chinese identifiers in official files, `git diff --check`, `git status --short`, and inspect `git diff`.
- [ ] **Step 6: Commit all intended files only** after reviewing status, diff, and recent log.
