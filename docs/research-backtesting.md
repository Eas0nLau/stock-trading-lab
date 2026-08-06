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

Each entry has an explicit ASCII English identifier, the original Chinese
display name, compatibility source path, declared entrypoint, capabilities,
target-date requirement, and safety status. The catalog is static and does not
infer entrypoints from source files.

The current legacy launchers are explicitly marked `unsafe_legacy` (or
`unsupported` when no entrypoint exists). The registry raises
`ResearchSafetyError` before importing them, including in test contexts. This
prevents import-time database, network, and global-account side effects. A
migrated strategy may be marked `context_aware` only when it declares the
exact `run(context)` entrypoint; no `start`/`strategy` guessing is performed.

The CLI refuses to run without an explicitly injected context:

```python
from stock_lab.modules.research.cli import main
main(["run", "strategy_demo"], context=context)
```

The example intentionally returns a controlled safety error until that legacy
launcher is migrated to the context-aware contract. The CLI validates
`--target-date` and converts safety, import, and configuration failures to a
nonzero result without a traceback.

Chinese files under `strategy/` remain compatibility launchers and preserve
their original display names. They are not imported during discovery.

## Schema Migration

Active strategy SQL uses the canonical English schema: `daily_quotes`,
`securities`, `index_daily`, `kdj_indicators`, `intraday_bars_5m`,
`jiuyan_actions`, `dragon_tiger`, `broker_listing_history`,
`broker_top_stats`, and `brokers`. The contract test scans active strategy and
shared research sources for legacy table names.
