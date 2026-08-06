# TDX Migration Design

## Goal

Move the official TongdaXin integration and monitoring behavior into the English `stock_lab` package while preserving the existing binary parsing, snapshot derivation, alert, and auction-monitor behavior. Existing Chinese script paths remain executable compatibility wrappers.

## Boundaries

- `stock_lab.infrastructure.tdx` owns validated TDX settings, plugin loading, cache refresh, quote subscription, snapshot access, and shutdown.
- `stock_lab.modules.tdx` owns stock-code models, local-file path/record parsing, snapshot pure logic, global-monitor pure logic, auction pure logic, and the securities-universe adapter.
- Official code receives `Settings` and `MarketDataRepository` or narrow callables. It does not import root `config.py`, `PyMySQL`, or legacy Chinese modules.
- The wrappers in `实时监控/tdx_全局监控.py` and `实时监控/tdx_竞价监控.py` import the English entry points and call `main()` only when executed.
- English identifiers and file names are used in official code. Chinese strings remain only where they are established display output or raw third-party values.

## Data Flow

Settings supplies the TDX root and refresh interval. The infrastructure adapter loads `PYPlugins/user/tqcenter.py` only when a real monitor is run. The global monitor normalizes configured codes, reads/parses local files or live snapshots, and applies pure alert logic. The auction monitor obtains the main-board, listed, non-ST universe through `MarketDataRepository.securities(market="主板")`, adapts rows to exchange-qualified codes, and applies pure auction signal logic.

## Error Handling

Invalid TDX configuration raises a clear validation error before plugin loading. Missing plugin files raise `FileNotFoundError`. Live refresh, subscription, and close failures retain the existing warning/cleanup behavior. Repository adaptation filters malformed or disallowed rows without opening a second database connection.

## Testing

Unit tests cover TDX path/config validation, securities-universe adaptation, representative day/minute binary parsing, snapshot and auction pure logic, and wrapper import/entry-point delegation. Tests use temporary files, fakes, and monkeypatches only; they never require a TDX installation, MySQL server, or network access.

## Documentation

Update architecture, migration, development, and README sections to identify the English official package, dependency direction, canonical securities repository, and compatibility wrapper paths.
