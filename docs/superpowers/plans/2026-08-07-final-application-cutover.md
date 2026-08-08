# Final Application Cutover Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete official English ownership of active collectors, emotion algorithms, V1 persistence consumers, and compatibility boundaries without executing migration `003`.

**Architecture:** Source-specific network and browser mechanics are lazy injected infrastructure adapters; domain collectors normalize records and persist through canonical repositories. Official jobs import only `stock_lab` modules, while documented legacy script paths forward to official English APIs and contain no routes, algorithms, storage fallbacks, or substantial collection logic.

**Tech Stack:** Python 3.12, FastAPI, Redis, SQLAlchemy, pandas, DrissionPage, pytest, Vue 3, Vite

## Global Constraints

- Preserve documented direct script paths only as thin forwarding wrappers.
- Remove dormant old REST routes.
- Remove legacy Redis reads and writes after all in-repository consumers switch.
- Old table compatibility must use English repositories and services and cannot query legacy tables.
- Tests must not use real network or database services.
- Do not execute `003_drop_legacy_schema.sql`.
- Leave the pre-existing untracked `data/` directory untouched.

---

### Task 1: Market-Data and Jiuyan Ownership

**Files:**
- Create: `src/stock_lab/infrastructure/market_data/akshare.py`
- Create: `src/stock_lab/infrastructure/market_data/tushare.py`
- Create: `src/stock_lab/infrastructure/browser/client.py`
- Create: `src/stock_lab/modules/market_data/collectors.py`
- Create: `src/stock_lab/modules/market_data/jiuyan.py`
- Modify: `src/stock_lab/jobs/daily_update.py`
- Modify: `task/data_sources.py`
- Modify: `task/_5_韭研公社异动.py`
- Test: `tests/unit/modules/market_data/test_collectors.py`
- Test: `tests/test_jiuyan_task.py`
- Test: `tests/unit/jobs/test_daily_update.py`

**Interfaces:**
- Produces: `MarketDataCollector.trading_dates(limit)`, `update_index_daily(start_date, end_date)`, `update_securities()`, `update_daily_quotes(start_date, end_date)`.
- Produces: `JiuyanCollector.collect(trade_date)` and `parse_jiuyan_response(response, trade_date)`.
- Consumes: `MarketDataRepository`, lazy injected source callables, and an injected browser page factory.

- [ ] **Step 1: Add failing ownership and behavior tests**

Assert injected frames normalize into canonical repository calls, Jiuyan retries incomplete payloads and upserts `jiuyan_actions`, daily-update defaults resolve official collectors, and task modules export only forwarding callables.

- [ ] **Step 2: Run the focused tests and confirm reverse-import failures**

Run: `uv run pytest tests/unit/modules/market_data/test_collectors.py tests/test_jiuyan_task.py tests/unit/jobs/test_daily_update.py -q`

- [ ] **Step 3: Implement official source adapters and collectors**

Keep AkShare, Tushare, and browser imports inside adapter methods. Move normalization, retry, rate limiting, and persistence orchestration unchanged behind the interfaces above. Compose defaults lazily from configured infrastructure resources.

- [ ] **Step 4: Replace task implementations with forwarding wrappers**

Preserve `交易日期列表`, `更新股票基础信息`, `更新股票日线`, `更新指数日线`, `解析异动响应`, and `韭研公社异动采集` as direct aliases or one-line calls to official APIs.

- [ ] **Step 5: Run focused tests**

Run: `uv run pytest tests/unit/modules/market_data tests/test_jiuyan_task.py tests/unit/jobs/test_daily_update.py tests/test_task_data_sources.py -q`

### Task 2: Emotion Algorithms and Canonical Hot-Board Compatibility

