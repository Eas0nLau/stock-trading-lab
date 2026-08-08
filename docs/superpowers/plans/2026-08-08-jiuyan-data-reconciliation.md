# 韭研公社数据核对与情绪重算 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 补齐 `jiuyan_actions` 中缺失的旧韭研记录，并使用完整韭研数据重算热门板块情绪。

**Architecture:** 新增一个专用的 `jiuyan_reconciliation` job。它使用数据库 client 的查询和事务能力，对旧表与新表按 `data_id` 做只补缺失的同步；同步完成后通过现有 `run_hot_board_emotion_job` 逐交易日重算 `hot_board_emotion_daily`。默认支持 dry-run 报告，真实写入必须显式执行。

**Tech Stack:** Python 3、SQLAlchemy、MySQL 8、pytest、现有 `stock_lab.modules.market_data` 与 `stock_lab.modules.emotion` 模块。

## Global Constraints

- 只处理 `t_韭研公社异动解析`、`jiuyan_actions` 和依赖它的 `hot_board_emotion_daily`。
- 以 `data_id` 作为韭研记录业务键；只插入旧表有、新表没有的记录。
- 不删除旧表，不覆盖新表已有记录，不执行 `003_drop_legacy_schema.sql`。
- 情绪重算只处理当前交易日和前一交易日都有韭研记录的日期。
- 情绪结果按 `(trade_date, board_name)` upsert；单个日期写入必须具备事务原子性。
- 默认 dry-run；实际补迁和重算通过显式参数开启。

---

### Task 1: Build Jiuyan reconciliation service

**Files:**
- Create: `src/stock_lab/jobs/jiuyan_reconciliation.py`
- Test: `tests/unit/jobs/test_jiuyan_reconciliation.py`

**Interfaces:**
- Produces `JiuyanReconciliationReport` with `source_count`, `target_count`, `missing_count`, `duplicate_source_ids`, `missing_dates`, `recalculated_dates`, and `skipped_dates`.
- Produces `reconcile_jiuyan_data(*, database, write=False, recalculate=False) -> JiuyanReconciliationReport`.
- Uses `database.query(sql, params=..., fetch=True)` for reads and `database.engine.begin()` for writes.

- [ ] **Step 1: Write failing tests for source/target comparison**

  Add fixtures containing old rows with two `data_id` values, target rows containing one of them, and a duplicate source key. Assert the report identifies exactly the missing key and rejects duplicate source keys before writing.

- [ ] **Step 2: Run the focused tests and verify failure**

  Run: `uv run pytest tests/unit/jobs/test_jiuyan_reconciliation.py -q`

  Expected: FAIL because the reconciliation module and report type do not exist.

- [ ] **Step 3: Implement read-only comparison and mapping**

  Query `COUNT(*)`, duplicate source IDs, and the source rows missing from the target with a `NOT EXISTS` predicate. Map legacy columns to canonical columns exactly as `db/migrations/002_migrate_legacy_data.sql`: `date -> trade_date`, `板块 -> board_name`, `板块个股数量 -> board_stock_count`, zero-padded `股票代码 -> stock_code`, and the remaining Jiuyan fields directly.

- [ ] **Step 4: Add idempotent insert behavior**

  When `write=True`, insert only the missing rows inside one transaction using `INSERT INTO jiuyan_actions ... SELECT ... WHERE NOT EXISTS` or an equivalent parameterized insert. Do not update rows already present in `jiuyan_actions`. Re-running the function must report `missing_count == 0` and write no rows.

- [ ] **Step 5: Run the focused tests and verify success**

  Run: `uv run pytest tests/unit/jobs/test_jiuyan_reconciliation.py -q`

  Expected: PASS for missing-row detection, duplicate rejection, field mapping, dry-run behavior, and idempotent write behavior.

### Task 2: Recalculate complete hot-board emotion dates

**Files:**
- Modify: `src/stock_lab/jobs/jiuyan_reconciliation.py`
- Test: `tests/unit/jobs/test_jiuyan_reconciliation.py`

