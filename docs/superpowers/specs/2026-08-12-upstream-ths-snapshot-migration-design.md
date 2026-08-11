# Upstream THS Snapshot Migration Design

## Goal

Migrate the business behavior of upstream `task/_6_同花顺行业和概念.py`
into the canonical architecture without copying its direct Chinese SQL, indefinite
CSV cache, excessive retries, swallowed worker failures, or partial completeness
checks.

The result is an independent full-snapshot job for:

- `ths_boards`;
- `ths_board_constituents`;
- `ths_stock_relations`.

The job collects and validates one coherent source snapshot in memory, then
replaces all three tables in one MySQL transaction. It is not part of the
close-of-day critical chain.

## Scope

This subproject includes:

- THS concept and industry board directory collection;
- concept import-code resolution;
- blockrank and paged-HTML constituent collection;
- strict completeness and referential validation;
- deterministic stock-to-board aggregation;
- one-transaction replacement of the three existing canonical tables;
- a structured independent job result;
- a thin `_6` compatibility module and CLI;
- documentation and regression coverage for the new runtime ownership.

This subproject excludes:

- persistent CSV or page caches;
- incremental supplementation of an old snapshot;
- Redis status, locks, or completion markers;
- `task_runs`, which belongs to the later task-ledger subproject;
- scheduling THS inside daily update;
- new API or frontend surfaces;
- schema versioning or active-snapshot tables.

## Upstream Baseline

The behavior baseline is upstream commit
`8e1a3f8348bd9b10af9174b55fd94b0dca9494fb`, file
`task/_6_同花顺行业和概念.py`.

Required behavior retained from upstream:

- concept boards come from `https://q.10jqka.com.cn/gn/`;
- industry boards come from `https://q.10jqka.com.cn/thshy/`;
- board links are parsed from `div.cate_inner`;
- concept import codes come from `<input id="clid">`;
- `88xxxx` boards prefer the THS blockrank source;
- unsupported or incomplete blockrank results fall back to paged HTML;
- stock relations aggregate industry and concept memberships into parallel,
  semicolon-separated name/code fields;
- collection supports bounded concurrency;
- the final MySQL update is a complete replacement.

Defects explicitly rejected:

- 60 retries with long linear sleeps;
- per-worker pacing without a global request interval;
- indefinite reuse of `data/*.csv`;
- worker exceptions converted to empty boards;
- accepting blockrank rows below the declared count;
- requiring only one constituent to consider a board complete;
- silently truncating pagination at 300 pages;
- falling back from a missing concept `clid` to the page code;
- direct table creation or Chinese-table SQL in the task wrapper;
- partial or mixed-date supplementation from old files or MySQL rows.

## Architecture

### HTTP Source

`stock_lab.infrastructure.market_data.ths` owns:

- lazy loading of AkShare's `ths.js` and `py_mini_racer` only when collection
  starts;
- generation and refresh of the THS `v` Cookie;
- request headers, referers, and blockrank host handling;
- one process-wide request pacer shared by every worker;
- bounded request retries and HTTP error translation;
- retrieval of board-directory, detail, blockrank, and constituent-page bodies.

Importing the module must not load V8, read AkShare datasets, open a database, or
perform a network request.

Default source settings are:

- `max_workers=4`;
- minimum global request interval `0.5` seconds;
- request timeout `20` seconds;
- maximum `3` attempts per request;
- retry waits of `1` and `2` seconds before attempts two and three, with no sleep
  after the final failure;
- fresh Cookie generation on initial use and after `401` or `403`.

The global request pacer applies before every network request, including retries
and blockrank requests. Concurrency must never multiply the configured request
rate.

### Parsing And Normalization

`stock_lab.modules.ths.parsing` owns pure parsing functions for:

- concept and industry directory HTML;
- concept `clid` detail HTML;
- blockrank JSONP and declared counts;
- HTML pagination metadata;
- HTML constituent tables;
- six-digit code and nonempty-name normalization.

Parsers return canonical dictionaries or typed immutable values. They do not
perform network requests, write files, or access MySQL.

Directory rows normalize to:

```text
board_code, board_type, board_name, page_code, detail_path
```

Constituent rows normalize to:

```text
board_code, stock_code, board_type, board_name, page_code, stock_name
```

