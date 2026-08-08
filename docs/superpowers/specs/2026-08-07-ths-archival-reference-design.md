# THS Archival Reference Ownership Design

## Decision

The three THS tables are archived imported reference data. The public repository
has no active runtime producer or consumer for them, so this change does not add
a collector, scheduled job, API, or compatibility adapter.

`stock_lab.modules.ths` is the official owner of canonical English read access to:

- `ths_boards`
- `ths_board_constituents`
- `ths_stock_relations`

## Module Boundary

The module exposes frozen dataclass models for a board, a board constituent, and
a stock-to-board relation. `ThsRepository` receives the existing query callable
through its constructor and returns those models from explicit English-column
queries.

The repository supports the useful indexed filters already represented by the
schema: boards by board type, constituents by board code, board type, or stock
code, and stock relations by stock code. Results have deterministic ordering.
It has no engine dependency and exposes no insert, update, delete, replace, or
upsert operation.

## Migration And Lifecycle

The existing schema and import migration remain the sole population mechanism.
Tests verify every model column is created and explicitly copied from its legacy
source. The migration validation section reports source and target row counts for
all three THS table pairs.

The legacy THS tables can be dropped after migration parity is confirmed. The
English tables remain import-only archived reference data after that point; they
are not refreshed by the application.

## Verification

Repository unit tests cover model projection, each supported filter, query
parameterization, deterministic ordering, and the absence of write methods or an
engine dependency. Migration tests cover complete THS column mappings and all
three validation queries. A source contract scan rejects references to the three
legacy THS table identifiers outside migration and historical documentation.

The final verification runs the complete Python test suite, Python compilation,
the frontend test/build commands defined by the repository, and a diff whitespace
check before commit.