**Interfaces:**
- Consumes `run_hot_board_emotion_job(trade_date, sample_trade_date, repository, analyzer, writer)` from `stock_lab.modules.emotion.jobs`.
- Uses `index_daily` dates to determine adjacent trading days and requires non-empty `jiuyan_actions` for both dates.
- Updates `hot_board_emotion_daily` using the existing emotion job writer contract.

- [ ] **Step 1: Write failing tests for complete-date selection**

  Provide index dates `[20260803, 20260804, 20260805]` and Jiuyan rows only for `20260803` and `20260804`. Assert only `20260804` is eligible, `20260805` is skipped, and the skip report includes the missing source date.

- [ ] **Step 2: Run the focused test and verify failure**

  Run: `uv run pytest tests/unit/jobs/test_jiuyan_reconciliation.py::test_recalculates_only_dates_with_current_and_previous_jiuyan_data -q`

  Expected: FAIL because date selection and recalculation are not implemented.

- [ ] **Step 3: Implement date selection and recalculation**

  Load ordered distinct trading dates from `index_daily`, load distinct dates from `jiuyan_actions`, and form adjacent pairs from the trading calendar. For each pair with both Jiuyan dates present, invoke `run_hot_board_emotion_job(current_date, previous_date, repository=..., writer=...)`. Record successful dates and skipped dates without fabricating emotion rows.

- [ ] **Step 4: Preserve per-date transaction boundaries**

  Ensure the writer passed to each emotion job opens one `engine.begin()` transaction for that date. If a date fails, propagate the error after recording the date and do not continue silently with a partial result.

- [ ] **Step 5: Run emotion job and reconciliation tests**

  Run: `uv run pytest tests/unit/jobs/test_jiuyan_reconciliation.py tests/unit/modules/emotion/test_jobs.py -q`

  Expected: PASS with correct date eligibility, writer calls, upsert keys, skipped-date reporting, and transaction behavior.

### Task 3: Add operational CLI and database verification

**Files:**
- Modify: `src/stock_lab/jobs/jiuyan_reconciliation.py`
- Create: `tests/integration/database/test_jiuyan_reconciliation.py`
- Modify: `docs/database-migrations.md`

**Interfaces:**
- CLI command: `uv run python -m stock_lab.jobs.jiuyan_reconciliation --dry-run`.
- CLI command: `uv run python -m stock_lab.jobs.jiuyan_reconciliation --write --recalculate`.
- The command refuses ambiguous modes, prints a machine-readable summary, and exits non-zero on duplicate source keys, SQL errors, or incomplete write validation.

- [ ] **Step 1: Write failing CLI and SQL-contract tests**

  Assert dry-run is the default, `--write --recalculate` enables both operations, no-write mode does not call the engine transaction, and the verification SQL contains the old/new `data_id` comparison plus canonical emotion table checks.

- [ ] **Step 2: Run the focused tests and verify failure**

  Run: `uv run pytest tests/integration/database/test_jiuyan_reconciliation.py -q`

  Expected: FAIL because the CLI and verification contract do not exist.

- [ ] **Step 3: Implement the CLI and final verification**

  Add `argparse` options `--dry-run`, `--write`, and `--recalculate`; require `--write` for `--recalculate`. Print source/target counts, missing rows, date ranges, recalculated dates, and skipped dates. After writes, re-run the `data_id` difference query and validate no duplicate canonical keys and valid `decision_reasons_json` values.

- [ ] **Step 4: Update migration documentation**

  Document the dry-run command, the explicit write command, required backup/paused-writer preconditions, expected verification output, and the fact that `003_drop_legacy_schema.sql` remains prohibited.

- [ ] **Step 5: Run the complete verification suite**

  Run: `uv run pytest tests/unit/jobs/test_jiuyan_reconciliation.py tests/integration/database/test_jiuyan_reconciliation.py tests/unit/modules/emotion/test_jobs.py tests/integration/database/test_schema_migration.py -q`

  Expected: PASS. Only after this, run the dry-run against the configured MySQL instance, inspect the report, then run the explicit write/recalculation command after backup confirmation.
