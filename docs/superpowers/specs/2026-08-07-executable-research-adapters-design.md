# Executable Research Adapters Design

## Goal

Make every one of the 57 catalogued research strategies runnable through
`run(context)` without importing legacy modules or using global database,
network, or account state. A run performs single-date stock selection for
`context.target_date`; shared orchestration performs date-range backtests.

## Architecture

The registry remains static and explicit. Each entry declares an English
identifier, Chinese display name, source path, adapter family, source
entrypoint, required capabilities, and strategy-specific parameters. All
entries are runnable; there are no blocked safety statuses.

Fifty-six source files define `strategy(filtered_codes, target_date)`. Their
adapter uses a source-preserving selector runtime: parse the file with `ast`,
compile function definitions plus literal configuration assignments, and
inject safe dependencies. It never executes import nodes, top-level calls,
`if __name__` blocks, or module initialization. Safe globals provide pandas,
NumPy, datetime utilities, a sequential Pool replacement, inert progress
wrapping, repository-backed `common`, context-backed `db`, account state
isolated to the run, and the official five-minute data interface. Literal
constants in date/config variants remain attached to their source strategy.

`龙虎榜_明日遴选.py` is an executable Dragon Tiger premium family adapter. It
calls the official `analyze_broker_premium` implementation with the injected
Dragon Tiger and market-data repositories and projects selected codes to the
standard selection result.

## Context And Providers

`ResearchContext` has an explicit `target_date`, `ResearchData`, query provider,
and isolated account state. Security codes are normalized at the repository
boundary: official methods accept qualified or bare values and return canonical
qualified `ts_code` plus six-character `symbol` where applicable.

The configured local provider creates `MarketDataRepository` and
`DragonTigerRepository` from project settings and the lazy local MySQL
resources. No connection is opened by listing strategies or parsing CLI
arguments. The provider is selected explicitly with `--provider local`.

`--offline` creates an in-memory SQLite fixture provider. It registers the
small MySQL-compatible functions used by selector SQL and loads canonical
fixture tables. It never accesses MySQL, Redis, or the network. Optional
`--fixture PATH` loads JSON fixture rows; otherwise a deterministic built-in
fixture is used.

## Selection And Backtesting

All adapters return `SelectionResult`: strategy identifier, display name,
target date, normalized selected rows, and diagnostics. Empty selections are
valid results, not errors.

The shared backtest runner iterates canonical trading dates, invokes the same
single-date adapter for each date, and computes next-session open-to-close
returns through `ResearchData`. It does not invoke legacy buy/sell/account
functions. Existing position sizing and aggregation primitives remain the
shared calculation layer.

## Launcher Cleanup

Legacy launchers retain their Chinese names and direct-launch compatibility,
but all stock-code handling uses canonical strings. Integer casts and literal
SQL tuple construction for `ts_code` are replaced with `normalize_symbol`,
`normalize_ts_code`, and parameterized `stock_code_filter` calls. Contract
tests scan every launcher for incompatible integer casts and raw `IN` filters.

## Error Handling

Missing target dates, malformed fixture files, unknown providers, unavailable
configured local resources, and source adapter failures become controlled
research configuration/execution errors. CLI reports them on stderr and
returns nonzero without a traceback. Empty fixture data and empty selections
remain successful.

## Testing

- Every static registry entry resolves and runs with an offline test context.
- Tests monkeypatch global DB/network constructors to fail, proving offline
  execution does not touch them.
- Representative volume/price, trend, new-high, KDJ, Dragon Tiger, and premium
  families run against canonical fixtures.
- Shared backtest orchestration is tested across multiple fixture dates.
- Contract scans cover legacy tables, raw integer stock-code conversion,
  literal `ts_code IN` construction, and unnormalized quote/security joins.
- Full pytest, compileall, frontend tests/build, and diff checks run before the
  implementation commit.
