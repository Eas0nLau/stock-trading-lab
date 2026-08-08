# 最终旧库数据补迁与删表 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 16 张旧表单向 upsert 到英文表，保留英文表独有数据，通过实时包含校验后删除旧表。

**Architecture:** 新增 `004_upsert_legacy_data.sql`，复用 `002` 的字段转换但把校验语义改为“目标包含源”，并将结果记录为 `004_legacy_containment_v1`。修改 `003_drop_legacy_schema.sql` 只接受最新 `004` 成功状态；应用代码在删表前移除最后一个旧表运行时读取。数据库操作严格按冻结、备份、补迁、校验、删表、删除后验证的顺序执行。

**Tech Stack:** MySQL 8、Python 3、SQLAlchemy、pytest、mysqldump、现有 `stock_lab` 数据库基础设施。

## Global Constraints

- 旧表有、新表没有的业务键插入新表。
- 两边业务键相同的记录，以旧表映射字段更新新表。
- 新表有、旧表没有的记录必须完整保留。
- 禁止对英文表执行 `DELETE`、`TRUNCATE`、全表替换或先清空后导入。
- 任何包含校验、唯一键、JSON、外键或行数保护失败都不得执行删表。
- 不使用 Redis 作为补迁来源。
- 删除旧表前必须停止所有写入方并创建新的完整备份。
- 未获得明确提交授权时不创建 Git 提交。

---

### Task 1: Add single-direction legacy upsert migration

**Files:**
- Create: `db/migrations/004_upsert_legacy_data.sql`
- Modify: `tests/integration/database/test_schema_migration.py`

**Interfaces:**
- Produces migration version `004_upsert_legacy_data`.
- Produces validation version `004_legacy_containment_v1` with `status` values `running`, `failed`, or `succeeded`.
- Consumes the 16 mappings from `db/schema_mapping.json` and the exact field conversions in `002_migrate_legacy_data.sql:187-272`.

