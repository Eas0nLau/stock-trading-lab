# Upstream Task Migration Design

## Goal

Use the newly published upstream `task/` implementation as the business-behavior reference while preserving the current project's English canonical schema, modular boundaries, APIs, explicitly requested extensions, and MySQL authority.

This is not a source-file overwrite. Each upstream workflow is migrated as a vertical business slice, tested against its intended behavior, and adapted to the current persistence model before obsolete local replacement code is removed.

## Upstream Baseline

The behavior baseline is upstream commit `8e1a3f8348bd9b10af9174b55fd94b0dca9494fb`, committed on 2026-08-10. It contains:

- `_1_日k数据更新.py`
- `_2_分时数据获取_5分k.py`
- `_3_kdj.py`
- `_4_上证指数日k.py`
- `_5_韭研公社异动.py`
- `_6_同花顺行业和概念.py`
- `_7_市值信息每日更新.py`
- `_8_指数情绪周期每日更新.py`
- `_9_热门板块情绪每日更新.py`
- `_10_开盘啦dde读取.py`
- `每日更新.py`
- `盘前纪要.py`
- `__init__.py`

The upstream code defines required sources, date behavior, outputs, orchestration, and operator-facing names. Its implementation defects are not compatibility requirements. Infinite retries, import-time network calls, old Chinese SQL, non-atomic Redis locks, `sys.path` mutation, broken formulas, unbounded browser loops, and partial-write behavior must not be copied.

## Decisions

- Migrate upstream behavior task by task instead of replacing the local `task/` directory wholesale.
- Preserve the canonical `src/stock_lab` jobs, modules, repositories, APIs, English schema, and guarded database migrations.
- Preserve locally added capabilities that were explicitly requested, including historical fund-flow backfill, current APIs, and Redis-to-MySQL migration tooling.
- Remove locally invented task replacements only after their consumers use the upstream-compatible canonical implementation.
- Keep MySQL as the authority for durable facts. Redis is limited to expiring locks, short-lived job polling, current-day/rebuildable caches, and transient notifications.

## Target Architecture

```text
Upstream task behavior
  -> infrastructure/source: HTTP, browser, provider sessions, pacing, retries
  -> modules: parsing, normalization, calculations, contracts
  -> repositories: MySQL transactions and stable business keys
  -> jobs: ranges, stages, retries, resumption, cache projection
  -> task: thin CLI or temporary compatibility entry points
```

External calls and database writes must not happen during module import. `task/` files may parse arguments, preserve required function signatures, and call canonical jobs; they may not contain provider requests, algorithms, direct SQL, or durable Redis writes.

## Migration Program

The work is split into six independently specified and verified subprojects.

### 1. Daily Market Facts And Enrichment

Migrate upstream `_1`, `_4`, `_7`, and `_10` behavior into the current market-data module:

- Tushare securities and daily quotes;
- Shanghai index history and trading-date coverage;
- Tushare daily-basic market value and share fields;
- KPL/LonghuVIP DDE history and missing-value repair.

Targets are the existing `securities`, `daily_quotes`, and `index_daily` tables. Base daily quotes and enrichment fields use separate upserts. Missing enrichment values must not overwrite existing non-null canonical values.

### 2. Five-Minute Bars And KDJ

Migrate upstream `_2` and `_3` behavior through the existing BaoStock source and local indicator implementation:

- `intraday_bars_5m` remains keyed by deterministic code/time/adjustment identity;
- `kdj_indicators` is deterministically recalculated from complete `daily_quotes` history;
- historical gaps and incorrect existing rows can be repaired, rather than only appending the latest KDJ row.

The current historical list-shape adapter remains until active strategies migrate to canonical row contracts.

### 3. Jiuyan And Emotion

Migrate upstream `_5`, `_8`, and `_9` behavior using the current Jiuyan parser and emotion modules:

- facts are stored in `jiuyan_actions` before exports;
- INI files are generated from committed MySQL rows and can be regenerated;
- index breadth and emotion write `index_market_breadth` and `index_emotion_daily`;
- hot-board emotion writes `hot_board_emotion_daily` for explicitly requested dates;
- the upstream `0.985` limit threshold defect and ignored range parameters are not preserved.

### 4. THS Board Snapshot Collection

Restore upstream `_6` source behavior as a canonical collector for:

- `ths_boards`;
- `ths_board_constituents`;
- `ths_stock_relations`.

The collector fetches a complete snapshot, validates board/constituent/relationship counts and referential coverage, then replaces all three tables in one transaction. The existing read-only repository becomes the query boundary; a separate writer owns snapshot replacement.

### 5. Premarket Summaries And Task Ledger

Restore upstream `盘前纪要` behavior without making an INI file or Redis marker the authority.

Add `premarket_summaries` with:

- `trade_date` primary key;
- source name and URL;
- source checksum;
- original document text;
- ordered mention JSON and mention count;
- output path;
- collection and update timestamps.

Add `task_runs` with:

- run ID, task name, optional trade date, and scope key;
- status and current stage;
- attempt number;
- start/completion timestamps;
- result JSON and bounded error text;
- indexes for latest task/date/scope state.

The premarket workflow commits source facts first, generates the INI second, records output warnings in `task_runs`, and mirrors only short-lived completion state to Redis.

### 6. Unified Scheduling And Compatibility Retirement

Refactor upstream `每日更新` orchestration to call canonical jobs. Migrate all internal callers, tests, scripts, and documented commands before deleting obsolete compatibility modules and aliases.

Retain `task/fund_flow_backfill.py` as an explicitly requested extension. Replace or retire other wrappers only when searches and tests prove no supported consumer remains.

## Persistence Mapping

| Upstream behavior | Canonical MySQL target | Redis role |
| --- | --- | --- |
| Securities | `securities` | None |
| Daily quotes | `daily_quotes` | None |
| Index history | `index_daily` | None |
| Market value and shares | Existing `daily_quotes` enrichment columns | None |
| DDE | `daily_quotes.dde_net_amount` | None |
| Five-minute bars | `intraday_bars_5m` | None |
| KDJ | `kdj_indicators` | None |
| Jiuyan actions | `jiuyan_actions` | None |
| Index breadth/emotion | `index_market_breadth`, `index_emotion_daily` | None |
| Hot-board emotion | `hot_board_emotion_daily` | None |
| THS boards/relations | Existing `ths_*` tables | Optional expiring source-page cache |
| Dragon tiger | Existing dragon-tiger tables | Expiring lock and job polling |
| Premarket summary | New `premarket_summaries` | Expiring lock/completion mirror |
| Daily and long-running task status | New `task_runs` | Expiring lock and polling mirror |
| Fund flow | `fund_flow_snapshots`, `fund_flow_records` | Current-day rebuildable cache and transient event |
| Strategy picks | Existing strategy-pick tables | Current-day rebuildable cache and transient event |

## Daily Orchestration

The refactored close-of-day workflow is fact-first:

1. acquire a token-protected Redis lock with TTL;
2. insert `task_runs(status='running', stage='index')`;
3. update index history and trading dates;
4. update securities and daily quotes;
5. merge market-value/share and DDE enrichment;
6. collect date-scoped Jiuyan and dragon-tiger facts;
7. recalculate KDJ for the affected range;
8. recalculate market breadth, index emotion, and hot-board emotion;
9. commit `task_runs` as `succeeded` or `succeeded_with_warnings`;
10. update a short-lived Redis completion mirror and release the lock.

Five-minute history, THS full snapshots, and premarket summaries remain independent jobs. They do not extend the critical close-of-day chain.

Each external stage commits its own MySQL transaction. The workflow must not hold a transaction across remote calls. On failure, `task_runs.stage` and MySQL completeness determine the smallest resumable stage; a Redis completion key never proves durable success.

