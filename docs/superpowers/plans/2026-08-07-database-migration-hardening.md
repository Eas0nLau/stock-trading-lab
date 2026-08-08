# Database Migration Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make all database migration and clean-initialization paths fail closed, rerunnable, convergent, and statically verifiable without accessing a real database.

**Architecture:** MySQL 8 stored procedures provide executable assertions through `SIGNAL SQLSTATE '45000'`; durable migration and validation tables provide the state consumed by the destructive guard. Python static contract tests parse DDL, copy statements, gates, and ordering, while the clean initializer embeds the canonical DDL directly.

**Tech Stack:** MySQL 8 SQL, Python 3.12, pytest, Docker Compose, npm/Vite

## Global Constraints

- Do not access a user database or use project database credentials.
- Invalid non-null legacy JSON must abort with table, column, and key diagnostics before copying.
- All 16 mappings must have row, distinct-key, and applicable date, aggregate, and JSON gates.
- `002` is recorded only after every gate succeeds; `003` drops nothing until prerequisites pass.
- `init/stock_trading_lab_v2.sql` must be self-contained and contain only English schema identifiers.

---

### Task 1: Static Migration Contracts

**Files:**
- Modify: `tests/integration/database/test_schema_migration.py`

**Interfaces:**
- Consumes: `db/schema_mapping.json` and all SQL artifacts as text
- Produces: parser helpers and assertions defining migration behavior without a database connection

- [x] **Step 1: Add parser tests for all canonical tables and insert statements**

Parse `CREATE TABLE`, `INSERT INTO ... SELECT ... ON DUPLICATE KEY UPDATE`, and validation calls. Assert every copied non-key target column appears in the update list.

- [x] **Step 2: Add ordering and fail-closed tests**

Assert `001` validates before recording, `002` preflights before copying and validates before recording, and `003` calls its prerequisite guard before the first `DROP TABLE`.

- [x] **Step 3: Add initializer and retirement tests**

Assert the current initializer contains `CREATE DATABASE`, `USE`, full DDL, no `SOURCE`, and no legacy identifiers; assert the old filename no longer exists and the renamed artifact is visibly marked historical.

- [x] **Step 4: Run the focused tests and confirm failures**

Run: `uv run pytest tests/integration/database/test_schema_migration.py -q`
Expected: failures identify incomplete update lists, missing gates/guards, delegated initialization, and active legacy filename.

### Task 2: Restartable Canonical Schema

**Files:**
- Modify: `db/migrations/001_create_english_schema.sql`

**Interfaces:**
- Produces: `schema_migrations`, `migration_validations`, 16 canonical tables, and successful version `001_create_english_schema`

- [x] **Step 1: Make every create resumable**

Use `CREATE TABLE IF NOT EXISTS` for state and canonical tables, preserving canonical DDL.

- [x] **Step 2: Add executable compatibility validation**

Create a temporary procedure that checks expected table/column signatures and key/index contracts in `information_schema`, signaling a contextual error on mismatch.

- [x] **Step 3: Record version idempotently after validation**

Use `INSERT ... ON DUPLICATE KEY UPDATE applied_at = applied_at` only after the validation procedure returns successfully.

- [x] **Step 4: Run focused schema tests**

Run: `uv run pytest tests/integration/database/test_schema_migration.py -q`
Expected: `001` contract tests pass; `002`, `003`, and initializer tests remain failing.

### Task 3: Convergent Copy And Executable Parity Gates

**Files:**
- Modify: `db/migrations/002_migrate_legacy_data.sql`

**Interfaces:**
- Consumes: legacy tables and canonical schema from `001`
- Produces: fully refreshed canonical rows, `002_parity_v1/succeeded`, and version `002_migrate_legacy_data`

- [x] **Step 1: Add prerequisite and JSON/broker preflight procedures**

Check `001`; reject invalid JSON with source table, column, and key; reject broker statistic values that cannot be normalized without truncation.

- [x] **Step 2: Normalize valid structured values**

Cast valid source JSON to JSON. Normalize broker counts, percentages, comma-separated amounts, and `万`/`亿` units with guarded expressions that preserve nulls.

- [x] **Step 3: Refresh every copied non-key column**