- [ ] **Step 1: Write failing static migration tests**

  Add tests asserting that `004_upsert_legacy_data.sql`:

  ```python
  assert "004_legacy_containment_v1" in sql
  assert sql.count("INSERT INTO `") >= 16
  assert "ON DUPLICATE KEY UPDATE" in sql
  assert not re.search(r"\b(?:DELETE\s+FROM|TRUNCATE|DROP\s+TABLE)\b", sql, re.I)
  for source, mapping in schema_mapping["tables"].items():
      assert f"FROM `{source}`" in sql
      assert f"INSERT INTO `{mapping['table']}`" in sql
  ```

  Assert that migration state is written as `running` before DML, `failed` from an exception handler, and `succeeded` only after all containment gates.

- [ ] **Step 2: Run tests and verify RED**

  Run: `uv run pytest --import-mode=importlib tests/integration/database/test_schema_migration.py -q`

  Expected: FAIL because `004_upsert_legacy_data.sql` does not exist.

- [ ] **Step 3: Implement all 16 upserts**

  Copy the 16 `INSERT ... SELECT ... ON DUPLICATE KEY UPDATE` statements from `002_migrate_legacy_data.sql:187-272` without changing key normalization or unit conversion. Do not copy the equality-based parity procedure from `002`. Wrap DML in one transaction with an SQL exception handler that rolls back and records `004_legacy_containment_v1/failed`.

- [ ] **Step 4: Add preservation snapshots**

  Before DML, create temporary tables containing each target table's pre-migration primary/business keys and exact row count. After DML, assert:

  ```sql
  SELECT COUNT(*) FROM target_after >= target_count_before;
  SELECT COUNT(*)
  FROM target_keys_before b
  LEFT JOIN target_after t ON t.business_key = b.business_key
  WHERE t.business_key IS NULL;
  -- result must be 0
  ```

  Use the canonical keys declared in `tests/integration/database/test_schema_migration.py:MIGRATIONS`; temporary snapshots must be dropped by both success and failure cleanup paths.

- [ ] **Step 5: Run migration contract tests**

  Run: `uv run pytest --import-mode=importlib tests/integration/database/test_schema_migration.py -q`

  Expected: PASS, with all 16 source/target mappings covered and no target-table deletion SQL.

### Task 2: Add fresh containment and field-parity gates

**Files:**
- Modify: `db/migrations/004_upsert_legacy_data.sql`
- Modify: `db/migrations/001_create_english_schema.sql`
- Modify: `init/stock_trading_lab_v2.sql`
- Modify: `tests/integration/database/test_schema_migration.py`

**Interfaces:**
- Produces one gate result per mapping: source rows, source distinct keys, missing target keys, mapped-field mismatch count, target rows before/after, and lost pre-existing target keys.
- Produces `migration_validation_tables`, keyed by `(validation_version, source_table)`, for durable table-level evidence.
- `004` succeeds only when every source key exists in the target and every mapped field compares null-safely equal.

- [ ] **Step 1: Write failing gate tests**

  Assert every mapping name appears in a call to the containment procedure. Assert the procedure rejects:

  ```text
  source_rows != source_distinct_keys
  missing_target_keys != 0
  mapped_field_mismatches != 0
  target_rows_after < target_rows_before
  lost_preexisting_target_keys != 0
  invalid_target_json != 0
  ```

- [ ] **Step 2: Run the focused test and verify RED**

  Run: `uv run pytest --import-mode=importlib tests/integration/database/test_schema_migration.py -q`

  Expected: FAIL because full mapped-field containment gates are absent.

- [ ] **Step 3: Implement null-safe field comparisons**

  For each mapping, join source to target using its transformed canonical key and count rows where any mapped target field differs using MySQL `<=>`. Use explicit `CONVERT(... USING utf8mb4) COLLATE utf8mb4_bin` for cross-collation text keys. Include every target column listed in the corresponding `INSERT` statement; do not reduce validation to aggregate sums.

- [ ] **Step 4: Persist structured gate evidence**

  Add this migration-state table to `001`, `stock_trading_lab_v2.sql`, and `004`:

  ```sql
  CREATE TABLE IF NOT EXISTS `migration_validation_tables` (
    `validation_version` varchar(64) NOT NULL,
    `source_table` varchar(128) NOT NULL,
    `target_table` varchar(128) NOT NULL,
    `source_rows` bigint NOT NULL,
    `source_distinct_keys` bigint NOT NULL,
    `missing_target_keys` bigint NOT NULL,
    `mapped_field_mismatches` bigint NOT NULL,
    `target_rows_before` bigint NOT NULL,
    `target_rows_after` bigint NOT NULL,
    `lost_preexisting_target_keys` bigint NOT NULL,
    `validated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`validation_version`, `source_table`)
  ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
  ```

  Persist exactly 16 rows for `004_legacy_containment_v1`. Keep `migration_validations.details` as a short summary that fits its existing `varchar(512)` contract.

- [ ] **Step 5: Run migration tests**

  Run: `uv run pytest --import-mode=importlib tests/integration/database/test_schema_migration.py -q`

  Expected: PASS for all preservation and containment contract checks.

### Task 3: Retire runtime legacy-table access and harden deletion guard

**Files:**
- Delete: `src/stock_lab/jobs/jiuyan_reconciliation.py`
- Delete: `tests/unit/jobs/test_jiuyan_reconciliation.py`
- Delete: `tests/integration/database/test_jiuyan_reconciliation_contract.py`
- Modify: `tests/test_cutover_contracts.py`
- Modify: `tests/test_research_contracts.py`
- Modify: `db/migrations/003_drop_legacy_schema.sql`
- Modify: `docs/database-migrations.md`

**Interfaces:**
- Removes the only sanctioned runtime read of `t_韭研公社异动解析`.
- `003` requires versions `001_create_english_schema`, `002_migrate_legacy_data`, and `004_upsert_legacy_data` plus `004_legacy_containment_v1/succeeded`.
- `003` also requires exactly 16 passing rows in `migration_validation_tables` for the same validation version.

- [ ] **Step 1: Write failing cutover and guard tests**

  Remove the Jiuyan migration allowlists and assert no Python file under `src/stock_lab` references any legacy table. Update `003` tests to require the `004` migration and fresh validation marker before the first `DROP TABLE`.

- [ ] **Step 2: Run tests and verify RED**

  Run: `uv run pytest --import-mode=importlib tests/test_cutover_contracts.py tests/test_research_contracts.py tests/integration/database/test_schema_migration.py -q`

  Expected: FAIL while the reconciliation job and old `003` guard remain.

- [ ] **Step 3: Remove the runtime reconciliation job**

  Delete the job and its dedicated tests. Keep emotion recalculation through `stock_lab.modules.emotion.jobs.run_hot_board_emotion_job`; no normal application path may query the legacy Jiuyan table.

- [ ] **Step 4: Harden `003`**

  Change the guard to require exactly these successful prerequisites:

  ```sql
  version IN (
    '001_create_english_schema',
    '002_migrate_legacy_data',
    '004_upsert_legacy_data'
  )
  validation_version = '004_legacy_containment_v1'
  status = 'succeeded'
  ```

  Also require 16 detail rows with `source_rows=source_distinct_keys`, zero missing/mismatch/lost-key counts, and `target_rows_after>=target_rows_before`.

  Keep the existing 16-table drop list. Do not add canonical tables.

- [ ] **Step 5: Run full code verification**

  Run: `uv run pytest --import-mode=importlib -q`

  Expected: PASS with no active legacy-table reference outside SQL migration files.

### Task 4: Freeze writers and create a verified backup

**Files:**
- Runtime artifact outside Git: `backup/stock_trading_lab_before_legacy_drop_<timestamp>.sql`

**Interfaces:**
- Consumes current MySQL settings without printing the password.
- Produces a restorable full database dump before any production DML.

- [ ] **Step 1: Stop all application writers**

  Stop backend port `8527`, frontend port `9527`, daily-update workers, premarket jobs, browser collectors, and any project Python process that can write MySQL. Record stopped process IDs. Do not kill unrelated MySQL or Redis services.

- [ ] **Step 2: Verify the freeze**

  Query exact row counts for all 16 source and target tables twice, at least 10 seconds apart. Expected: every count is unchanged. If any count changes, identify and stop the remaining writer before continuing.

- [ ] **Step 3: Create full backup**

  Run `mysqldump` with `--single-transaction --routines --triggers --events --hex-blob --set-gtid-purged=OFF --result-file=<absolute backup path>`. Supply credentials through process environment or a temporary protected defaults file; never place the password in command output or Git.

- [ ] **Step 4: Verify backup artifact**

  Require a successful exit code, non-zero file size, and presence of `CREATE TABLE` statements for both `stock_daily` and `daily_quotes`. Record path, size, and SHA-256 checksum. Do not proceed if verification fails.

### Task 5: Execute `004` and verify target preservation

**Files:**
- Execute: `db/migrations/004_upsert_legacy_data.sql`

**Interfaces:**
- Produces current `004_upsert_legacy_data` and `004_legacy_containment_v1/succeeded` records.
- Must preserve every pre-existing canonical business key.

- [ ] **Step 1: Capture pre-migration canonical inventory**

  Save exact row counts, min/max dates, distinct business-key counts, and SHA-256 hashes of sorted target-only business keys for all 16 canonical tables. At minimum record the existing `hot_board_emotion_daily` target-only rows and all canonical daily-quote keys.

- [ ] **Step 2: Execute `004` once**

  Run the SQL through the configured MySQL 8 client. Capture all gate output and require exit code zero.

- [ ] **Step 3: Verify known gaps and full containment**

  Require:

  ```text
  index_market_breadth source keys missing = 0
  index_emotion_daily source keys missing = 0
  securities source keys missing = 0
  daily_quotes source keys missing = 0
  all 16 mapped-field mismatch counts = 0
  all 16 lost target-only key counts = 0
  ```

- [ ] **Step 4: Verify preserved canonical facts**

  Compare pre/post target-only key hashes and row counts. Expected: no target row count decreases and no pre-existing key disappears. Specifically confirm `hot_board_emotion_daily` retains all rows added by the 2026-08-08 recalculation.

- [ ] **Step 5: Run full tests before deletion**

  Run: `uv run pytest --import-mode=importlib -q`

  Expected: PASS. If not, stop with old tables intact.

### Task 6: Delete legacy tables and verify the cutover

**Files:**
- Execute: `db/migrations/003_drop_legacy_schema.sql`

**Interfaces:**
- Deletes exactly the 16 legacy tables in `db/schema_mapping.json`.
- Records migration version `003_drop_legacy_schema` only after all drops succeed.

- [ ] **Step 1: Reconfirm destructive preconditions**

  Confirm backup path/checksum, stopped writers, successful `004` state, zero containment failures, clean Git diff for migration code, and passing full tests.

- [ ] **Step 2: Execute guarded `003` once**

  Run with the MySQL client and capture output. Do not interrupt the process because MySQL DDL is not transactionally rollbackable.

- [ ] **Step 3: Verify exact deletion set**

  Query `information_schema.TABLES`. Expected: all 16 source names from `schema_mapping.json` are absent, all 16 canonical targets and migration-state tables are present.

- [ ] **Step 4: Verify canonical data unchanged**

  Compare every canonical row count, distinct business-key count, date range, and preserved-key hash against the post-`004` inventory. Expected: exact equality.

- [ ] **Step 5: Verify application and Redis reconstruction**

  Run the full test suite, application startup check, representative emotion/fund-flow/strategy-pick API reads, and cache rebuild/read paths. Redis loss or cache deletion must not cause loss of canonical facts.

- [ ] **Step 6: Keep services stopped on failure**

  If any deletion-side verification fails, do not restart writers. Restore the complete database from the verified backup, rerun post-restore checks, and only then restart services.