## Write And Cache Semantics

- Validate remote responses before writing.
- Write MySQL facts transactionally before any cache or notification.
- A cache failure does not roll back committed facts. Record `succeeded_with_warnings` and rebuild cache from MySQL.
- Market-data enrichment never replaces a non-null fact with a missing source value.
- THS snapshot replacement is all-or-nothing after completeness validation.
- Strategy collection saves snapshot, stocks, and events in one MySQL transaction before updating Redis.
- Fund-flow replacement updates snapshot `record_count`, removes boards absent from the replacement, and writes current rows in one transaction.
- HTTP/HTML page caches have TTL and source/date/version keys. Permanent page caches are not allowed.
- Process-local SSE queues are transient delivery only and are not historical event storage.

## Source Reliability

- Tushare uses bounded retries, token rotation, documented pacing, and explicit exhausted failure.
- BaoStock login/query/logout occurs inside calls, not imports; provider errors are returned, not handled with `exit()`.
- Browser collectors have an overall timeout and bounded attempts, and report slider/manual-verification state.
- THS collection uses bounded concurrency and global pacing, not only per-worker sleeps.
- DDE collection uses bounded concurrency, global pacing, a finite retry budget, and persists its failed-stock result in `task_runs.result_json`.
- Derived calculations have no network dependency and are deterministic for the same canonical inputs and parameters.

## Deletion And Retention

Delete after consumer migration:

- `task/data_sources.py`;
- `task/emotion_analysis.py`;
- obsolete aliases in daily, Jiuyan, premarket, and market-data wrappers;
- compatibility tests whose callers have moved to canonical APIs, but only after equivalent canonical behavior tests exist.

Retain until active strategy migration:

- the historical five-minute `get_data()` list-shape adapter and argument compatibility.

Retain as canonical or explicitly requested:

- `src/stock_lab/jobs/*` and `src/stock_lab/modules/*` owners;
- English schema and migration files;
- `task/fund_flow_backfill.py` and canonical fund-flow history code;
- current API modules and Redis fact-migration tools;
- guarded legacy data migrations and schema mapping.

Do not reintroduce direct references to old Chinese tables, `utils.db` SQL from task modules, import-time I/O, unbounded retries, or non-expiring Redis locks.

## Testing

Each upstream workflow receives a behavior contract covering:

- date boundaries and provider parameters;
- response validation and normalized fields;
- stable business keys and target tables;
- idempotent reruns and historical repair;
- amount, percentage, date, code, and adjustment units;
- intended export or API response.

Source and parser tests use fixed responses and never access the network. Repository tests cover transactions, empty-response protection, null-preserving enrichment, full snapshot replacement, and duplicate execution. Job tests cover stage failure, retry exhaustion, lock expiry, resumption, cache failure, and `task_runs` transitions.

Architecture tests enforce that task imports cause no ambient I/O and task modules remain thin. Persistence tests enforce MySQL-before-Redis ordering and MySQL rebuildability. Migration contract tests cover both clean initialization and incremental creation of `premarket_summaries` and `task_runs`.

The known user-owned `output/.gitignore` contract failure is ignored. Other test failures are not ignored.

## Rollout And Acceptance

Each subproject has its own spec, implementation plan, focused tests, migration verification, documentation update, and review checkpoint.

The program is complete when:

- every upstream task behavior is mapped to a canonical job or explicitly rejected as a defect;
- all durable facts are stored in canonical MySQL tables;
- Redis contains only expiring operational state and rebuildable current caches;
- the daily workflow resumes safely after any stage failure;
- no supported code reads or writes old Chinese tables;
- no task module performs import-time network or database work;
- all supported internal callers use canonical APIs or documented temporary adapters;
- historical backfill documentation reflects the final commands, limits, and recovery process;
- no destructive migration is executed as part of this program.