**Files:**
- Create: `src/stock_lab/modules/emotion/index_cycle.py`
- Create: `src/stock_lab/modules/emotion/hot_board.py`
- Modify: `src/stock_lab/modules/emotion/jobs.py`
- Modify: `src/stock_lab/modules/emotion/service.py`
- Modify: `实时监控/情绪周期.py`
- Modify: `实时监控/热门板块情绪.py`
- Modify: `utils/热门板块情绪算法.py`
- Test: `tests/test_emotion_analysis.py`
- Test: `tests/unit/modules/emotion/test_algorithms.py`
- Test: `tests/unit/modules/emotion/test_jobs.py`

**Interfaces:**
- Produces: `calculate_index_cycle(index_rows, market_rows) -> dict`.
- Produces: `analyze_hot_board_day(...) -> dict` and `HotBoardConfig`.
- Consumes: canonical English rows from `EmotionRepository` and `MarketDataRepository`.

- [ ] **Step 1: Add parity tests around existing algorithm fixtures**

Call the new English functions with canonical records and assert the persisted score components, cycle state, continuation state, summary, and decision reasons match current expected fixtures.

- [ ] **Step 2: Run tests and confirm the new modules are missing**

Run: `uv run pytest tests/test_emotion_analysis.py tests/unit/modules/emotion/test_algorithms.py tests/unit/modules/emotion/test_jobs.py -q`

- [ ] **Step 3: Move algorithms and update jobs**

Translate internal identifiers to English while preserving Chinese display values. Remove runtime imports of `实时监控.情绪周期` and `utils.热门板块情绪算法`; jobs pass canonical records directly and no longer construct legacy-shaped algorithm inputs.

- [ ] **Step 4: Thin compatibility files and remove old routes**

Expose documented Chinese function aliases to English implementations. Delete `注册接口` and legacy path constants. Make `实时监控/热门板块情绪.py` construct `EmotionRepository` and `EmotionService` against canonical tables only.

- [ ] **Step 5: Run emotion and API tests**

Run: `uv run pytest tests/test_emotion_analysis.py tests/test_emotion_pipeline_integration.py tests/unit/modules/emotion tests/api/test_emotion_v1.py -q`

### Task 3: Fund-Flow V1-Only Collector and Consumers

**Files:**
- Create: `src/stock_lab/modules/fund_flow/parsing.py`
- Modify: `src/stock_lab/modules/fund_flow/collector.py`
- Modify: `src/stock_lab/modules/fund_flow/repository.py`
- Delete: `src/stock_lab/modules/fund_flow/legacy_adapter.py`
- Modify: `实时监控/资金流向.py`
- Modify: `实时监控/情绪周期.py`
- Modify: `strategy/20260617_资金流向935回测.py`
- Modify: `src/stock_lab/modules/research/providers.py`
- Test: `tests/unit/modules/fund_flow/test_collector.py`
- Test: `tests/unit/modules/fund_flow/test_fund_flow.py`
- Test: `tests/test_research_families.py`

**Interfaces:**
- Produces: `FundFlowBrowserSource.collect(flow_type) -> list[dict]` and `FundFlowCollector.collect(flow_type) -> dict`.
- Produces: V1-only `FundFlowRepository.history`, `dates`, and `save_history`.
- Consumes: injected page factory, clock, settings, and V1 Redis repository.

- [ ] **Step 1: Change tests to require V1-only keys**

Assert collection writes only `fund_flow:v1:{flow_type}:*`, repository misses do not inspect list/key patterns, emotion and research fixtures use V1 history, and duplicate collection times replace the last V1 snapshot.

- [ ] **Step 2: Run focused tests and observe legacy assumptions fail**

Run: `uv run pytest tests/unit/modules/fund_flow tests/test_research_families.py -q`

- [ ] **Step 3: Move parsing/browser collection and remove fallback adapters**

Move EastMoney response parsing, concept exclusion, scheduling windows, retry behavior, and warm-up to English modules. Rename `save_legacy_snapshot` to `save_snapshot`; remove legacy reader/writer construction and delete `legacy_adapter.py`.

