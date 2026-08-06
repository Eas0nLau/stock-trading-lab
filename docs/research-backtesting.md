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
    account=account_adapter,
)
```

`ResearchData` exposes canonical `securities`, `daily_quotes`, `index_daily`,
`kdj_indicators`, `intraday_bars_5m`, and Dragon Tiger access. Tests should use
`ResearchContext.test_context()` or fake repositories. Missing capabilities
raise `ResearchSafetyError` instead of silently creating a live connection.

Pure return calculations are available from `stock_lab.modules.research.backtest`.
They operate on caller-owned data and do not mutate the legacy global account.

## Strategy Registry

List all 57 legacy strategy launchers without importing them:

```powershell
uv run python -m stock_lab.modules.research list
```

Each entry has an ASCII English identifier, the original Chinese display name,
and its compatibility source path. A selected entry is loaded lazily and
adapted to the uniform `run(context) -> result` contract. Strategies with a
legacy `strategy(filtered_codes, target_date)` entrypoint receive those values
through explicit run parameters; callers must still supply the date and any
other selection inputs.

The CLI refuses to run without an explicitly injected context:

```python
from stock_lab.modules.research.cli import main
main(["run", "strategy_demo"], context=context)
```

Chinese files under `strategy/` remain compatibility launchers and preserve
their original display names. They are not imported during discovery.

## Schema Migration

Active strategy SQL uses the canonical English schema: `daily_quotes`,
`securities`, `index_daily`, `kdj_indicators`, `intraday_bars_5m`,
`jiuyan_actions`, `dragon_tiger`, `broker_listing_history`,
`broker_top_stats`, and `brokers`. The contract test scans active strategy and
shared research sources for legacy table names.
