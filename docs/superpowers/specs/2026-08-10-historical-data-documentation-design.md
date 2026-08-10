# Historical Data Documentation Design

## Goal

Produce maintainable handover documentation that tells operators which historical datasets the current project needs, which providers can supply them, and how to run and verify every currently supported backfill workflow.

The upstream repository audit is research input only. It will not appear in the final handover documents.

## Deliverables

### `docs/historical-data-source-matrix.md`

This document describes the current project's historical-data requirements and source decisions.

For each dataset it will record:

- business purpose and canonical MySQL target;
- current project collector or computation entry point;
- current provider and available date depth;
- whether AkShare can supply the same semantics;
- one of four source decisions: direct replacement, partial coverage, unavailable, or semantic mismatch;
- exact AkShare API names where applicable;
- stability, authentication, verification, and request-frequency constraints;
- the recommended production source and fallback policy.

The matrix will cover at least securities, daily quotes, index history and trading dates, five-minute bars, industry and concept boards, fund flow, limit-up and Jiuyan actions, dragon-tiger data, KDJ, emotion data, financial data, margin data, northbound data, IPO data, dividends, and chip distribution.

It will explicitly state that derived indicators such as KDJ should be recomputed locally, and that Jiuyan editorial data, historical THS relationships, vendor-specific DDE values, and exact THS dragon-tiger semantics must not be silently replaced with superficially similar AkShare fields.

### `docs/historical-data-backfill-runbook.md`

This document is an operator runbook for the current repository. It will contain only commands and callable interfaces that actually exist.

Workflows will be labelled as:

- supported CLI;
- callable API only;
- upstream-limited;
- retired or migration-only.

The runbook will organize execution in dependency order:

1. environment and service checks;
2. database schema and legacy-data migration checks;
3. trading calendar, index history, securities, and daily quotes;
4. five-minute bars and other independent fact data;
5. dragon-tiger, Jiuyan, and fund-flow history;
6. KDJ, market breadth, index emotion, and hot-board emotion recomputation;
7. MySQL validation and current-day Redis cache checks.

Each workflow will document:

- command or Python entry point and parameters;
- prerequisites and required environment variables;
- source provider and target tables;
- date-selection behavior and dependency order;
- request pacing, retries, browser verification, and provider-specific limits;
- idempotency and duplicate handling;
- pre-run checks, post-run SQL validation, and expected results;
- failure symptoms, restart scope, and recovery steps;
- known gaps where an operator CLI does not yet exist.

The runbook will include separate checklists for first deployment, current-year backfill, one-day repair, and interrupted-run recovery. It will warn against destructive schema operations and fabricated zero or empty records.

## Data And Operational Rules

- MySQL is the historical system of record. Redis is limited to current-day cache, indexes, and events.
- Remote failures must be reported by date and entity. A failed source response must not be converted into zero-valued data.
- Existing canonical batches and rows are skipped or upserted according to the repository contract so operators can resume interrupted work.
- AkShare calls are treated as calls to their documented upstream providers, not as an independent data authority.
- AkShare workflows must be serial and rate-limited. Fund-flow documentation will describe the intended one-second global interval and exponential retry policy as planned until the implementation actually uses it.
- The documentation must distinguish current behavior from planned changes. It must not present the current direct-EastMoney fund-flow adapter as an AkShare workflow.
- Validation uses target-table date coverage, row counts, unique keys, required fields, amount units, and representative samples.

## Evidence And Maintenance

Every source decision will cite current project files and official provider documentation. Operator commands will be checked against the current CLI parsers or public Python functions.

The two handover documents will be written in Chinese. Commands, API names, environment variables, table names, field names, and source identifiers will retain their exact code spelling.

The final documents will identify stale README statements when they conflict with code. They will not reproduce the upstream repository inventory or its missing-task history.

## Acceptance Criteria

- Both documents exist under `docs/` and cross-link to each other.
- The source matrix gives an explicit AkShare suitability decision for every historical dataset used by the current project.
- The runbook covers every current remote collector, derived recomputation, and legacy migration relevant to historical data.
- Every documented shell command exists and every non-CLI workflow is clearly labelled as a Python API.
- Request-frequency guidance is present for AkShare, Tushare, Jiuyan, EastMoney browser collection, BaoStock, and THS.
- Each persisted workflow includes target tables, idempotency behavior, validation queries, and recovery guidance.
- Current implementation, upstream limitation, and planned work are visibly distinct.
- No original-repository audit content is included in the final handover documents.