- [ ] **Step 4: Migrate direct consumers and thin wrapper**

Read history through `FundFlowRepository` in emotion/research code. Preserve direct monitor script collection names as one-line wrappers. Remove `/api/zijin` registration, old key helpers, chart cache implementations, and direct Redis access.

- [ ] **Step 5: Run fund-flow, emotion, and research tests**

Run: `uv run pytest tests/unit/modules/fund_flow tests/api/test_fund_flow_v1.py tests/test_emotion_analysis.py tests/test_research_families.py -q`

### Task 4: Strategy-Pick Official Browser Collection

**Files:**
- Create: `src/stock_lab/modules/strategy_pick/parsing.py`
- Modify: `src/stock_lab/modules/strategy_pick/collector.py`
- Modify: `src/stock_lab/modules/strategy_pick/repository.py`
- Modify: `src/stock_lab/modules/strategy_pick/service.py`
- Delete: `src/stock_lab/modules/strategy_pick/legacy_adapter.py`
- Modify: `实时监控/策略选股.py`
- Test: `tests/unit/modules/strategy_pick/test_strategy_pick_collector.py`
- Test: `tests/unit/modules/strategy_pick/test_strategy_pick_repository.py`
- Test: `tests/unit/modules/strategy_pick/test_strategy_pick_contracts.py`

**Interfaces:**
- Produces: `parse_strategy_response(payload) -> list[dict]`, `StrategyPickBrowserSource.collect(strategy)`, and `StrategyPickCollector.run(stop_event)`.
- Consumes: canonical `StrategyPickRepository`, default strategy settings, injected page factory, clock, and sleeper.

- [ ] **Step 1: Add English parsing, retry, scheduling, and V1-only persistence tests**

Assert JSON/JSONP parsing, market inference, concept filtering, event diffs, per-strategy slots, reconnect retries, and absence of `策略选股:*` writes.

- [ ] **Step 2: Run focused tests and confirm official ownership is absent**

Run: `uv run pytest tests/unit/modules/strategy_pick -q`

- [ ] **Step 3: Move collection and scheduling into official modules**

Remove `import_module("实时监控.策略选股")`. Implement browser collection with injected adapters and canonical camelCase snapshots. Make repository methods V1-only with no `write_legacy` switches or legacy reader/writer.

- [ ] **Step 4: Reduce compatibility script and remove old routes**

Keep documented direct collection/monitor names forwarding to the official collector. Delete `/api/strategy-pick` route registration and all direct old Redis operations.

- [ ] **Step 5: Run strategy-pick tests**

Run: `uv run pytest tests/unit/modules/strategy_pick tests/api/test_strategy_pick_v1.py -q`

### Task 5: Dragon-Tiger Source and Cache Adapters

**Files:**
- Create: `src/stock_lab/infrastructure/market_data/dragon_tiger.py`
- Modify: `src/stock_lab/modules/dragon_tiger/collectors.py`
- Modify: `游资溢价分析/采集/龙虎榜数据采集.py`
- Modify: `游资溢价分析/采集/营业部数据采集.py`
- Modify: `游资溢价分析/采集/游资数据采集.py`
- Modify: `游资溢价分析/溢价分析.py`
- Modify: `游资溢价分析/__init__.py`
- Test: `tests/unit/modules/dragon_tiger/test_collectors.py`
- Test: `tests/unit/modules/dragon_tiger/test_compatibility.py`
- Test: `tests/unit/infrastructure/market_data/test_dragon_tiger.py`

**Interfaces:**
- Produces: lazy `DragonTigerHttpSource` page methods and `JsonPageCache.get/set`.
- Consumes: injected HTTP session, filesystem root, clock, and canonical collector/repository functions.

- [ ] **Step 1: Add source URL, cache, lazy import, and wrapper tests**

Use fake sessions and temporary paths; assert no import-time request, stable cache keys, parser inputs, and wrapper-only legacy files.

