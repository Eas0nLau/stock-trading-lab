# Market Data Repository Migration Design

## Goal

Create the official English market-data module under `src/stock_lab/modules/market_data` and move shared application reads and writes to `securities`, `daily_quotes`, and `index_daily` without rewriting the 57 strategy files or TDX monitor files.

## Boundary

The new repositories expose canonical English rows and models only. They own table names, SQL column names, identifier normalization, and row conversion for securities, daily quotes, and index daily data. Legacy-shaped aliases remain only in the public adapters in `utils/common.py` and `utils/account.py`, because existing strategies still consume those utility return shapes.

The module will provide:

- `models.py`: typed canonical records for securities, daily quotes, and index daily rows.
- `helpers.py`: normalization for `ts_code`, six-digit symbols, dates, and external source rows.
- `repository.py`: query and upsert interfaces for the three English tables, using the existing callable query/database conventions.
- `__init__.py`: stable exports for the next strategy and monitor migration.

`task/data_sources.py` will use these helpers and repository interfaces while retaining its current Chinese function names as task compatibility entry points. Emotion jobs will consume the market-data repository for index and quote reads rather than embedding table access.

## Shared Utility Migration

`utils/common.py` will replace direct reads from `stock_basic`, `stock_daily`, and `akshare_sh000001` with repository calls or canonical English SQL. Its existing functions will preserve their current external return keys where concrete strategies require them. `utils/account.py` will use a shared daily-quote repository query and adapt canonical fields to its current `open`, `close`, `pre_close`, `high`, `low`, and `pct_chg` access pattern.

Identifiers will remain strings throughout repository and adapter boundaries. A code such as `000001.SZ` remains `000001.SZ`; a bare numeric symbol becomes `000001` for symbol comparisons, without converting away leading zeroes or exchange suffixes.

## Testing

Tests will be written first for:

- canonical model/helper normalization, including leading zeros and exchange suffixes;
- SQL/table and selected-column contracts for all three repositories;
- data-source result adapters and writes to English tables;
- shared utility adapters and account open/close paths using fakes;
- emotion repository/job consumption of canonical market data.

No test will connect to a real production database or inspect/write `data/`. Verification will include the full Python suite, `compileall`, frontend tests/build commands discovered from `front/package.json`, and a final legacy-reference scan limited to the explicitly deferred strategy, monitor, and research callers.

## Documentation

`docs/migration.md`, `docs/database-migrations.md`, and `docs/architecture.md` will describe the new module ownership, compatibility boundary, canonical columns, identifier rules, and the deferred strategy/TDX migration.