Canonical `board_type` values are English: `concept` and `industry`.
`detail_path` values remain the source route segments `gn` and `thshy`.

Industry `board_code` equals its normalized six-digit `page_code`. Concept
`board_code` must come from a valid six-digit `clid`; a missing or invalid `clid`
fails that board and blocks the snapshot.

Stock codes extract one to six source digits and normalize to six digits. Stock
names are stripped and must be nonempty. Placeholder rows containing
`暂无成份股数据` are not stock rows.

### Collection Coordinator

`stock_lab.modules.ths.collection` owns full-snapshot orchestration.

It first collects both board directories and resolves every concept import code.
Both board types must be present. It then submits one bounded worker per board,
with at most four workers active by default.

Every worker returns one of three explicit outcomes:

- complete nonempty constituents;
- complete, source-proven empty board;
- failed board with a bounded error message.

No worker exception is converted to an empty result.

#### Blockrank

For `88xxxx` board codes, the collector requests blockrank `d15` first and reads
`block.subcodeCount`.

- If the declared count is zero, the board is explicitly empty.
- Counts below 3000 request `d{ceil(count / 15) * 15}`.
- Counts at or above 3000 request both `a3000` and `d3000`.
- Rows use blockrank fields `5` and `55` for stock code and name.
- The result is accepted only when the number of unique valid stock codes equals
  the declared count.

Unsupported blockrank boards, empty responses without a zero declaration,
decode failures, or count mismatches fall back to HTML pagination.

#### HTML Pagination

Page one uses:

```text
https://q.10jqka.com.cn/{detail_path}/detail/code/{page_code}/
```

Later pages use:

```text
https://q.10jqka.com.cn/{detail_path}/detail/field/199112/order/desc/page/{page}/ajax/1/code/{page_code}/
```

The declared page count is parsed from `span.page_info`. A missing page indicator
means one page. The default and maximum supported safety limit is `300` pages. If
the source declares more pages, collection fails rather than silently truncating.

Every declared page must parse successfully. A later page that is empty or adds
no new stock codes is a failure. Page one is accepted as a true empty board only
when it explicitly contains `暂无成份股数据`; a generic missing table or empty parse is
not proof of emptiness.

### Snapshot Validation

The snapshot is valid only when all of these conditions hold:

- concept and industry board directories are both nonempty;
- every `board_code` is unique;
- every `(board_type, page_code)` pair is unique;
- every concept board has a valid resolved `clid`;
- every board has a complete nonempty or source-proven empty worker result;
- no failed boards remain;
- constituent keys `(board_code, stock_code)` are unique;
- every constituent references a collected board and repeats the same board type,
  name, and page code;
- every stock code is six digits and every stock name is nonempty;
- the stock relation aggregate contains exactly the stock codes present in the
  constituent set;
- relation membership names and codes are parallel, deterministic, deduplicated,
  and derived only from the current snapshot.

Source-proven empty boards remain in `ths_boards` and have no constituent rows.
They do not make the snapshot incomplete.

### Stock Relation Aggregation

One `ths_stock_relations` row is generated per stock code.

Industry and concept memberships are independently deduplicated by board code,
sorted by `(board_code, board_name)`, and joined with semicolons into parallel
name/code strings.

The stock name is selected deterministically from current constituent rows:

1. highest occurrence count;
2. names not beginning with `C` or `N`, case-insensitive;
3. longer name;
4. lexical order.

No previous MySQL relation or CSV value participates in aggregation.

## Persistence

The existing `ThsRepository` remains a read-only query boundary with no engine
or write methods.

A separate `ThsSnapshotWriter` owns the database engine and exposes one operation:

```python
replace_snapshot(boards, constituents, stock_relations) -> dict[str, int]
```

All input rows are fully validated before `engine.begin()` is opened. Inside one
transaction, the writer:

1. deletes `ths_board_constituents`;
2. deletes `ths_stock_relations`;
3. deletes `ths_boards`;
4. inserts all boards;
5. inserts all constituents;
6. inserts all stock relations;
7. queries and verifies the three persisted row counts.

The child tables are deleted before the board table so the sequence remains safe
if foreign keys are added later. Boards are inserted before child rows for the
same reason.

Every row in one replacement receives the same validated `collected_date` and
one `updated_at` timestamp. Any delete, insert, or count mismatch raises and rolls
back the entire replacement. No remote call occurs while the transaction is open.