- [ ] **Step 2: Run focused tests and confirm source adapters are missing**

Run: `uv run pytest tests/unit/modules/dragon_tiger tests/unit/infrastructure/market_data/test_dragon_tiger.py -q`

- [ ] **Step 3: Move HTTP/cache logic and thin legacy files**

Keep source URLs, headers, pagination, retry/error behavior, and JSON cache semantics in the official adapter. Legacy scripts compose and call official collectors only; premium analysis delegates to the English `analyze_broker_premium` API.

- [ ] **Step 4: Run dragon-tiger tests**

Run: `uv run pytest tests/unit/modules/dragon_tiger tests/unit/infrastructure/market_data/test_dragon_tiger.py -q`

### Task 6: English Identifiers and Compatibility Contracts

**Files:**
- Modify: `src/stock_lab/jobs/premarket_summary.py`
- Modify: `src/stock_lab/modules/dragon_tiger/__init__.py`
- Modify: affected official callers under `src/stock_lab`
- Modify: `utils/ini_util.py`
- Create: `tests/test_cutover_contracts.py`
- Modify: existing compatibility tests as needed

**Interfaces:**
- Produces: `write_ini_list(items, output_dir, file_name)` and English premium-analysis exports.
- Consumes: documented wrapper allow-list and source-tree AST.

- [ ] **Step 1: Add contract scans**

Parse official Python files with `ast` and fail on imports rooted at `task`, `实时监控`, `游资溢价分析`, or `utils`; fail on Chinese identifier definitions/exports while allowing strings and source payload keys. Scan active Python for forbidden legacy Redis/table literals. Enforce per-file wrapper line limits and forbidden imports/calls in `task`, `实时监控`, and `游资溢价分析` compatibility allow-lists.

- [ ] **Step 2: Run contract tests and capture every remaining violation**

Run: `uv run pytest tests/test_cutover_contracts.py -q`

- [ ] **Step 3: Rename official identifiers and finish wrappers**

Replace official Chinese names with English names, including INI and premium-analysis APIs. Keep Chinese aliases only in compatibility files where a documented direct script imports them.

- [ ] **Step 4: Run all compatibility and contract tests**

Run: `uv run pytest tests/test_cutover_contracts.py tests/unit/compatibility tests/test_optional_task_modules.py tests/unit/modules/dragon_tiger/test_compatibility.py -q`

### Task 7: Documentation and Full Verification

**Files:**
- Modify: `docs/architecture.md`
- Modify: `docs/migration.md`
- Modify: `docs/database-migrations.md`
- Modify: `db/migrations/README.md`

**Interfaces:**
- Produces: final ownership map and explicit separate-approval status for migration `003`.

- [ ] **Step 1: Update cutover documentation**

Document official collector/algorithm/source ownership, V1-only Redis behavior, canonical hot-board access, wrapper limits, contract scans, and that application blockers are removed while backup/parity/manual approval remain mandatory before `003`.

- [ ] **Step 2: Run the complete Python suite**

Run: `uv run pytest -q`
Expected: all tests pass with no real network or database access.

- [ ] **Step 3: Compile Python sources**

Run: `uv run python -m compileall -q src task 实时监控 游资溢价分析 utils strategy tests`
Expected: exit code 0.

- [ ] **Step 4: Run frontend tests and build**

Run: `npm test` in `front`
Expected: all Node tests pass.

Run: `npm run build` in `front`
Expected: Vite production build succeeds.

- [ ] **Step 5: Run diff and contract checks**

Run: `git diff --check`
Run: `uv run pytest tests/test_cutover_contracts.py -q`
Run: `git status --short`
Expected: no whitespace errors, contracts pass, and only intended files plus untouched `data/` appear.

- [ ] **Step 6: Review and commit**

Inspect `git diff --stat`, `git diff`, and `git log --oneline -10`; stage only intended cutover files and commit with `refactor: complete application cutover`.
