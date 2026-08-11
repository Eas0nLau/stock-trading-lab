# Upstream Intraday And KDJ Migration Design

## Goal

Migrate the behavior of upstream `task/_2_分时数据获取_5分k.py` and
`task/_3_kdj.py` into the canonical market-data architecture without restoring
legacy tables, import-time network access, direct SQL, unbounded retries, or
unsafe all-market defaults.

This is the second subproject of the approved upstream task migration. It owns
five-minute BaoStock history, KDJ calculation compatibility, canonical KDJ
persistence, and close-of-day KDJ orchestration. Jiuyan, emotion, THS, premarket,
and durable `task_runs` migration remain outside this subproject.

## Decisions

- Canonical five-minute time is the 12-digit minute `YYYYMMDDHHMM`.
- Both legacy 12-digit timestamps and BaoStock 17-digit timestamps resolve to the
  same canonical `trade_time` and `data_id`.
- The bulk five-minute CLI requires explicit start and end dates.
- Repeated `--stock-code` options limit the run; without them, the runner reads
  the canonical securities universe.
- The compatibility function `calculate_ths_kdj` reproduces the upstream formula
  exactly, including zero-filled warm-up and flat-window RSV behavior.
- Canonical `calculate_kdj` and `kdj_indicators` persistence retain the current
  corrected expanding-window and flat-window behavior.
- KDJ joins the close-of-day critical chain after daily market facts and before
  Jiuyan/emotion analysis. Five-minute history remains an independent job.
- Historical five-minute and KDJ facts live only in MySQL. Redis is not a fact
  store or completion authority for either independent backfill.

## Architecture

### BaoStock Source

`BaoStockSource.fetch_5m_bars(start_date, end_date, ts_code)` remains a narrow,
single-security provider boundary. It owns lazy BaoStock import, code/date
validation, login, query, response validation, logout, and typed infrastructure
errors. It does not enumerate securities, create worker pools, persist rows, or
format legacy lists.

The source range is inclusive. It rejects a start date later than the end date.
There is no import-time login and no call to `exit()`.

### Canonical Normalization And Identity

`normalize_intraday_bar` converts each source row into canonical English fields.
It normalizes both `YYYYMMDDHHMM` and longer BaoStock timestamp strings to the
first 12 digits. The stable identifier is derived from normalized `ts_code`,
`trade_date`, and 12-digit `trade_time`.

This identity matches rows produced by the legacy migration scripts. Re-fetching
a migrated minute updates the existing canonical row instead of inserting a
second row with a 17-digit time.

### Intraday Jobs

The existing single-security fetch and update functions remain the primitive
operations. A new bulk history runner composes them and owns:

- explicit inclusive date ranges;
- an optional explicit stock-code scope;
- canonical universe lookup when no scope is supplied;
- bounded worker concurrency;
- per-security validation and MySQL transaction boundaries;
- deterministic structured results.

Each security is fetched and fully normalized before its transaction begins.
One malformed or failed security cannot roll back already committed securities.
No transaction spans a remote request.

### Upstream Five-Minute Entry

`task/_2_分时数据获取_5分k.py` remains a thin compatibility boundary and exposes:

- `get_data(start_date, end_date, code=None, stock=None)`;
- `process_stock_batch(args)`;
- `main(start_date, end_date, stock_codes=None, max_workers=4)`;
- a CLI with required `--start-date` and `--end-date`, repeated
  `--stock-code`, and bounded `--max-workers`.

`get_data` preserves the upstream ten-column list order:

```text
open, close, date, time, code, high, low, volume, amount, adjustflag
```

Legacy list projection exists only in this task module. Canonical jobs and
repositories use dictionaries with English schema fields. The CLI never defaults
to fetching the whole market from 2025.

### KDJ Algorithms

Two explicit pure functions serve different contracts.

`calculate_ths_kdj(df, n=9, m1=3, m2=3)` is the upstream compatibility
algorithm:

- full `rolling(n)` low/high windows;
- missing and zero-range RSV becomes zero;
- first row remains `K=D=J=50`;
- later smoothing uses `1/m1` and `1/m2`;
- result columns are `trade_date`, `k`, `d`, and `j`;
- the caller's DataFrame is not used for persistence or network access.

The compatibility implementation validates positive integer `n`, `m1`, and
`m2` rather than preserving upstream divide-by-zero and invalid-window crashes.

Canonical `calculate_kdj(rows, period=9)` retains its existing deterministic
behavior: normalized symbol/date ordering, expanding windows during warm-up,
flat-range RSV of 50, and canonical dictionary output. Compatibility calculations
must never be written implicitly to `kdj_indicators`.

### Canonical KDJ Persistence And Upstream Entry

`update_kdj_indicators(start_date, end_date, stock_codes=None, repository=None,
period=9)` remains the only KDJ writer. It reads sufficient daily history through
the end date, calculates canonical values, writes every requested date, and
upserts duplicates so historical corrections are possible.

