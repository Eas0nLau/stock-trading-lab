# Upstream Jiuyan And Emotion Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden Jiuyan collection, add durable per-date completeness and rebuildable INI exports, restore `_5/_8/_9` task surfaces, and provide repairable index/hot-board emotion range backfills without changing canonical formulas.

**Architecture:** Jiuyan parsing, browser lifecycle, export, and persistence coordination are separated into focused modules. MySQL stores both actions and a per-date completeness manifest transactionally. Existing single-date emotion algorithms remain authoritative; new range coordinators resolve canonical trading dates and isolate failures by date.

**Tech Stack:** Python 3.12, DrissionPage adapter, SQLAlchemy/MySQL 8, pandas-free canonical parsing, pathlib, hashlib/JSON, pytest, uv, PowerShell 5.1.

## Global Constraints

- Upstream `_6_同花顺行业和概念.py` is outside this plan and belongs to the next THS subproject.
- Jiuyan defaults are two attempts and one 180-second overall deadline.
- Each attempt creates a fresh page/listener and closes both in `finally`.
- `HumanVerificationRequired` fails immediately and is never retried automatically.
- Jiuyan responses are completely validated before any MySQL write.
- `jiuyan_actions` and `jiuyan_collection_days` commit in the same per-date transaction.
- Pre-migration Jiuyan dates without a complete manifest are unverified and cannot feed new hot-board recalculation.
- MySQL facts commit before INI generation.
- INI failures return `succeeded_with_warnings` and never roll back facts.
- INI files are deterministic rebuildable output, not fact or completion authority.
- Daily update stays single-date; historical work uses explicit range coordinators.
- Canonical index and hot-board emotion formulas remain unchanged.
- Do not copy the upstream ±98.5% limit-threshold bug, fixed-date CLIs, ignored date ranges, infinite browser waits, direct SQL, import-time browser work, unbounded retries, or permanent Redis markers.
- Redis remains only an expiring lock/completion mirror; general `task_runs` authority remains deferred.
- Continue ignoring only the user-approved `output/.gitignore` cutover assertion; every other failure must be fixed.

---

### Task 1: Jiuyan Completeness Manifest Schema And Repository Transaction

**Files:**
- Create: `db/migrations/006_create_jiuyan_collection_days.sql`
- Modify: `init/stock_trading_lab_v2.sql`
- Modify: `src/stock_lab/modules/market_data/repository.py`
- Modify: `tests/integration/database/test_schema_migration.py`
- Create: `tests/unit/modules/market_data/test_jiuyan_repository.py`
- Modify: `docs/database-migrations.md`

**Interfaces:**
- Consumes: canonical Jiuyan action dictionaries and manifest dictionary for one trade date.
- Produces: `MarketDataRepository.replace_jiuyan_actions(trade_date, rows, manifest) -> int`, `jiuyan_actions_for_date(trade_date) -> list[dict]`, `jiuyan_collection_day(trade_date) -> dict | None`, and `latest_complete_jiuyan_date() -> int | None`.

- [ ] **Step 1: Add failing migration contract tests**

Add `JIUYAN_MANIFEST_PATH` and assert the migration creates this exact table contract:

```sql
CREATE TABLE IF NOT EXISTS `jiuyan_collection_days` (
  `trade_date` int NOT NULL,
  `status` varchar(16) NOT NULL,
  `source_board_count` int NOT NULL,
  `source_stock_count` int NOT NULL,
  `accepted_stock_count` int NOT NULL,
  `source_fingerprint` varchar(64) NOT NULL,
  `collected_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`trade_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

The test must also require `006_create_jiuyan_collection_days` in `schema_migrations`, no legacy Chinese table names, and the same table in `init/stock_trading_lab_v2.sql` for fresh installations.

- [ ] **Step 2: Add failing repository transaction tests**

Create a fake SQLAlchemy engine/connection and assert:

```python
count = repository.replace_jiuyan_actions(
    20260806,
    [{
        "data_id": "20260806_hash",
        "trade_date": 20260806,
        "board_name": "机器人",
        "board_stock_count": 12,
        "stock_code": "000001",
        "stock_name": "平安银行",
    }],
    {
        "trade_date": 20260806,
        "status": "complete",
        "source_board_count": 1,
        "source_stock_count": 1,
        "accepted_stock_count": 1,
        "source_fingerprint": "a" * 64,
    },
)