Expand each `ON DUPLICATE KEY UPDATE` list to include all copied non-key columns in target-column order.

- [x] **Step 4: Add all 16 executable parity validations**

For each mapping compare source rows with target rows and source distinct mapped keys with target distinct keys. Add date range checks where a date is mapped, selected `DECIMAL` casts for aggregate comparisons, and JSON validity checks for JSON targets.

- [x] **Step 5: Gate success recording**

Clear stale `002_parity_v1` status at start. Run all parity checks via a procedure, write `succeeded`, then idempotently record `002`; any signal leaves both success records absent.

- [x] **Step 6: Run focused migration tests**

Run: `uv run pytest tests/integration/database/test_schema_migration.py -q`
Expected: `001` and `002` contracts pass; `003` and initializer tests remain failing.

### Task 4: Guard Destructive Finalization

**Files:**
- Modify: `db/migrations/003_drop_legacy_schema.sql`

**Interfaces:**
- Consumes: migration versions `001`, `002` and validation `002_parity_v1/succeeded`
- Produces: dropped legacy tables and idempotent version `003_drop_legacy_schema`

- [x] **Step 1: Add prerequisite procedure before drops**

Signal unless both required versions and the exact successful validation version/status exist.

- [x] **Step 2: Preserve fail-closed ordering and rerun semantics**

Call and remove the guard before disabling foreign keys or dropping a table; record `003` idempotently afterward.

- [x] **Step 3: Run focused migration tests**

Run: `uv run pytest tests/integration/database/test_schema_migration.py -q`
Expected: migration contracts pass; initializer tests remain failing.

### Task 5: Clean Initialization And Setup Alignment

**Files:**
- Modify: `init/stock_trading_lab_v2.sql`
- Rename: `init/stock_trading_lab.sql` to `init/LEGACY_stock_trading_lab_chinese_schema.sql`
- Modify: `init/docker/mysql/docker-compose.yml`
- Modify: `README.md`
- Modify: `环境安装.md`
- Modify: `docs/database-migrations.md`
- Modify: `db/migrations/README.md`
- Modify: `docs/architecture.md`
- Modify: `docs/migration.md`

**Interfaces:**
- Produces: self-contained clean database bootstrap and unambiguous operational instructions

- [x] **Step 1: Embed complete canonical schema in initializer**

Add `CREATE DATABASE IF NOT EXISTS stock_trading_lab`, `USE stock_trading_lab`, state tables, and all 16 canonical table definitions with no `SOURCE` or migration copy/drop logic.

- [x] **Step 2: Retire the historical initializer**

Rename it and prepend a warning that it is archival legacy Chinese-schema DDL and must not be used for current setup.

- [x] **Step 3: Align optional Docker initialization**

Set `MYSQL_DATABASE=stock_trading_lab` and document/comment an optional read-only mount of `stock_trading_lab_v2.sql` into `/docker-entrypoint-initdb.d/001-stock-trading-lab.sql`.

- [x] **Step 4: Update all setup and migration documentation**

Document clean install versus legacy upgrade, executable gate behavior, status/version prerequisites, invalid JSON aborts, initializer retirement, and no automatic `003` execution.

- [x] **Step 5: Run focused migration tests**

Run: `uv run pytest tests/integration/database/test_schema_migration.py -q`
Expected: PASS.

### Task 6: Full Verification And Commit

**Files:**
- Verify all changed files

**Interfaces:**
- Produces: evidence that the repository and frontend remain buildable and only intended files are committed

- [x] **Step 1: Run full Python tests and compilation**

Run: `uv run pytest -q`
Run: `uv run python -m compileall -q src tests app.py front_run.py`
Expected: both exit zero.

- [x] **Step 2: Run frontend verification**

Run in `front`: `npm test -- --run`
Run in `front`: `npm run build`
Expected: both exit zero.

- [x] **Step 3: Review SQL and repository diff**

Run: `git diff --check`
Run: `git status --short`
Run: `git diff --stat`
Expected: no whitespace errors; only intended migration, initialization, test, and documentation files are modified; existing untracked `data/` remains untouched.

- [x] **Step 4: Commit implementation**

Stage only intended files and commit with `fix: harden database migrations`.
