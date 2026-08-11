# Upstream Jiuyan And Emotion Migration Design

## Goal

Migrate the upstream behavior of `task/_5_韭研公社异动.py`,
`task/_8_指数情绪周期每日更新.py`, and
`task/_9_热门板块情绪每日更新.py` into the canonical architecture while
preserving bounded browser behavior, MySQL authority, deterministic exports, and
repairable historical emotion calculations.

Upstream `task/_6_同花顺行业和概念.py` is not an emotion task. It remains outside
this subproject and will be handled with the THS snapshot migration.

## Decisions

- Jiuyan browser attempts are finite, deadline-bound, fresh-page attempts.
- Slider/manual verification fails immediately with `HumanVerificationRequired`.
- Every page and listener is cleaned up after each attempt.
- Jiuyan source data is validated completely before any database write.
- A MySQL `jiuyan_collection_days` manifest records durable per-date completeness.
- Jiuyan facts commit to MySQL before INI files are generated.
- INI files are rebuildable output, not durable fact or task authority.
- An export failure yields `succeeded_with_warnings` and does not roll back facts.
- Daily emotion remains date-scoped and fast.
- `_8` and `_9` gain separate range coordinators for historical repair.
- Canonical emotion formulas remain authoritative; known upstream threshold bugs
  are not copied.
- Redis remains an expiring lock/completion mirror. Durable task-ledger authority
  remains deferred to the later `task_runs` subproject.

## Scope

### Included

- Jiuyan source lifecycle, retry, deadline, response validation, persistence, INI
  export, and front-rank query.
- Schema migration and repository ownership for `jiuyan_collection_days`.
- Thin `_5` compatibility names and CLI.
- Index-emotion and market-breadth range backfill with `_8` compatibility entry.
- Hot-board emotion range backfill with `_9` compatibility entry.
- Trading-calendar adjacency and canonical sample filtering.
- Daily-update integration for structured Jiuyan results and emotion failures.
- Tests and operator documentation.

### Excluded

- THS board/constituent collection from upstream `_6`.
- New `task_runs` schema and MySQL task-ledger authority.
- Premarket summary migration.
- Removal of all legacy emotion translation contracts.
- Changes to frontend visual design or V1 API routes.

## Architecture

### Jiuyan Browser Source

`JiuyanBrowserSource` owns one remote attempt. It receives injected page creation,
clock, and cleanup dependencies so tests never open a browser.

For each call it:

1. validates the requested date;
2. waits for the process-global Jiuyan request slot;
3. creates a uniquely named fresh page rather than reusing the cached
   `jiuyan-action` tab;
4. starts the `/jystock-app/api/v1/action/field` listener;
5. navigates with a timeout bounded by the remaining overall deadline;
6. detects slider/manual verification before and during listener processing;
7. returns the first valid decoded response for the target endpoint;
8. stops the listener and closes the page in `finally`.

`HumanVerificationRequired` is never retried automatically. Ordinary timeout,
navigation, decoding, and incomplete-response errors may be retried by the
collector within the configured finite attempt budget and total deadline.

The defaults are two attempts and one 180-second overall deadline. The deadline
includes request-slot waiting, navigation, interaction, and listener processing;
an individual operation cannot extend the total deadline.

No source method writes MySQL, Redis, or files.

### Jiuyan Parser And Completeness

`parse_batch(response, trade_date)` remains deterministic and side-effect free. It
returns canonical rows plus source board count, raw stock count, accepted stock
count, source date, and a deterministic source fingerprint. The fingerprint is
the SHA-256 of normalized UTF-8 JSON with sorted keys and compact separators. It
validates:

- response type and nested collection shape;
- a source date matching the requested date for every accepted response shape;
- at least one non-empty board group;
- non-empty board names;
- positive reported board stock counts;
- stock code, stock name, action-info, range, and source-code fields;
- `shares_range / 100` between 9.5 and 10.2 inclusive;
- valid limit-up time when present;
- no duplicate stock within a board;
- no structurally invalid stock is silently discarded;
- at least one stock passes the 9.5-10.2 accepted range.

`board_stock_count` is retained as source metadata but is not required to equal the
group list length because the upstream count semantics are not sufficiently
documented. Completeness means the entire received group/list structure was
validated, every raw stock was parsed, and the batch manifest committed with the
facts.

`parse_response(response, trade_date)` remains as the compatibility projection and
returns only the parsed row list from `parse_batch`.

Canonical identifiers preserve six-digit stock identity and avoid overlong board
names in `data_id`. The identifier uses a deterministic digest of trade date,
board name, and canonical stock code rather than embedding the full board name.
The human-readable board name remains in `board_name`.

### Jiuyan Collector And Result

`JiuyanCollector.collect(trade_date)` coordinates finite attempts. It performs no
write until parsing and completeness validation finish.

Persistence for one date is replacement-oriented and transactional:

1. delete existing `jiuyan_actions` rows for the target date;
2. insert the complete canonical replacement;
3. insert or replace `jiuyan_collection_days` with `status='complete'`, source
   counts, accepted count, fingerprint, and collection time;
4. verify persisted action count equals the accepted manifest count;
5. commit.

This removes boards or stocks absent from a corrected source response instead of
leaving stale rows from prior upserts.

After commit, the collector invokes the export service. It returns:

```text
status, updated, trade_date, export_paths, warnings
```

`status` is `success` or `succeeded_with_warnings`. Remote, parsing, completeness,
and persistence errors raise and produce no successful result. Export errors are
captured in `warnings` after facts are durable.

## Jiuyan Collection Manifest

A new migration creates `jiuyan_collection_days`:

```text
trade_date, status, source_board_count, source_stock_count,
accepted_stock_count, source_fingerprint, collected_at
```

`trade_date` is the primary key. `status='complete'` is written only in the same
transaction as the date replacement. Failed attempts do not replace an existing
complete manifest.

Existing pre-migration Jiuyan rows have no manifest and are treated as unverified.
They remain readable by current APIs, but new hot-board range recalculation refuses
to consume them until the date is recollected successfully. This conservative rule
prevents old partial rows from being interpreted as real market retreat.

### Jiuyan INI Export

The export service reads committed rows through the repository. It does not
accept uncommitted source rows.

Output root:

```text
output/韭研公社异动板块/<trade_date>/
```

It writes one UTF-8 INI per included board and one all-stock INI. Lines use the
existing project format:

```text
1 = 000001,平安银行
```

Rules:

- exclude `ST板块`;
- normal boards sort by descending reported board count, then board name;
- `公告`, `其他`, and `新股` sort after normal boards;
- stocks within a board sort by true consecutive-board streak, then board count,
  limit-up time, and stock code;
- a stock present in multiple boards is exported only under the first ordered
  board;
- file names are sanitized and deterministic;
- existing target-date INI files are replaced atomically through temporary files;
- the all-stock file is named `<unique_count>_全部.ini`.

The exporter does not depend on THS board codes or caches. THS import-code mapping
belongs to the later `_6` subproject.

### Front-Rank Query

The canonical front-rank service reads one date from `jiuyan_actions`, excluding
`ST板块`. It returns structured board and reason summaries and may log them for CLI
use. It never reads the legacy Chinese table and never scrapes the page.

`日内前排()` defaults to the latest complete Jiuyan date and can accept an explicit
date.

### Index Emotion Range Coordinator

Existing deterministic market-breadth and index-emotion calculations remain the
single-date primitives. A range coordinator owns:

- validated inclusive start/end dates;
- reversed-range normalization for upstream compatibility;
- canonical trading-date selection;
- enough history before each target date for MA and volume windows;
- per-date transaction boundaries;
- structured partial-failure output.

The result contains `status`, `updated`, `processed_dates`, and `failed_dates`.

Repository queries become end-date aware rather than always taking only the latest
160 index rows or latest 80 quote dates. Historical dates with existing facts must
be calculable even when they are older than the current latest-window cutoff.

`task/_8_指数情绪周期每日更新.py` is a thin range/CLI adapter. Its CLI never runs a
hard-coded historical range.

### Hot-Board Emotion Range Coordinator

The single-date hot-board algorithm remains canonical. A range coordinator:

1. resolves target dates from the canonical trading calendar;
2. resolves the immediately preceding trading date for every target;
3. verifies both Jiuyan dates have `jiuyan_collection_days.status='complete'` and
   matching persisted action counts;
4. filters sample stocks to Shanghai/Shenzhen main boards and excludes ST names;
5. calls the single-date canonical job;
6. commits each target date independently;
7. returns deterministic processed and failed date lists.

The result contains `status`, `updated`, `processed_dates`, and `failed_dates`.

Direct single-date calls also validate that `sample_trade_date` is the immediately
preceding canonical trading date. Arbitrary non-adjacent samples are rejected.

The range coordinator supports historical repair without making daily update
recompute a 30-day window on every run.

`task/_9_热门板块情绪每日更新.py` is a thin range/CLI adapter. It honors both range
arguments and never silently treats one as an ignored cutoff.

## Formula Policy

Canonical formulas in `stock_lab.modules.emotion` remain authoritative.

Index emotion retains:

- trend score 0-35;
- breadth score 0-25;
- limit structure score 0-20;
- volume score 2-10;
- risk-appetite score 0-10;
- state bands at 25, 40, 60, 75, and 88;
- forced `退潮` under the existing downtrend and weak-structure conditions.

The upstream approximate ±98.5% limit threshold defect is not copied. Canonical
limit-up/down breadth continues to use the project's tested market thresholds.

Hot-board emotion retains the existing promotion, coverage, confidence,
continuation-adjustment, climax, and score-cap formulas. This project adds source
and sample validation, not a silent formula rewrite.

