# THS Archival Reference Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish official read-only ownership of three imported THS reference tables and prove their migration and legacy-table retirement readiness.

**Architecture:** A focused `stock_lab.modules.ths` package owns frozen canonical models and parameterized reads through the existing injected query callable. SQL migrations remain the only writer; tests enforce the no-write contract, complete imports, parity validation, and absence of runtime legacy THS references.

**Tech Stack:** Python 3.12, dataclasses, pytest, MySQL 8 SQL, Vue/Vite verification

## Global Constraints

- Treat `ths_boards`, `ths_board_constituents`, and `ths_stock_relations` as archived imported reference data.
- Do not add a runtime collector, scheduled job, API, compatibility adapter, or repository write method.
- Use canonical English identifiers and an injected database query callable.
- Preserve the existing untracked `data/` worktree content and unrelated user changes.

---

### Task 1: Read-Only THS Module

**Files:**
- Create: `src/stock_lab/modules/ths/__init__.py`
- Create: `src/stock_lab/modules/ths/models.py`
- Create: `src/stock_lab/modules/ths/repository.py`
- Create: `tests/unit/modules/ths/test_ths_repository.py`

**Interfaces:**
- Consumes: injected callable `query(sql: str, params: tuple | None = None, fetch: bool = False)`
- Produces: frozen `ThsBoard`, `ThsBoardConstituent`, and `ThsStockRelation` dataclasses; `ThsRepository(query)` with `boards(board_type=None)`, `board_constituents(board_code=None, board_type=None, stock_code=None)`, and `stock_relations(stock_code=None)`

- [ ] **Step 1: Write failing repository tests**

Create a recording fake query and tests that assert model instances, canonical table/column names, filters and parameters, deterministic ordering, and no engine or write-like public methods:

```python
repository = ThsRepository(query)
assert repository.boards("concept") == [ThsBoard(**row)]
assert query.calls[-1][1] == ("concept",)
assert "FROM `ths_boards`" in query.calls[-1][0]
assert not hasattr(repository, "upsert_boards")
assert not hasattr(repository, "_engine")
```

- [ ] **Step 2: Run tests and confirm the missing package failure**

Run: `uv run pytest tests/unit/modules/ths/test_ths_repository.py -q`

Expected: collection fails with `ModuleNotFoundError: No module named 'stock_lab.modules.ths'`.

- [ ] **Step 3: Implement frozen models and explicit read queries**

Define model fields exactly from migration `001`: seven data fields plus `updated_at` for boards and constituents, and seven data fields plus `updated_at` for relations. Build SQL from fixed table/column constants, append only fixed filter clauses, pass values as tuples, request `fetch=True`, and instantiate each dataclass from `dict(row)`.

- [ ] **Step 4: Run focused repository tests**

Run: `uv run pytest tests/unit/modules/ths/test_ths_repository.py -q`

Expected: all THS repository tests pass.

### Task 2: Migration And Legacy Contracts

**Files:**
- Modify: `db/migrations/002_migrate_legacy_data.sql`
- Modify: `tests/integration/database/test_schema_migration.py`
- Create: `tests/test_ths_contracts.py`

**Interfaces:**
- Consumes: the three legacy-to-English pairs in `db/schema_mapping.json`
- Produces: row-count validation result rows named `ths_boards`, `ths_board_constituents`, and `ths_stock_relations`; static source contracts for complete migration and no runtime legacy references

- [ ] **Step 1: Add failing migration and source contract tests**

Assert each THS `INSERT` and `SELECT` contains every target/source column in matching order, each table has a row-count validation query, and runtime source paths contain none of:

```python
LEGACY_THS_TABLES = (
    "t_同花顺板块列表",
    "t_同花顺板块成分股",
    "t_同花顺股票板块概念对应关系",
)
```

Scan active Python and SQL outside `db/migrations`, `init`, docs, tests, `.git`, `.venv`, `data`, and generated caches so migration definitions and historical documentation remain permitted.

- [ ] **Step 2: Run contract tests and confirm missing validations**

Run: `uv run pytest tests/integration/database/test_schema_migration.py tests/test_ths_contracts.py -q`

Expected: migration validation assertions fail because `002_migrate_legacy_data.sql` has no THS parity queries.

- [ ] **Step 3: Add all three SQL parity queries**

Append one explicit source/target `COUNT(*)` query for each THS pair after the existing validation queries, preserving the import statements as the only population mechanism.

- [ ] **Step 4: Run migration and source contracts**

Run: `uv run pytest tests/integration/database/test_schema_migration.py tests/test_ths_contracts.py -q`

Expected: all selected tests pass.

### Task 3: Ownership And Retirement Documentation

**Files:**
- Modify: `README.md`
- Modify: `docs/architecture.md`
- Modify: `docs/migration.md`
- Modify: `docs/database-migrations.md`
- Modify: `db/migrations/README.md`

**Interfaces:**
- Consumes: ownership and lifecycle decisions established by Tasks 1 and 2
- Produces: consistent operator and contributor guidance for import-only archival data and legacy-table retirement

- [ ] **Step 1: Update all requested documentation surfaces**

Document that `stock_lab.modules.ths` owns read-only access; the application has no producer/consumer and no collector should be inferred; `002` is the sole import path; the three old THS tables may be dropped after row-count and sampled-data parity; and the English tables remain archived/import-only afterward. Correct README statements that currently imply a live THS updater or active THS runtime use.

- [ ] **Step 2: Verify terminology and references**

Run: `rg -n "THS|同花顺|ths_" README.md docs/architecture.md docs/migration.md docs/database-migrations.md db/migrations/README.md`

Expected: each requested document clearly describes archival ownership without claiming an active collector.

### Task 4: Full Verification And Commit

**Files:**
- Review: all changed files

**Interfaces:**
- Consumes: Tasks 1-3
- Produces: verified commit containing only intended THS ownership changes

- [ ] **Step 1: Run backend tests and compilation**

Run: `uv run pytest -q`

Run: `uv run python -m compileall -q src tests`

Expected: both commands exit zero.

- [ ] **Step 2: Run frontend tests and production build**

Run: `npm --prefix front test`

Run: `npm --prefix front run build`

Expected: frontend tests pass and Vite completes a production build.

- [ ] **Step 3: Review diff integrity**

Run: `git diff --check`

Run: `git status --short`

Run: `git diff -- README.md docs/architecture.md docs/migration.md docs/database-migrations.md db/migrations src/stock_lab/modules/ths tests`

Expected: no whitespace errors; only intended files plus pre-existing untracked `data/` appear.

- [ ] **Step 4: Commit the complete change**

Stage only the THS module, tests, SQL, requested docs, design, and plan. Commit with:

```text
feat: establish read-only THS data ownership
```

- [ ] **Step 5: Confirm final status and commit**

Run: `git status --short`

Run: `git log -1 --oneline`

Expected: the requested files are committed; pre-existing untracked `data/` remains untouched.
