# Research And Backtesting

The official research API lives under `src/stock_lab/modules/research`. It is
safe to import and list strategies without a database, Redis, broker, or
network connection.

## Data Access

Create a `ResearchContext` with explicitly injected production repositories:

```python
from stock_lab.modules.research import ResearchContext, ResearchData
from stock_lab.modules.market_data import MarketDataRepository
from stock_lab.modules.dragon_tiger import DragonTigerRepository

data = ResearchData(market_repository, dragon_tiger_repository)
context = ResearchContext(
    market_data=data,
    dragon_tiger=dragon_tiger_repository,
    target_date=20260102,
    query_provider=query_provider,
)
```

`ResearchData` exposes canonical `securities`, `daily_quotes`, `index_daily`,
`kdj_indicators`, `intraday_bars_5m`, and Dragon Tiger access. Repository read
boundaries return qualified string `ts_code` values and six-character symbols.
Tests and local experiments can use `OfflineResearchProvider`; it creates an
in-memory SQLite provider and never opens MySQL, Redis, or a network client.
Fixture rows for securities, quotes, KDJ, Jiuyan, and Dragon Tiger are
normalized to qualified exchange codes at this boundary. Offline SQL schema or
query errors raise `ResearchExecutionError` instead of being treated as empty
results. Fixtures may also provide `redis_lists` for deterministic strategies
that consume captured Redis list snapshots.

Pure return calculations are available from `stock_lab.modules.research.backtest`.
They operate on caller-owned data and do not mutate the legacy global account.

## Strategy Registry

List all 57 legacy strategy launchers without importing them:

```powershell
uv run python -m stock_lab.modules.research list
```

Each entry has an explicit ASCII English identifier, the original Chinese
display name, compatibility source path, declared selector, capabilities,
target-date requirement, adapter family, and selection-data family. The static
catalog classifies every entry as `daily_quotes`, `dragon_tiger`, `jiuyan`,
`fund_flow`, `kdj`, or `dragon_tiger_premium`. Date and parameter variants may
share a family; tests require at least one non-empty behavioral fixture for
every declared family in addition to executing all 57 entries offline.

All 57 entries implement the same operation: `entry.run(context)` performs
single-date selection for `context.target_date` and returns `SelectionResult`.
The source-selector adapter compiles only the functions reachable from the
declared selector plus safe configuration assignments. It skips imports,
top-level calls, and legacy account/backtest entrypoints, then injects the
context repositories. `龙虎榜_明日遴选` uses the official Dragon Tiger premium
analytics adapter directly.

Run against deterministic built-in fixtures:

```powershell
uv run python -m stock_lab.modules.research run strategy_demo --target-date 20260102 --offline
uv run python -m stock_lab.modules.research backtest strategy_demo --start-date 20260102 --end-date 20260131 --offline
```

Use `--offline --fixture path/to/fixture.json` to provide local fixture tables.
Use `--provider local` to create repositories from the configured `MYSQL_*`
settings. Provider creation is explicit and listing strategies never opens a
connection. Configuration failures return nonzero without a traceback.

`backtest` iterates repository trading dates, invokes the same single-date
selector for each signal date, and calculates next-session open-to-close
returns. Pricing dates include the first available session after the requested
signal end date, so an end-date selection can still be evaluated. It does not
execute legacy global account functions.

Chinese files under `strategy/` remain source-compatible launchers and preserve
their original display names. They are parsed, not imported, by registry runs.

## Schema Migration

Active strategy SQL uses the canonical English schema: `daily_quotes`,
`securities`, `index_daily`, `kdj_indicators`, `intraday_bars_5m`,
`jiuyan_actions`, `dragon_tiger`, `broker_listing_history`,
`broker_top_stats`, and `brokers`. The contract test scans active strategy and
shared research sources for legacy table names. Additional scans reject integer
stock-code conversion, raw tuple-based `ts_code IN` clauses, and unnormalized
daily-quote/security joins. Official stock-code filters use bound parameters;
strategy execution does not expose a helper for rendering SQL literals.
