# Dragon-Tiger and Broker Migration Design

## Scope

Move production dragon-tiger collection, broker collection, broker-history collection,
and broker premium analysis from `游资溢价分析` into
`stock_lab.modules.dragon_tiger`. Cut all active Python readers and writers over from
the legacy Chinese tables to `dragon_tiger`, `broker_listing_history`,
`broker_top_stats`, and `brokers`. Dragon-tiger analytics read prices from
`daily_quotes` through the market-data repository.

The migration must preserve source values, filters, amount units, listing identity,
broker deduplication, and the legacy premium calculation. It must not contact a live
website, Redis instance, or database during tests.

## Architecture

The official package has five responsibilities:

- `models.py` defines immutable English records matching the canonical schema.
- `parsing.py` translates source HTML and Chinese visible values into canonical
  records. Source-specific text stays at this adapter edge.
- `repository.py` owns queries and upserts for the four canonical tables.
- `collectors.py` orchestrates injected HTTP/cache providers, parsers, trading dates,
  and repository writes.
- `analytics.py` computes broker premium selections from canonical repository rows
  and market-data repository quotes.

No official module refers to a legacy table or exposes Chinese identifiers. SQL
parameters are bound through repository methods except fixed schema identifiers.

## Compatibility

The existing Chinese paths remain only where they are concrete execution entrypoints.
They construct existing local infrastructure dependencies and delegate to the official
collectors or analysis function. Importing a compatibility module performs no network
or database work. Existing strategy files keep their algorithms and result shapes but
their dragon-tiger SQL uses canonical table and column names.

## Data Flow

The listing collector obtains trading dates from `daily_quotes`, fetches one source
page per date, parses canonical listings, derives unique brokers and listing-history
rows, then upserts each collection. Broker-directory and broker-history collectors use
the same repository and injected fetch functions. Empty or unpublished pages produce
no writes for that page; malformed structural input raises a parser error with local
context instead of silently producing partial rows.

Premium analysis loads listings for the latest date and broker history for the
requested interval. It applies the existing net-buy, excluded-broker, minimum sample,
and average-return thresholds. For each historical listing it obtains ordered quote
rows, calculates the return from the next session open to the following session open,
and ranks the latest-date candidates using the same grouping and deduplication rules.

## Verification

Unit tests cover amount and page parsing, repository SQL and upserts, collector
dependency boundaries, premium-analysis parity, and compatibility wrappers. Contract
tests reject active legacy dragon-tiger table references. Verification includes full
pytest, Python compileall, frontend tests and build, and a final diff/status review.

## Migration Documentation

`docs/migration.md` records ownership and compatibility status.
`docs/database-migrations.md` removes dragon-tiger and broker code from the blockers
for dropping the legacy schema while retaining unrelated blockers.