assert count == 1
assert "DELETE FROM `jiuyan_actions` WHERE `trade_date` = :trade_date" in calls[0].sql
assert "INSERT INTO `jiuyan_actions`" in calls[1].sql
assert "INSERT INTO `jiuyan_collection_days`" in calls[2].sql
```

Add tests that manifest/action date mismatch, non-complete status, invalid fingerprint length, and accepted count mismatch raise `DataValidationError` before opening a transaction. Assert a transaction exception prevents later statements.

- [ ] **Step 3: Run schema/repository tests and verify failure**

Run:

```powershell
uv run --frozen pytest -q tests/integration/database/test_schema_migration.py tests/unit/modules/market_data/test_jiuyan_repository.py
```

Expected: FAIL because migration `006` and repository methods do not exist.

- [ ] **Step 4: Add migration and fresh-install schema**

Create `006_create_jiuyan_collection_days.sql` with `SET NAMES utf8mb4`, the table DDL above, and:

```sql
INSERT INTO `schema_migrations` (`version`)
VALUES ('006_create_jiuyan_collection_days')
ON DUPLICATE KEY UPDATE `applied_at` = `applied_at`;
```

Add the same DDL to `init/stock_trading_lab_v2.sql` after `jiuyan_actions`.

- [ ] **Step 5: Implement repository validation and transaction**

Validate rows and manifest before `engine.begin()`. Within one transaction:

```python
connection.execute(
    text("DELETE FROM `jiuyan_actions` WHERE `trade_date` = :trade_date"),
    {"trade_date": trade_date},
)
self._execute_insert(connection, "jiuyan_actions", rows, ("data_id",))
self._execute_insert(
    connection,
    "jiuyan_collection_days",
    [manifest],
    ("trade_date",),
)
persisted_count = connection.execute(
    text(
        "SELECT COUNT(*) FROM `jiuyan_actions` "
        "WHERE `trade_date` = :trade_date"
    ),
    {"trade_date": trade_date},
).scalar_one()
if int(persisted_count) != int(manifest["accepted_stock_count"]):
    raise DataValidationError(
        f"Persisted Jiuyan count mismatch for {trade_date}"
    )
```

`accepted_stock_count` must equal `len(rows)`. Every action's `trade_date` must equal the target. Fingerprint must match `[0-9a-f]{64}`. `status` must be `complete`.

Add read methods using parameterized SQL and English tables only.

- [ ] **Step 6: Run focused tests**

Run:

```powershell
uv run --frozen pytest -q tests/integration/database/test_schema_migration.py tests/unit/modules/market_data/test_jiuyan_repository.py tests/unit/modules/market_data/test_market_data_repository.py
```

Expected: PASS.

- [ ] **Step 7: Document and commit manifest ownership**

Document that `006` runs after `005`, old Jiuyan dates remain unverified until recollected, and no Redis marker substitutes for the manifest. Commit:

```powershell
git add -- "db/migrations/006_create_jiuyan_collection_days.sql" "init/stock_trading_lab_v2.sql" "src/stock_lab/modules/market_data/repository.py" "tests/integration/database/test_schema_migration.py" "tests/unit/modules/market_data/test_jiuyan_repository.py" "docs/database-migrations.md"
git commit -m "feat: add Jiuyan collection manifest"
```

### Task 2: Strict Jiuyan Batch Parsing

**Files:**
- Create: `src/stock_lab/modules/market_data/jiuyan_parsing.py`
- Modify: `src/stock_lab/modules/market_data/jiuyan.py`
- Create: `tests/unit/modules/market_data/test_jiuyan_parsing.py`
- Modify: `tests/test_jiuyan_task.py`

**Interfaces:**
- Consumes: Jiuyan decoded response object and validated `trade_date`.
- Produces: immutable `ParsedJiuyanBatch(rows, legacy_rows, source_board_count, source_stock_count, accepted_stock_count, source_fingerprint)`; `parse_batch(response, trade_date) -> ParsedJiuyanBatch`; compatibility `parse_response(response, trade_date) -> list[dict]`.

- [ ] **Step 1: Add failing grouped-response golden test**

Use a response with top-level date and two boards. Assert:

```python
batch = parse_batch(response, 20260805)