No new schema migration is required because all three canonical tables and their
keys already exist in `001_create_english_schema.sql` and the clean initializer.

## Job Contract

`stock_lab.jobs.ths_snapshot` owns default dependency composition and exposes a
full-snapshot job.

Success returns:

```python
{
    "status": "success",
    "collected_date": 20260812,
    "boards": 520,
    "constituents": 18000,
    "stock_relations": 5400,
    "empty_boards": 3,
    "persisted": True,
    "failed_boards": [],
    "errors": [],
}
```

Failure returns the available observed counts plus deterministic
`failed_boards` and `errors`, with `persisted=False`. A failed snapshot never
invokes the writer. CLI exits nonzero when status is failed.

Each stored error string is truncated to at most `1000` characters. Board failure
ordering follows canonical `(board_type, board_code)` ordering rather than worker
completion order.

This job does not use Redis and does not record `task_runs` yet. It remains an
independent operator-triggered snapshot job and is not called by daily update.

## Compatibility Surface

`task/_6_同花顺行业和概念.py` is an import-safe forwarding wrapper. It exposes:

- `采集同花顺板块成分股(...)`;
- `每日更新同花顺板块成分股(...)`;
- an English `update(...)` alias;
- a CLI with optional `--collect-date` and `--max-workers`.

Both Chinese names and the English alias execute the same full canonical
collection, validation, and transaction replacement. The default date is the
current local date and the default worker count is four. `collect_date` must be a
valid `YYYYMMDD` date. `max_workers` must be between `1` and `8`; values outside
that range fail validation instead of being silently clamped.

The wrapper does not restore:

- `补采同花顺缺失板块成分股`;
- CSV output or cache functions;
- direct table-creation functions;
- direct MySQL writer functions;
- requests, BeautifulSoup, pandas, SQLAlchemy, AkShare, or V8 imports.

## Error Handling

- Network errors, timeouts, and HTTP errors use at most three attempts.
- `401` and `403` refresh the Cookie before a retry.
- Parsing, count mismatch, invalid code, pagination truncation, and missing `clid`
  are data-completeness failures, not retry loops at the job layer.
- All worker failures are collected and reported; no partial snapshot is written.
- Error strings are bounded before inclusion in structured results.
- Import-time dependency or source failures are prohibited.

## Documentation Changes

The existing archival-only THS documentation and tests must be updated. The final
ownership is:

- `ThsRepository`: canonical read-only query boundary;
- `ThsSnapshotWriter`: only runtime writer;
- `002` and `004`: legacy migration/import paths, no longer the sole writers;
- `task/_6_同花顺行业和概念.py`: thin operator compatibility entry point.

The old Chinese tables remain migration-only and are never referenced by active
runtime code.

## Testing

Tests use fixed HTML and JSONP fixtures and never contact THS.

Coverage includes:

- concept and industry directory parsing;
- required concept `clid` resolution;
- blockrank decode, count calculation, exact-count acceptance, and HTML fallback;
- HTML page-count parsing, all-page collection, explicit empty proof, duplicate
  codes, no-new-row failure, and safety-limit failure;
- code/name normalization;
- deterministic stock relation aggregation and stock-name selection;
- global pacing across concurrent workers;
- bounded retries and Cookie refresh;
- failed-board aggregation and zero writer calls on incomplete snapshots;
- source-proven empty boards;
- writer validation before transaction;
- three-table delete/insert/count order and transaction rollback;
- structured job and CLI exit contracts;
- import-safe thin wrapper behavior;
- no active legacy THS table references;
- unchanged canonical read queries.

Final verification runs focused THS tests, cutover contracts, the filtered full
Python suite, `compileall`, `git diff --check`, and an independent code review.
The approved `output/.gitignore` contract failure remains the only excluded test.

## Acceptance Criteria

The subproject is complete when:

- one complete source snapshot replaces all three canonical tables atomically;
- no failed, truncated, stale, or mixed-date board result can be persisted;
- explicitly proven empty boards are retained safely;
- global request pacing and retry budgets remain bounded under concurrency;
- the existing read-only repository contract remains intact;
- `_6` is a thin import-safe wrapper with no direct source or SQL behavior;
- documentation no longer describes the THS tables as permanently import-only;
- focused, full, compilation, cutover, and review checks pass.
