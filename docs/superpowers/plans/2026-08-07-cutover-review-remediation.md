# Cutover Review Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore behavior lost in the final cutover and enforce complete independence between official modules and compatibility utilities.

**Architecture:** Official infrastructure factories own MySQL, Redis, AkShare, and Tushare acquisition. Domain services own fund-flow shaping/caching and hot-board response derivation; compatibility files only compose or forward official APIs, with AST contracts rejecting implementation behavior.

**Tech Stack:** Python 3.12, Redis, SQLAlchemy, FastAPI, pandas, pytest, Vue 3, Vite

## Global Constraints

- Official code under `src/stock_lab` must not import `utils`, `task`, or Chinese compatibility packages.
- Fund-flow storage remains V1-only; chart caches must also use ASCII V1 keys.
- No test may contact real network, Redis, or MySQL services.
- Preserve direct compatibility script paths as thin wrappers.
- Do not execute `003_drop_legacy_schema.sql`.

---

### Task 1: Strategy Collector Missing-Date Failure

**Files:**
- Modify: `tests/unit/modules/strategy_pick/test_strategy_pick_collector.py`
- Modify: `src/stock_lab/modules/strategy_pick/collector.py`

**Interfaces:**
- Produces: `StrategyPickCollector.persist_legacy_snapshot()` with a current-date fallback when `collectedDate` is absent.

- [ ] Add a test that persists a snapshot without `collectedDate` under a patched clock and expects `YYYYMMDD`.
- [ ] Run the test and verify the missing `datetime` name fails.
- [ ] Restore the standard-library import and run all strategy-pick tests.

### Task 2: Official Infrastructure Composition

**Files:**
- Create: `src/stock_lab/infrastructure/database/query.py`
- Create: `src/stock_lab/infrastructure/market_data/akshare.py`
- Create: `src/stock_lab/infrastructure/market_data/tushare.py`
- Modify: official jobs/APIs/collectors currently importing `utils`
- Modify: relevant unit tests

**Interfaces:**
- Produces: `create_mysql_query(resources)`, `create_market_data_repository(settings)`, lazy `AkShareSource`, and lazy `TushareSource`.
- Produces: official Redis acquisition through existing `create_redis_client(settings)`.

- [ ] Add contract and unit tests proving official imports do not load `utils` and source clients remain lazy.
- [ ] Run focused tests and verify all 12 current reverse imports are reported.
- [ ] Replace every official `utils` import with injected dependencies or infrastructure factories.
- [ ] Run job, API, infrastructure, and market-data tests.

### Task 3: Fund-Flow Chart Semantics and Warm-Up

**Files:**
- Modify: `src/stock_lab/modules/fund_flow/repository.py`
- Modify: `src/stock_lab/modules/fund_flow/service.py`
- Modify: `src/stock_lab/modules/fund_flow/source.py`
- Modify: `src/stock_lab/modules/fund_flow/api.py`
- Modify: `tests/unit/modules/fund_flow/test_fund_flow.py`
- Modify: `tests/unit/modules/fund_flow/test_collector.py`

**Interfaces:**
- Produces: `FundFlowService.history(flow_type, trade_date, top_n=None)`.
- Produces: top-N positive and negative filtering, matrix-v1 for `top_n <= 0`, matrix-v2 for `top_n > 0`, V1 chart cache keys/indexes, invalid-cache recovery, cache invalidation after save, and `FundFlowSource.warm_history()` for each latest flow date.

- [ ] Add literal behavior tests for top inflow/outflow selection, duplicate-time replacement, sparse matrix points, cache hit/miss/invalidation, and warm-up calls.
- [ ] Run focused tests and verify failures expose the absent semantics.
- [ ] Implement shaping and caching in the official service/repository and call warm-up through the service.
- [ ] Run fund-flow API, service, repository, and collector tests.

### Task 4: Hot-Board Legacy Response Parity

**Files:**
- Modify: `src/stock_lab/modules/emotion/service.py`
- Modify: `实时监控/热门板块情绪.py`
- Modify: `tests/unit/modules/emotion/test_repository.py`
- Create: `tests/unit/compatibility/test_hot_board_wrapper.py`

**Interfaces:**
- Produces: canonical `recent_strength`, state-rank sorting, and `methodology` fields from `EmotionService.hot_board_emotion()`.
- Produces: legacy response keys including `近期强度` and complete `数据口径` after compatibility translation.

- [ ] Add a three-session weighted-strength fixture with literal expected value and complete methodology assertions.
- [ ] Run the tests and verify fields and ordering are absent.
- [ ] Implement weighted `0.2/0.3/0.5` recent strength, legacy state ranking, and all prior methodology/data-scope definitions.
- [ ] Run emotion and compatibility tests.

### Task 5: Strong Wrapper Contracts and Final Verification

**Files:**
- Modify: `tests/test_cutover_contracts.py`
- Modify: compatibility wrappers only where the stronger contract finds ownership leakage
- Modify: cutover documentation if behavior descriptions changed

**Interfaces:**
- Produces: AST enforcement against official `utils` imports and wrapper Redis/DB/network/route/browser/algorithm behavior.

- [ ] Add AST checks for forbidden official roots, wrapper persistence/network attributes, route decorators, infrastructure constructors, algorithmic loops/comprehensions, and non-forwarding control flow.
- [ ] Run the contract test and verify current wrappers/official imports fail for the expected reasons.
- [ ] Reduce violating wrappers or move composition into official runtime factories until contracts pass.
- [ ] Run full pytest, compileall, frontend tests/build, and `git diff --check`.
- [ ] Review status/diff/log, exclude `data/`, and commit remediation in new commits.