assert batch.source_board_count == 2
assert batch.source_stock_count == 3
assert batch.accepted_stock_count == 2
assert len(batch.rows) == 2
assert batch.rows[0]["stock_code"] == "000001"
assert batch.rows[0]["data_id"].startswith("20260805_")
assert len(batch.rows[0]["data_id"]) <= 64
assert len(batch.source_fingerprint) == 64
assert parse_response(response, 20260805) == list(batch.legacy_rows)
```

The source fingerprint assertion must compare to `sha256(json.dumps(response, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()`.

- [ ] **Step 2: Add failing validation matrix**

Parameterize responses for:

- missing top-level/group date proof;
- mismatched date;
- non-list data;
- empty boards;
- blank board name;
- non-positive reported count;
- non-list group stocks;
- missing stock code/name/action info/range/source code;
- duplicate stock inside one board;
- malformed limit-up time;
- no accepted 9.5-10.2 rows.

Each must raise `IncompleteJiuyanResponse` with a stable reason fragment. Add exact boundary tests for 9.5 and 10.2 and structurally valid filtered rows at 9.49 and 10.21.

- [ ] **Step 3: Run parser tests and verify failure**

Run:

```powershell
uv run --frozen pytest -q tests/unit/modules/market_data/test_jiuyan_parsing.py tests/test_jiuyan_task.py
```

Expected: FAIL because `ParsedJiuyanBatch` and `parse_batch` do not exist and current parsing accepts unverified shapes.

- [ ] **Step 4: Implement parsing module**

Define:

```python
from typing import Sequence


@dataclass(frozen=True)
class ParsedJiuyanBatch:
    rows: Sequence[dict[str, object]]
    legacy_rows: Sequence[dict[str, object]]
    source_board_count: int
    source_stock_count: int
    accepted_stock_count: int
    source_fingerprint: str
```

Use `validated_trade_date`, `normalize_symbol`, `hashlib.sha256`, strict `%Y-%m-%d`/`%Y%m%d` date comparison, and strict `%H:%M` or `%H:%M:%S` time parsing.

Collect date candidates from `response["date"]`, a dictionary-valued
`response["data"]["date"]`, and every grouped row's `date`. Require at least one
candidate and require every candidate to normalize to the requested date. Support
both grouped rows with `list` and flat canonical/Chinese row fixtures, but never
accept a shape without date proof.

Generate canonical IDs with:

```python
identity = f"{trade_date}|{board_name}|{stock_code}"
data_id = f"{trade_date}_{sha256(identity.encode('utf-8')).hexdigest()[:32]}"
```

Every raw stock must validate structurally before the percentage filter is applied. A filtered row contributes to `source_stock_count` but not `accepted_stock_count`.

Move compatibility parsing helpers out of `jiuyan.py`, then re-export `parse_batch`, `parse_response`, `ParsedJiuyanBatch`, and exceptions from `jiuyan.py` so existing imports remain valid.

- [ ] **Step 5: Run parser and compatibility tests**

Run:

```powershell
uv run --frozen pytest -q tests/unit/modules/market_data/test_jiuyan_parsing.py tests/test_jiuyan_task.py
```

Expected: PASS.

- [ ] **Step 6: Commit strict parsing**

```powershell
git add -- "src/stock_lab/modules/market_data/jiuyan_parsing.py" "src/stock_lab/modules/market_data/jiuyan.py" "tests/unit/modules/market_data/test_jiuyan_parsing.py" "tests/test_jiuyan_task.py"
git commit -m "feat: validate complete Jiuyan batches"
```

### Task 3: Fresh-Page Jiuyan Browser Lifecycle

**Files:**
- Create: `src/stock_lab/modules/market_data/jiuyan_source.py`
- Modify: `src/stock_lab/infrastructure/browser/client.py`
- Modify: `src/stock_lab/infrastructure/browser/__init__.py`
- Modify: `src/stock_lab/modules/market_data/jiuyan.py`
- Create: `tests/unit/modules/market_data/test_jiuyan_source.py`
- Modify: `tests/unit/infrastructure/test_browser_client.py`

**Interfaces:**
- Consumes: `page_factory(name, background=True)`, `page_closer(name, page)`, clock, request-slot function, requested date, absolute deadline, and attempt number.
- Produces: `JiuyanBrowserSource.__call__(trade_date, *, deadline, attempt) -> dict`; `close_page(name, page=None) -> None`.

- [ ] **Step 1: Add failing browser cleanup tests**

Build fake pages/listeners and assert success, timeout, navigation failure, decode failure, and slider paths all call:

```python
page.listen.stop()
page_closer(unique_name, page)
```

For two calls, assert different names such as `jiuyan-action-20260805-1-<token>` and `jiuyan-action-20260805-2-<token>`. Assert page navigation/listener timeout never exceeds `deadline - monotonic()`.

Add a test where the clock already reaches the deadline before page creation and require `IncompleteJiuyanResponse("deadline")` without creating a page.

- [ ] **Step 2: Add failing browser registry cleanup test**

Populate `_pages["test"]` with a fake page, call `close_page("test", page)`, and assert the registry entry is removed and `page.close()` is called once. A stale different page argument must not remove a newer registry page.

- [ ] **Step 3: Run source/browser tests and verify failure**

Run:

```powershell
uv run --frozen pytest -q tests/unit/modules/market_data/test_jiuyan_source.py tests/unit/infrastructure/test_browser_client.py
```

Expected: FAIL because unique fresh-page lifecycle and `close_page` do not exist.

- [ ] **Step 4: Implement browser registry cleanup**

In `close_page`, remove the named page only when the stored object is the supplied page or no page argument is provided. Close the selected page outside the registry lock. Ignore close exceptions after removing the stale reference.

- [ ] **Step 5: Implement deadline-bound source**

Use `uuid.uuid4().hex[:8]` in the page name. Before each operation compute:

```python
remaining = deadline - monotonic()
if remaining <= 0:
    raise IncompleteJiuyanResponse(
        f"Jiuyan collection deadline exceeded for {trade_date}"
    )
```

Call `page.get(url, timeout=remaining)`, then inspect slider state. Click `全部异动解析` when present. Iterate `page.listen.steps(timeout=min(15, remaining))`, rechecking verification prompts while packets arrive. Decode JSON/JSONP and return only matching target packets.

In `finally`, best-effort `page.listen.stop()` followed by `page_closer(name, page)`.

Move source-specific constants and helpers from `jiuyan.py` into `jiuyan_source.py`, and re-export compatibility names from `jiuyan.py`.

- [ ] **Step 6: Run source and browser tests**

Run:

```powershell
uv run --frozen pytest -q tests/unit/modules/market_data/test_jiuyan_source.py tests/unit/infrastructure/test_browser_client.py tests/test_jiuyan_task.py
```

Expected: PASS.

- [ ] **Step 7: Commit source reliability**

```powershell
git add -- "src/stock_lab/modules/market_data/jiuyan_source.py" "src/stock_lab/infrastructure/browser/client.py" "src/stock_lab/infrastructure/browser/__init__.py" "src/stock_lab/modules/market_data/jiuyan.py" "tests/unit/modules/market_data/test_jiuyan_source.py" "tests/unit/infrastructure/test_browser_client.py" "tests/test_jiuyan_task.py"
git commit -m "fix: bound Jiuyan browser attempts"
```

### Task 4: Jiuyan Collector With Structured Result

**Files:**
- Modify: `src/stock_lab/modules/market_data/jiuyan.py`
- Create: `tests/unit/modules/market_data/test_jiuyan_collector.py`
- Modify: `tests/test_jiuyan_task.py`

**Interfaces:**
- Consumes: `parse_batch`, response source `(trade_date, deadline, attempt)`, manifest repository transaction, optional exporter, monotonic clock.
- Produces: `JiuyanCollector.collect(trade_date) -> dict` and `collect_jiuyan_actions(trade_date) -> dict` with `status`, `updated`, `trade_date`, `export_paths`, and `warnings`.

- [ ] **Step 1: Add failing retry/deadline/result tests**

Assert ordinary first-attempt failure followed by success uses attempts `[1, 2]` with the same absolute deadline. Assert `HumanVerificationRequired` invokes only attempt 1. Assert exhaustion raises `IncompleteJiuyanResponse` and does not call repository/exporter.

For success, assert repository receives batch rows/manifest before exporter and result equals:

```python
{
    "status": "success",
    "updated": 2,
    "trade_date": 20260805,
    "export_paths": ["board.ini", "all.ini"],
    "warnings": [],
}
```

For exporter failure after repository success, require `status='succeeded_with_warnings'`, `updated=2`, no export paths, and one warning string.

- [ ] **Step 2: Run collector tests and verify failure**

Run:

```powershell
uv run --frozen pytest -q tests/unit/modules/market_data/test_jiuyan_collector.py tests/test_jiuyan_task.py
```

Expected: FAIL because the collector still returns an integer, lacks shared deadline semantics, and writes through old upsert behavior.

- [ ] **Step 3: Implement finite collector coordination**

Constructor defaults:

```python
max_attempts=2
total_timeout_seconds=180
monotonic=time.monotonic
exporter=None
```

Compute one deadline before the loop. Call source with keyword `deadline` and `attempt`. On parsed success, build manifest from the batch and call `replace_jiuyan_actions`. Invoke exporter only after the transaction returns, using `exporter(trade_date, repository=self.repository)`, and convert returned paths to strings in the structured result.

Catch only exporter exceptions into warnings. Re-raise `HumanVerificationRequired`. Log ordinary attempt failures and stop when attempts or deadline are exhausted.

- [ ] **Step 4: Update default composition**

Compose `JiuyanBrowserSource(create_page, close_page)` and the canonical repository through lazy imports. Leave the default exporter unset in this task; Task 5 wires `export_jiuyan_actions` after that service exists. Do not open a browser, database connection, or output file on module import.

- [ ] **Step 5: Run collector tests**

Run:

```powershell
uv run --frozen pytest -q tests/unit/modules/market_data/test_jiuyan_collector.py tests/test_jiuyan_task.py
```

Expected: PASS.

- [ ] **Step 6: Commit structured collection**

```powershell
git add -- "src/stock_lab/modules/market_data/jiuyan.py" "tests/unit/modules/market_data/test_jiuyan_collector.py" "tests/test_jiuyan_task.py"
git commit -m "feat: persist complete Jiuyan collections"
```

### Task 5: Rebuildable Jiuyan INI And Front-Rank Services

**Files:**
- Create: `src/stock_lab/modules/market_data/jiuyan_exports.py`
- Create: `src/stock_lab/jobs/jiuyan_compatibility.py`
- Modify: `src/stock_lab/modules/market_data/jiuyan.py`
- Modify: `task/_5_韭研公社异动.py`
- Create: `tests/unit/modules/market_data/test_jiuyan_exports.py`
- Create: `tests/unit/compatibility/test_jiuyan_task.py`
- Modify: `tests/test_cutover_contracts.py`

**Interfaces:**
- Consumes: repository `jiuyan_actions_for_date`, `jiuyan_collection_day`, and `latest_complete_jiuyan_date`.
- Produces: `export_jiuyan_actions(trade_date, repository=None, output_root=Path("output")) -> list[Path]`, `front_rank_summary(trade_date=None, repository=None) -> dict`, and thin `_5` names/CLI.

- [ ] **Step 1: Add failing export golden tests**

Use committed canonical rows containing normal boards, `公告`, `其他`, `新股`, `ST板块`, duplicate cross-board stocks, consecutive streaks, non-consecutive streaks, and limit-up times.

Assert:

- `ST板块` has no file;
- normal board files sort before special boards;
- duplicate stock appears only in the first board;
- true `2天2板` sorts before `3天2板`, then earlier limit-up time;
- names replace Windows-invalid characters `[<>:"/\\|?*]` with `_`;
- every file uses `index = code,name` and UTF-8;
- all file name is `<unique_count>_全部.ini`;
- stale target-date INI files are removed only after all new temporary files are ready;
- running twice produces byte-identical output and the same path list.

- [ ] **Step 2: Add failing front-rank and wrapper tests**

Require latest complete date lookup, ST exclusion, deterministic board counts, and reason token splitting on `+` with parenthetical text removed.

Monkeypatch private official delegates in `_5` and require `等待请求频率`, `格式化页面日期`, `解析异动响应`, `韭研公社异动采集`, `导出韭研公社异动板块`, and `日内前排` to be one-line forwards. CLI requires explicit `--date` and supports `--export-only` and `--front-rank` modes.

- [ ] **Step 3: Run export/wrapper tests and verify failure**

Run:

```powershell
uv run --frozen pytest -q tests/unit/modules/market_data/test_jiuyan_exports.py tests/unit/compatibility/test_jiuyan_task.py
```

Expected: FAIL because export/front-rank services and restored names do not exist.

- [ ] **Step 4: Implement deterministic exporter**

Generate the complete output set in a temporary sibling directory. After all writes succeed, remove old `.ini` files from the date directory and move the new files with `Path.replace`.

Implement streak parsing with `r"^(\d+)天(\d+)板$"`; true consecutive rows are those where days equal boards. Sort using explicit tuples, never sets or random fallback codes.

- [ ] **Step 5: Implement front-rank service and official CLI**

Return:

```python
{
    "trade_date": 20260805,
    "boards": [{"board_name": "机器人", "stock_count": 3}],
    "reasons": [{"reason": "减速器", "stock_count": 2}],
}
```

`jiuyan_compatibility.run_cli` parses one required date and mutually exclusive `--export-only` / `--front-rank`. Normal mode collects and exports through `collect_jiuyan_actions`.

- [ ] **Step 6: Convert task `_5` to pure forwarding**

Move all CLI and behavior to official modules. Keep task functions as single-return delegates so `WRAPPER_LIMITS` remains valid. Do not restore THS cache methods.

Update `create_default_collector()` to inject `export_jiuyan_actions` lazily now that the exporter exists.

- [ ] **Step 7: Run export, compatibility, and cutover tests**

Run:

```powershell
uv run --frozen pytest -q tests/unit/modules/market_data/test_jiuyan_exports.py tests/unit/compatibility/test_jiuyan_task.py tests/test_jiuyan_task.py tests/test_cutover_contracts.py -k "not output_directory_tracks_only_ignore_policy"
```

Expected: PASS.

- [ ] **Step 8: Commit Jiuyan outputs and compatibility**

```powershell
git add -- "src/stock_lab/modules/market_data/jiuyan_exports.py" "src/stock_lab/modules/market_data/jiuyan.py" "src/stock_lab/jobs/jiuyan_compatibility.py" "task/_5_韭研公社异动.py" "tests/unit/modules/market_data/test_jiuyan_exports.py" "tests/unit/compatibility/test_jiuyan_task.py" "tests/test_cutover_contracts.py" "tests/test_jiuyan_task.py"
git commit -m "feat: restore Jiuyan exports and queries"
```

### Task 6: Emotion Repository Date-Aware Inputs And Completeness

**Files:**
- Modify: `src/stock_lab/modules/emotion/repository.py`
- Modify: `src/stock_lab/modules/emotion/jobs.py`
- Modify: `tests/unit/modules/emotion/test_repository.py`
- Modify: `tests/unit/modules/emotion/test_jobs.py`

**Interfaces:**
- Produces: `trading_dates(start_date=None, end_date=None) -> list[int]`, `previous_trading_date(trade_date) -> int | None`, `index_daily_rows_through(end_date, limit=180)`, `market_breadth_rows_through(end_date, limit=80)`, and `jiuyan_date_complete(trade_date) -> bool`.
- Updates: single-date index/hot-board jobs to use end-date-aware history, strict adjacency, manifest completeness, and main-board/non-ST action filtering.

- [ ] **Step 1: Add failing repository SQL tests**

Require parameterized `trade_date <= %s` before ordering/limit for index and breadth history. Require trading calendar range SQL and previous-date query. Require manifest completeness SQL that joins/compares `accepted_stock_count` to the action count.

Require `board_action_rows` to filter:

```sql
(`stock_code` BETWEEN '000001' AND '003999'
 OR `stock_code` BETWEEN '600000' AND '609999')
AND (`stock_name` IS NULL OR `stock_name` NOT LIKE '%ST%')
```

- [ ] **Step 2: Add failing job validation tests**

Add tests that:

- old target dates use history ending at the target rather than latest rows;
- non-adjacent `sample_trade_date` raises `DataValidationError`;
- incomplete current or previous manifest raises;
- main-board/non-ST rows only reach analyzer;
- previous-only and current-only boards remain in the union;
- completeness flags passed to analyzer are true only after manifest checks.
- a corrected rerun transaction deletes all existing hot-board rows for the target
  date before inserting the complete replacement, while analyzer failure performs
  no delete.

- [ ] **Step 3: Run repository/job tests and verify failure**

Run:

```powershell
uv run --frozen pytest -q tests/unit/modules/emotion/test_repository.py tests/unit/modules/emotion/test_jobs.py
```

Expected: FAIL because date-aware and manifest methods are absent and current jobs hard-code latest windows/completeness.

- [ ] **Step 4: Implement repository methods**

When a `MarketDataRepository` is injected, call `market_data.index_daily(end_date=end_date, limit=limit)` for index history. Resolve trading dates from `market_data.index_daily(start_date=start_date, end_date=end_date)` and return their distinct dates. Use parameterized SQL for the non-injected path. Keep output order ascending by date.

`jiuyan_date_complete` returns true only when manifest status is `complete` and its accepted count equals `COUNT(*)` in `jiuyan_actions` for the date.

- [ ] **Step 5: Update single-date jobs**

`run_index_emotion_job` requests `index_daily_rows_through(trade_date, 180)` and `market_breadth_rows_through(trade_date, 80)`.

`run_hot_board_emotion_job` validates:

```python
expected_previous = repository.previous_trading_date(trade_date)
if expected_previous != sample_trade_date:
    raise DataValidationError(
        f"Previous trading date mismatch: expected {expected_previous}, got {sample_trade_date}"
    )
if not repository.jiuyan_date_complete(sample_trade_date):
    raise DataValidationError(
        f"Unverified Jiuyan actions for {sample_trade_date}"
    )
if not repository.jiuyan_date_complete(trade_date):
    raise DataValidationError(
        f"Unverified Jiuyan actions for {trade_date}"
    )
```

Pass true completeness flags only after these checks.

Update the default writer so a complete `hot_board_emotion_daily` result replaces
the target date transactionally: calculate all rows first, delete by `trade_date`,
then insert the replacement in the same `engine.begin()` block. Keep injected
writer tests able to observe the complete table payload without opening a database.

- [ ] **Step 6: Run emotion repository/job tests**

Run:

```powershell
uv run --frozen pytest -q tests/unit/modules/emotion/test_repository.py tests/unit/modules/emotion/test_jobs.py tests/unit/modules/emotion/test_algorithms.py
```

Expected: PASS with canonical formula assertions unchanged.

- [ ] **Step 7: Commit date-aware emotion inputs**

```powershell
git add -- "src/stock_lab/modules/emotion/repository.py" "src/stock_lab/modules/emotion/jobs.py" "tests/unit/modules/emotion/test_repository.py" "tests/unit/modules/emotion/test_jobs.py"
git commit -m "fix: validate emotion source dates"
```

### Task 7: Index And Hot-Board Emotion Range Coordinators

**Files:**
- Modify: `src/stock_lab/modules/emotion/jobs.py`
- Create: `tests/unit/modules/emotion/test_range_jobs.py`

**Interfaces:**
- Produces: `backfill_index_emotion(start_date=None, end_date=None, *, repository=None, runner=run_index_emotion_job) -> dict` and `backfill_hot_board_emotion(start_date=None, end_date=None, *, repository=None, runner=run_hot_board_emotion_job) -> dict`.

- [ ] **Step 1: Add failing range coordinator tests**

Use a fake trading calendar `[20260804, 20260805, 20260806]` and assert:

```python
result = backfill_index_emotion(
    20260806,
    20260804,
    repository=repository,
    runner=runner,
)

assert calls == [20260804, 20260805, 20260806]
assert result == {
    "status": "success",
    "updated": 3,
    "processed_dates": [20260804, 20260805, 20260806],
    "failed_dates": [],
    "errors": [],
}
```

For hot-board, assert calls are `(20260805, 20260804)` and `(20260806, 20260805)`; the first calendar date without a prior session is excluded. Add one-date failure tests proving later dates continue and successful counts remain.

Add no-date tests selecting the latest canonical trading date and empty-calendar tests raising `DataValidationError`.

- [ ] **Step 2: Run range tests and verify import failure**

Run:

```powershell
uv run --frozen pytest -q tests/unit/modules/emotion/test_range_jobs.py
```

Expected: collection FAIL because the range functions do not exist.

- [ ] **Step 3: Implement normalized range selection**

Normalize missing dates to latest, one-sided ranges to one date, and reversed ranges by swapping. Use repository trading dates, not calendar arithmetic. Iterate ascending dates.

For every failure append:

```python
{"trade_date": trade_date, "error": str(error)}
```

to `errors`, add the date to `failed_dates`, and continue. `status` is failed when any date fails. `updated` sums integer runner results.

Call the index runner as `runner(trade_date, repository=repository)` and the hot-board runner as `runner(trade_date, previous_trade_date, repository=repository)` so injected and default paths use the same contract.

- [ ] **Step 4: Run range and single-date tests**

Run:

```powershell
uv run --frozen pytest -q tests/unit/modules/emotion/test_range_jobs.py tests/unit/modules/emotion/test_jobs.py tests/unit/modules/emotion/test_algorithms.py
```

Expected: PASS.

- [ ] **Step 5: Commit range coordinators**

```powershell
git add -- "src/stock_lab/modules/emotion/jobs.py" "tests/unit/modules/emotion/test_range_jobs.py"
git commit -m "feat: add emotion history backfills"
```

### Task 8: Restore `_8` And `_9` Task Entry Points

**Files:**
- Create: `src/stock_lab/jobs/emotion_compatibility.py`
- Create: `task/_8_指数情绪周期每日更新.py`
- Create: `task/_9_热门板块情绪每日更新.py`
- Create: `tests/unit/compatibility/test_emotion_tasks.py`
- Modify: `tests/test_cutover_contracts.py`

**Interfaces:**
- Consumes: `backfill_index_emotion` and `backfill_hot_board_emotion` from Task 7.
- Produces: `_8.更新`, `_8.update`, `_8.main`, `_9.更新`, `_9.update`, `_9.main`, and import-safe CLIs.

- [ ] **Step 1: Add failing compatibility tests**

Monkeypatch private official delegates and assert exact start/end forwarding, no-date forwarding, reversed dates left for canonical normalization, aliases, JSON output, and nonzero CLI exit on failed status.

Import both task modules under guarded browser/network/database factories and assert imports cause no side effects.

- [ ] **Step 2: Run compatibility tests and verify import failure**

Run:

```powershell
uv run --frozen pytest -q tests/unit/compatibility/test_emotion_tasks.py
```

Expected: FAIL because `_8` and `_9` do not exist.

- [ ] **Step 3: Implement official CLI composition**

`emotion_compatibility.run_index_cli` and `run_hot_board_cli` accept optional `--start-date` and `--end-date`, call the matching backfill, print JSON, and return 0 for success or 1 for failed.

- [ ] **Step 4: Implement pure forwarding wrappers**

Each task function is one return statement. Add exact wrapper limits:

```python
"task/_8_指数情绪周期每日更新.py": 80,
"task/_9_热门板块情绪每日更新.py": 80,
```

- [ ] **Step 5: Run compatibility and cutover tests**

Run:

```powershell
uv run --frozen pytest -q tests/unit/compatibility/test_emotion_tasks.py tests/test_cutover_contracts.py -k "not output_directory_tracks_only_ignore_policy"
```

Expected: PASS.

- [ ] **Step 6: Commit `_8/_9` entry points**

```powershell
git add -- "src/stock_lab/jobs/emotion_compatibility.py" "task/_8_指数情绪周期每日更新.py" "task/_9_热门板块情绪每日更新.py" "tests/unit/compatibility/test_emotion_tasks.py" "tests/test_cutover_contracts.py"
git commit -m "feat: restore upstream emotion tasks"
```

### Task 9: Daily Structured Jiuyan Result And Failure Semantics

**Files:**
- Modify: `src/stock_lab/jobs/daily_update.py`
- Modify: `tests/unit/jobs/test_daily_update.py`
- Modify: `tests/test_emotion_pipeline_integration.py`

**Interfaces:**
- Consumes: `DailyUpdateCollector.collect_board_actions(trade_date) -> dict` with status `success` or `succeeded_with_warnings`.
- Produces: `counts['board_actions']`, top-level `warnings`, and unchanged lock/completion behavior.

- [ ] **Step 1: Update failing daily fake results**

Return:

```python
{
    "status": "success",
    "updated": 7,
    "trade_date": trade_date,
    "export_paths": ["7_全部.ini"],
    "warnings": [],
}
```

from fake Jiuyan collection. Require daily count 7. Add a warning case returning `succeeded_with_warnings`; assert emotion still runs, completion is written, and the warning appears in result.

Add failure tests for `HumanVerificationRequired`, Jiuyan failed status, hot-board exception, and index-emotion exception; all must release lock and suppress completion.

- [ ] **Step 2: Run daily tests and verify failure**

Run:

```powershell
uv run --frozen pytest -q tests/unit/jobs/test_daily_update.py tests/test_emotion_pipeline_integration.py tests/test_daily_update_wrapper.py
```

Expected: FAIL because daily update treats Jiuyan as an integer and has no warning output.

- [ ] **Step 3: Add structured stage validation**

Implement a helper accepting only `success` and `succeeded_with_warnings`. Return integer `updated` and warning strings. Any other status raises `JobExecutionError("Jiuyan update failed")`.

Store warnings in the daily result only when non-empty:

```python
result = {
    "status": "success",
    "trade_date": trade_date,
    "source_trade_date": source_trade_date,
    "counts": counts,
}
if warnings:
    result["warnings"] = warnings
```

Do not catch `HumanVerificationRequired`; the existing `finally` releases the lock.

- [ ] **Step 4: Run daily and pipeline tests**

Run:

```powershell
uv run --frozen pytest -q tests/unit/jobs/test_daily_update.py tests/test_emotion_pipeline_integration.py tests/test_daily_update_wrapper.py
```

Expected: PASS.

- [ ] **Step 5: Commit daily integration**

```powershell
git add -- "src/stock_lab/jobs/daily_update.py" "tests/unit/jobs/test_daily_update.py" "tests/test_emotion_pipeline_integration.py"
git commit -m "feat: integrate verified Jiuyan collections"
```

### Task 10: Documentation, API Regression, Review, And Full Verification

**Files:**
- Modify: `docs/historical-data-source-matrix.md`
- Modify: `docs/historical-data-backfill-runbook.md`
- Modify: `docs/database-migrations.md`
- Modify: `docs/migration.md`
- Modify: `README.md`
- Modify: `tests/api/test_emotion_v1.py`

**Interfaces:**
- Produces: operator guidance and V1 response regression coverage matching the migrated Jiuyan/emotion behavior.

- [ ] **Step 1: Update documentation**

Document:

- `_6` is THS and remains deferred;
- migration `006` and unverified pre-migration Jiuyan dates;
- two attempts, 180-second deadline, fresh pages, immediate slider failure, and cleanup;
- MySQL replacement/manifest before INI generation;
- export warning and independent export/front-rank commands;
- `_8/_9` inclusive range CLI behavior and partial failures;
- strict adjacent complete Jiuyan dates and main-board/non-ST scope;
- daily remains single-date and Redis completion remains temporary compatibility state.

- [ ] **Step 2: Add V1 API contract assertions**

Extend existing API tests to assert current index and hot-board field names, empty response behavior, and recursive snake_case payloads remain unchanged after job/repository refactoring. Do not add new endpoints.

- [ ] **Step 3: Run import and CLI checks without browser/network access**

Run:

```powershell
uv run --frozen python -c "import importlib; modules=['task._5_韭研公社异动','task._8_指数情绪周期每日更新','task._9_热门板块情绪每日更新']; [importlib.import_module(name) for name in modules]; print('UPSTREAM_JIUYAN_EMOTION_IMPORTS_OK')"
uv run --frozen python -m task._5_韭研公社异动 --help
uv run --frozen python -m task._8_指数情绪周期每日更新 --help
uv run --frozen python -m task._9_热门板块情绪每日更新 --help
```

Expected: all commands exit zero without opening a browser, connecting to MySQL/Redis, or requesting a network resource.

- [ ] **Step 4: Run focused verification**

Run:

```powershell
uv run --frozen pytest -q --import-mode=importlib tests/unit/modules/market_data/test_jiuyan_repository.py tests/unit/modules/market_data/test_jiuyan_parsing.py tests/unit/modules/market_data/test_jiuyan_source.py tests/unit/modules/market_data/test_jiuyan_collector.py tests/unit/modules/market_data/test_jiuyan_exports.py tests/unit/compatibility/test_jiuyan_task.py tests/unit/modules/emotion tests/unit/compatibility/test_emotion_tasks.py tests/unit/jobs/test_daily_update.py tests/test_jiuyan_task.py tests/test_emotion_pipeline_integration.py tests/test_daily_update_wrapper.py tests/api/test_emotion_v1.py tests/integration/database/test_schema_migration.py
```

Expected: PASS.

- [ ] **Step 5: Run full verification**

Run:

```powershell
uv run --frozen pytest -q --import-mode=importlib
uv run --frozen pytest -q --import-mode=importlib -k "not output_directory_tracks_only_ignore_policy"
uv run --frozen python -m compileall src task tests
git diff --check
git status --short
```

Expected: the unfiltered suite has only the user-approved `output/.gitignore` failure; the filtered suite passes; compilation and diff checks pass. Fix every other failure.

- [ ] **Step 6: Request independent code review**

Review the full implementation range against:

```text
docs/superpowers/specs/2026-08-11-upstream-jiuyan-emotion-migration-design.md
docs/superpowers/plans/2026-08-11-upstream-jiuyan-emotion-migration.md
```

The reviewer must inspect schema/transaction safety, parser completeness, deadline and cleanup, manual verification, export atomicity, manifest authority, historical range/date adjacency, sample filtering, formula preservation, partial failures, wrapper import safety, daily completion, API compatibility, and missing tests. Fix all Critical and Important findings and rerun Step 5.

- [ ] **Step 7: Commit documentation and final consistency changes**

```powershell
git add -- "docs/historical-data-source-matrix.md" "docs/historical-data-backfill-runbook.md" "docs/database-migrations.md" "docs/migration.md" "README.md" "tests/api/test_emotion_v1.py"
git commit -m "docs: document Jiuyan and emotion migration"
```

Do not create an empty commit when no documentation or API consistency changes remain.
