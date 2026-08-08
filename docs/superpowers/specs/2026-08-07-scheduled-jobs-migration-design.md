# Scheduled Jobs Migration Design

## Scope

Move daily-update orchestration and premarket-summary extraction into official English
modules under `stock_lab.jobs`. Preserve the documented weekday/time scheduling,
date-scoped idempotency, expiring single-run locks, ordered INI output, and direct
Chinese task entry points. Retire legacy emotion-analysis writes to Chinese tables by
redirecting those functions to the official emotion jobs.

The public repository contains no implementation or history for `task/盘前纪要.py`.
The premarket job therefore accepts an injected source and does not invent a website,
endpoint, browser flow, or credentials. With no source configured it returns an
explicit `disabled` result and does not mark the date complete.

## Architecture

`stock_lab.infrastructure.cache.locks` owns a token-checked Redis lock abstraction.
It acquires with `SET NX EX`, requires a positive expiry, and deletes a lock only when
the stored token still belongs to the caller. Job tests inject an in-memory Redis-like
client and never contact Redis.

`stock_lab.jobs.daily_update` owns date normalization, trading-date resolution, step
ordering, completion state, backfill behavior, and result contracts. Its collector is
an injected object exposing the existing market-data and Jiuyan collection steps;
official emotion job callables are injected alongside it. Default dependency assembly
is lazy so importing the module performs no database, Redis, or network operation.

`stock_lab.jobs.premarket_summary` owns pure ordered extraction and run orchestration.
The source returns summary text plus the local security universe. Extraction matches
known stock names and six-digit codes in body order, deduplicates by normalized code,
and preserves the first occurrence. The writer receives canonical English stock
records and produces the established numbered `code,name` INI format under
`output/韭研公社盘前纪要/<date>/<count>_盘前纪要提及股票.ini`. Both source and writer can
be replaced in tests.

## State And Scheduling

Official V1 state keys are:

- `stock_lab:jobs:v1:daily_update:lock`
- `stock_lab:jobs:v1:daily_update:completed:<YYYYMMDD>`
- `stock_lab:jobs:v1:premarket_summary:lock`
- `stock_lab:jobs:v1:premarket_summary:completed:<YYYYMMDD>`

Completion keys retain the existing seven-day lifetime. Daily-update locks retain the
six-hour lifetime; premarket locks use an expiring run lock as well. A completion key
is written only after every step or the INI writer succeeds. Every acquired lock is
released in `finally`, including source, extraction, and write failures.

The realtime scheduler calls official runners directly after 17:35 and 08:00 on
weekdays. Jobs own the atomic lock and completion checks, so scheduler polling does not
perform a race-prone check before starting a thread. Optional premarket source loading
may return no source; this is a supported disabled state, not an import failure or a
successful collection.

## Compatibility

`task/每日更新.py` keeps `tasks`, `backfill`, and its command-line interface as thin
delegates. `task/盘前纪要.py` restores the documented direct function name as a thin
delegate. Compatibility modules may assemble local defaults lazily but contain no job
or persistence implementation.

`task/emotion_analysis.py` retains the two historical write entry points only as
delegates to `run_index_emotion_job` and `run_hot_board_emotion_job`. Legacy conversion,
SQL, and Chinese-table writes are removed. Tests and callers that need canonical
emotion behavior use the official module directly.

## Error Handling And Results

Concurrent acquisition raises a job execution error and never sets completion state.
Invalid dates, missing trading dates, malformed source data, and empty extraction are
explicit failures. `disabled` is reserved for a missing premarket source. Successful
and skipped results include the normalized trade date; failures propagate after lock
release so schedulers can log and retry on a later poll.

## Verification

Unit tests cover extraction order and deduplication, INI output, token ownership,
idempotency, concurrent locks, disabled sources, and lock release after each failure
boundary. Scheduler tests cover weekday/time gates and official optional runners;
wrapper tests verify delegation and imports without ambient I/O. Contract tests ensure
`task/emotion_analysis.py` no longer writes legacy tables.

Final verification runs full pytest, Python compileall, frontend tests and build,
legacy-key/table and official-naming diff checks, `git diff --check`, and a final
status/diff review without contacting real network, database, or Redis services.