`task/_3_kdj.py` exposes the upstream names:

- `calculate_ths_kdj` delegates to the pure compatibility algorithm;
- `save_code_kdj(ts_code, start_date=None, end_date=None)` delegates to the
  canonical job for one security;
- `save_daily_kdj(start_date=None, end_date=None)` delegates to the canonical
  all-market job;
- the CLI requires or resolves an explicit target date/range without direct SQL.

The filename remains lowercase `_3_kdj.py`, matching the upstream repository.

## Data Flow

### Five-Minute History

1. Parse and validate the explicit date range and optional security scope.
2. Resolve canonical securities when no scope is supplied.
3. Submit at most `max_workers` independent security fetches.
4. For each security, perform BaoStock login/query/logout.
5. Normalize all returned rows, including 12-digit minute identity.
6. Upsert that security's rows in one MySQL transaction.
7. Record the security as processed, empty, or failed.
8. Return a deterministic structured result after all workers finish.

The result contains:

```text
status, updated, processed_codes, empty_codes, failed
```

Partial failures preserve successful transactions and set `status='failed'`.
If every requested security is empty, the run also fails. An empty universe is a
validation failure, not a successful update.

### KDJ And Daily Update

1. Daily index, securities, quotes, market value, and DDE facts commit.
2. Canonical KDJ recalculates the affected date range using prior quote history.
3. Jiuyan and emotion stages run only after KDJ succeeds.
4. KDJ row count is included in daily-update counts.
5. A KDJ failure raises `JobExecutionError`, releases the token-protected Redis
   lock, and does not write the daily completion mirror.

Five-minute history does not run in this chain because it is high-volume,
security-scoped, and not required by close-of-day emotion calculations.

## Failure And Retry Semantics

- BaoStock provider failures are typed exceptions; callers never terminate the
  process with `exit()`.
- No recursive or unbounded retry is introduced. A future retry policy must be
  finite and tested before being enabled.
- Malformed rows fail only their security before persistence.
- Empty five-minute responses are reported explicitly.
- KDJ calculations are local and deterministic; malformed canonical quote data
  fails the affected invocation rather than producing partial indicator writes.
- Bulk result lists are sorted by canonical `ts_code` for reproducible output.
- Neither independent job uses Redis markers to claim durable completion.

## Compatibility And Retirement

`_2.get_data()` stays because active strategies still consume its ten-column
legacy list. New production code must use canonical jobs and repository rows.

`intraday_bars_5m_legacy()` remains until all active strategy consumers migrate.
It is not expanded and is removed only after a repository-wide caller search and
equivalent canonical consumer tests.

`task/_3_kdj.py` keeps upstream callable names but contains no database query,
provider client, retry loop, or persistence implementation. No compatibility
alias may write legacy `stock_kdj` or read legacy `stock_daily`.

The following upstream behaviors are intentionally retired:

- import-time BaoStock login or database/client construction;
- fixed six-process pools and fixed batches of 300 securities;
- no-argument all-market history from 2025;
- direct SQL interpolation and legacy table writes;
- `exit()` on provider errors;
- recursive database retries;
- latest-row-only KDJ persistence and no-op duplicate updates;
- integer stock codes and loss of exchange identity.

## Testing

### Five-Minute Tests

- 12-digit and 17-digit source times produce the same minute and `data_id`;
- migrated and newly fetched representations cannot duplicate a logical minute;
- reversed ranges, invalid dates, and invalid stock codes fail before login;
- malformed rows fail without a partial security write;
- single-security, explicit multi-security, and canonical-universe modes;
- bounded concurrency and deterministic result ordering;
- partial failure preserves successful writes;
- all-empty and empty-universe runs fail;
- `_2` names, signatures, CLI, legacy list order, and import safety.

### KDJ Tests

- golden upstream samples for first-row initialization, first eight warm-up rows,
  rolling-window values, flat ranges, and non-default `m1`/`m2`;
- invalid compatibility parameters fail clearly;
- canonical formula regression tests remain unchanged;
- one-security and all-market canonical persistence paths;
- all requested dates are repairable on rerun;
- `_3_kdj` names, signatures, CLI, and import safety;
- daily ordering, count reporting, lock release, and completion suppression on KDJ
  failure.

### Verification

- focused source/job/repository/compatibility tests;
- cutover contract tests with only the user-approved `output/.gitignore` case
  excluded;
- full pytest suite in importlib mode;
- `compileall`, task import checks, CLI `--help`, `git diff --check`, and clean
  worktree verification.

## Documentation

Update the historical source matrix, backfill runbook, database migration notes,
and migration map to state:

- BaoStock five-minute timestamps use canonical minute identity;
- the bulk CLI requires explicit dates and supports security scoping;
- compatibility and canonical KDJ formulas intentionally differ;
- KDJ is part of the close-of-day critical chain;
- five-minute history remains independent and MySQL-authoritative.
