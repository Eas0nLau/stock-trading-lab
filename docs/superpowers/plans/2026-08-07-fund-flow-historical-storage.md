# Fund Flow Historical Storage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Store one year of fund-flow history in MySQL with six-decimal-precision yuan-to-billion normalization, while retaining Redis as a same-day cache and displaying amounts to two decimals.

**Architecture:** MySQL is the authoritative store with `fund_flow_snapshots` and `fund_flow_records`. Redis stores same-day snapshots, date indexes, Top-N matrices, and SSE notifications. A backfill adapter writes daily aggregates from newest to oldest and skips existing canonical snapshots.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy/MySQL 8, redis-py, Vue 3, ECharts, pytest, Node test runner.

## Global Constraints

- `net_inflow_100m` is stored as `DECIMAL(20,6)` in units of 亿元.
- EastMoney source `f62` values in 元 are divided by `100000000` exactly once at the canonical boundary.
- MySQL is the historical source of truth; Redis is a same-day/cache and event layer.
- UI amounts, axis labels, tooltips, and end labels display two decimal places using normal rounding.
- Do not execute `003_drop_legacy_schema.sql`.
- Tests use injected source/database/Redis fakes and do not contact external services.

---

### Task 1: Canonical Fund-Flow Schema And Repository

**Files:**
- Modify: `db/migrations/001_create_english_schema.sql`
- Modify: `init/stock_trading_lab_v2.sql`
- Modify: `src/stock_lab/modules/fund_flow/contracts.py`
- Create: `src/stock_lab/modules/fund_flow/mysql_repository.py`
- Test: `tests/unit/modules/fund_flow/test_mysql_repository.py`
- Test: `tests/unit/modules/fund_flow/test_fund_flow_amounts.py`

**Interfaces:**
- `FundFlowMySQLRepository.save_snapshot(flow_type: str, trade_date: int, collected_at: str, records: list[dict]) -> int`
- `FundFlowMySQLRepository.history(flow_type: str, trade_date: int) -> list[list[dict]]`
- `FundFlowMySQLRepository.dates(flow_type: str) -> list[str]`
- `normalize_net_inflow_100m(value: object, source_unit: str = "wan") -> Decimal`

- [ ] Write tests proving `41113.02` 万元 becomes `Decimal("4.111302")` 亿元, canonical 亿 values are not divided twice, and malformed values fail validation.
- [ ] Write repository tests proving snapshot uniqueness uses flow type/date/time/board code and all amount columns are bound parameters.
- [ ] Add the two English tables with `DECIMAL(20,6)`, canonical indexes, and idempotent upsert constraints to both schema files.
- [ ] Implement the Decimal normalizer and repository transaction/upsert/read methods.
- [ ] Run `uv run pytest -q tests/unit/modules/fund_flow/test_mysql_repository.py tests/unit/modules/fund_flow/test_fund_flow_amounts.py` and verify all tests pass.
- [ ] Commit `feat: add mysql fund flow history storage`.

### Task 2: Historical Backfill And Dual Storage

**Files:**
- Create: `src/stock_lab/jobs/fund_flow_backfill.py`
- Modify: `src/stock_lab/modules/fund_flow/collector.py`
- Modify: `src/stock_lab/modules/fund_flow/service.py`
- Modify: `src/stock_lab/modules/fund_flow/api.py`
- Create: `tests/unit/jobs/test_fund_flow_backfill.py`
- Modify: `tests/unit/modules/fund_flow/test_collector.py`

**Interfaces:**
- `FundFlowDailySource.fetch(flow_type: str, trade_date: int) -> list[dict]`
- `backfill_fund_flow(start_date: int, end_date: int, source, mysql_repository, redis_repository, trading_dates) -> dict`
- `FundFlowService.history()` reads Redis first and falls back to MySQL, then repopulates Redis.

- [ ] Add failing tests for newest-to-oldest daily iteration, one-year date range, skip-existing behavior, unit normalization, failed-date reporting, and no fake empty success.
- [ ] Implement the injected daily-source protocol and an explicit production adapter; a missing/unavailable historical source returns a failed date with the error rather than fabricated data.
- [ ] Update `save_snapshot` to commit MySQL before publishing/saving Redis success state.
- [ ] Backfill current legacy Redis snapshots into MySQL with the one-time 万元-to-亿元 conversion and rebuild V1 Redis cache from MySQL.
- [ ] Add service fallback tests proving Redis loss still returns MySQL history and writes the cache.
- [ ] Run `uv run pytest -q tests/unit/jobs/test_fund_flow_backfill.py tests/unit/modules/fund_flow` and commit `feat: backfill fund flow history into mysql`.

### Task 3: Frontend Precision And Verification

**Files:**
- Modify: `front/src/views/FundFlow.vue`
- Modify: `front/src/modules/fund-flow/normalizers.js`
- Modify: `front/src/modules/fund-flow/normalizers.test.js`
- Modify: `tests/api/test_fund_flow_v1.py`
- Modify: `docs/database-migrations.md`
- Modify: `README.md`

- [ ] Add Node tests for two-decimal formatting of positive, negative, zero, and high-precision values.
- [ ] Use one frontend formatter for list values, ECharts axis, tooltip, and end labels; preserve raw six-decimal values for calculations.
- [ ] Verify API fallback and `top_n` behavior through FastAPI tests.
- [ ] Run `uv run pytest -q`, `npm test`, `npm run build`, and `uv run python -m compileall -q src task utils strategy`.
- [ ] Run MySQL migration/backfill against the configured database only after a fresh `mysqldump`; verify date coverage, row counts, duplicate keys, and amount samples.
- [ ] Commit `fix: format and verify fund flow amounts`.