## Daily Update

The daily critical chain remains:

1. index and trading calendar;
2. securities and daily quotes;
3. market value and DDE;
4. KDJ;
5. Jiuyan collection and durable replacement;
6. Jiuyan INI export;
7. hot-board emotion;
8. index emotion and market breadth;
9. Redis completion mirror.

Daily update accepts Jiuyan results with `status` equal to `success` or
`succeeded_with_warnings`, stores `updated` in counts, and surfaces warnings in the
job result. A rebuildable INI warning does not block emotion because MySQL facts
are already committed.

Remote, parsing, completeness, persistence, hot-board, or index-emotion failure
releases the token-protected lock and prevents the completion mirror.

Redis completion remains temporary compatibility state. This subproject does not
claim it is durable proof of MySQL completeness.

## Compatibility Entry Points

### `_5_韭研公社异动.py`

The thin wrapper exposes current names plus restored upstream behavior:

- `等待请求频率`;
- `格式化页面日期`;
- `解析异动响应`;
- `韭研公社异动采集`;
- `导出韭研公社异动板块`;
- `日内前排`;
- an explicit-date CLI.

THS refresh functions from the upstream `_5` file are intentionally not restored.
They move to the `_6` THS subproject.

### `_8_指数情绪周期每日更新.py`

Expose `更新(start_date=None, end_date=None)` and English aliases, forwarding to
the canonical index-emotion range coordinator. Missing dates resolve to the latest
canonical trading date. Reversed dates are normalized.

### `_9_热门板块情绪每日更新.py`

Expose `更新(start_date=None, end_date=None)` and English aliases, forwarding to
the canonical hot-board range coordinator with the same date rules.

Task files contain only parameter forwarding and CLI delegation. Browser,
algorithm, persistence, export, and repository behavior live under `src/stock_lab`.

`task/emotion_analysis.py` remains until its active callers migrate to `_8`, `_9`,
or canonical jobs.

## Failure Semantics

- Human verification raises immediately and is not retried in-process.
- Ordinary Jiuyan attempts are finite and share one overall deadline.
- Page/listener cleanup is best-effort but always attempted.
- Invalid or partial Jiuyan responses never replace existing facts.
- Date replacement is atomic.
- INI failure is a warning after commit and is independently repairable.
- Emotion range backfills preserve successful dates and report failed dates.
- No stage uses `exit()`, infinite loops, unbounded retries, or permanent Redis
  markers.
- No remote call occurs inside a database transaction.

## Testing

### Jiuyan Source And Parser

- fresh page per attempt;
- listener/page cleanup on success, ordinary error, timeout, and slider;
- finite attempts and total deadline;
- no retry after `HumanVerificationRequired`;
- JSON and JSONP decoding;
- top-level and grouped date matching;
- malformed shape, missing date, empty board, invalid count, malformed stock,
  duplicate stock, and partial-board rejection;
- exact 9.5 and 10.2 boundaries;
- stable digest-based identifiers and six-digit codes.

### Persistence And Export

- full validation before transaction;
- transactional per-date replacement removes stale rows;
- manifest and facts commit atomically;
- persisted action count matches accepted manifest count;
- unverified legacy dates are rejected by new hot-board backfills;
- export starts only after commit;
- export warning preserves committed facts;
- independent export rerun from repository;
- board ordering, special-board ordering, ST exclusion, stock sorting,
  cross-board deduplication, sanitized names, atomic replacement, and all-stock
  output;
- front-rank structured output and latest-complete-date selection.

### Emotion

- old historical dates beyond prior 80/160-row cutoffs;
- inclusive ranges and reversed ranges;
- per-date partial failures;
- strict adjacent previous trading date;
- incomplete Jiuyan date rejection;
- main-board/non-ST filtering;
- previous-only and current-only boards;
- coverage thresholds, state boundaries, score caps, and climax behavior;
- index formula regression, including correct limit thresholds;
- `_8` and `_9` names, aliases, CLI, and import safety.

### Daily And API

- Jiuyan success and `succeeded_with_warnings` counts;
- export warnings surfaced without blocking emotion;
- slider, persistence, hot-board, and index-emotion failures release the lock and
  suppress completion;
- V1 API fields and frontend normalization remain unchanged;
- cutover contracts, full pytest, compileall, CLI help, import safety, diff check,
  and clean worktree verification.

## Documentation

Update source matrix, backfill runbook, migration map, and README to state:

- `_6` is THS and is deferred;
- Jiuyan uses bounded fresh-page attempts and immediate manual-verification
  failure;
- MySQL facts commit before rebuildable INI output;
- `jiuyan_collection_days` is the durable completeness proof for emotion inputs;
- `_8` and `_9` support historical ranges while daily update remains single-date;
- emotion calculations require complete adjacent Jiuyan dates;
- Redis completion is temporary compatibility state, not durable authority.
