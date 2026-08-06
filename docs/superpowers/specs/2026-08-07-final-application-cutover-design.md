# Final Application Cutover Design

## Goal

Complete the application-code cutover to `src/stock_lab` so official code owns
all active collection, analysis, persistence, and integration behavior. Preserve
documented direct script paths only as thin forwarding wrappers. Do not execute
`003_drop_legacy_schema.sql`; leave destructive schema removal for a separately
approved operation.

## Ownership Boundaries

### Market data and Jiuyan

`stock_lab.modules.market_data` owns source normalization, persistence-facing
collection services, and Jiuyan response parsing. Third-party clients and browser
mechanics live under `stock_lab.infrastructure`. `task/data_sources.py` and
`task/_5_韭研公社异动.py` preserve documented callables by forwarding to official
English APIs and contain no substantial source or persistence implementation.

### Emotion

Index-cycle and hot-board algorithms move into English modules under
`stock_lab.modules.emotion`. Emotion jobs invoke those implementations directly.
The old Chinese emotion modules contain compatibility forwarding only, and dormant
legacy REST route registration is removed. Hot-board compatibility reads canonical
tables through the English repository and service; it does not query old tables.

### Fund flow and strategy pick

Browser interaction belongs to English infrastructure adapters. Fund-flow and
strategy-pick modules own collection scheduling, parsing, and persistence. All
in-repository fund-flow consumers use `FundFlowRepository` V1 keys. Legacy Redis
fallback reads, dual-writes, and compatibility persistence are removed after those
consumers switch.

### Dragon tiger

Official adapters own dragon-tiger HTTP sources and cache behavior. The
`游资溢价分析` package remains only as documented executable wrappers and does not
own collection, HTTP, cache, persistence, or premium-analysis logic.

### Naming and compatibility

Identifiers exported under `src/stock_lab` are English. This includes INI-writing
and premium-analysis APIs. Compatibility packages may retain Chinese public names
only to preserve documented direct script imports, and each such name delegates to
an English implementation.

## Data Flow

External source adapters return source payloads to domain collectors. Collectors
normalize payloads into canonical English records and call repositories. Domain
services and jobs consume canonical repositories only. Compatibility scripts call
the same domain services; they do not access browser, network, Redis, or SQL APIs
directly except for minimal dependency composition where an existing direct script
requires it.

Fund-flow writes target only `fund_flow:v1:*`. Reads target only V1 repository
methods. Canonical SQL targets only English tables. No fallback can silently revive
legacy storage after this cutover.

## Error Handling

Existing retry, validation, timeout, and incomplete-response behavior is preserved
when implementations move. Optional clients remain lazy so imports never contact a
network or database. Tests inject fake clients, repositories, clocks, and payloads.

## Enforcement

Contract scans fail when:

- official `src/stock_lab` code imports Chinese compatibility modules;
- active code references legacy Redis keys or legacy tables;
- `src/stock_lab` defines or exports Chinese identifiers;
- compatibility directories exceed thin-wrapper limits or contain forbidden
  network, browser, persistence, route, or algorithm implementation patterns.

Allow-lists are narrow and documented for migration SQL, historical documentation,
test fixtures, and display-only Chinese strings.

## Verification

Add focused unit and contract tests before moving each implementation. Run the full
Python test suite without real network or database access, compile all Python code,
run frontend tests and production build, inspect repository scans, and review the
final diff. Commit all intended code, tests, and documentation while leaving the
pre-existing untracked `data/` directory untouched. Do not execute migration `003`.
