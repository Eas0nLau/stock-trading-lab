# Dragon Tiger Premium Product Design

## Goal

Replace the legacy `游资溢价分析/` executable wrappers with an asynchronous page-triggered collection job, a premium-analysis API, and a Vue page that lets users trigger and inspect the analysis.

## Product Meaning

龙虎榜 records stocks and broker seats that appear on the exchange disclosure list. 游资溢价分析 uses broker history to estimate the average two-trading-day open-to-open return after a qualifying broker purchase, then selects current stocks associated with brokers whose historical sample and average return pass the configured thresholds.

The product is research assistance, not an automatic trading signal. Results depend on the selected dates, available daily quotes, broker-history coverage, net-buy threshold, and minimum sample count.

## Entry Points

### Page-Triggered Collection Job

The page sends:

```text
POST /api/v1/dragon-tiger/collection-jobs
{
  "startDate": 20260404,
  "latestDate": 20260806
}
```

The API returns HTTP 202 with a `jobId`. A one-shot background job executes four stages in order:

1. Collect all 龙虎榜 listing pages for trading dates in the requested range.
2. Refresh the broker directory.
3. Refresh broker history pages.
4. Analyze broker premium using the refreshed canonical data.

The page polls:

```text
GET /api/v1/dragon-tiger/collection-jobs/{jobId}
```

The job state is stored in Redis with a per-job key and an active-job lock. Duplicate active requests return HTTP 409. A failed stage records a non-secret error and stops later stages. The API process must not block the request thread while external pages are collected.

### Analysis API

```text
GET /api/v1/dragon-tiger/premium?start_date=20260404&latest_date=20260806
```

Response contract:

```json
{
  "startDate": 20260404,
  "latestDate": 20260806,
  "selectedCount": 2,
  "selectedCodes": ["000001.SZ", "600000.SH"],
  "sourceTables": ["dragon_tiger", "broker_listing_history", "daily_quotes"]
}
```

The endpoint analyzes existing canonical data only. It does not collect data or write analysis results. The collection-job status endpoint returns the final analysis response when stage 4 completes.

### Frontend

Add a `龙虎榜溢价` header action and a `DragonTigerPremium` tab. The page has start/latest date controls, an analyze action, loading/error/empty states, result count, selected stock codes, and the canonical source-table note. It does not claim that a result is a trading recommendation.

## Canonical Data

| Purpose | Table |
|---|---|
| 龙虎榜明细和买卖席位 | `dragon_tiger` |
| 营业部历史上榜记录 | `broker_listing_history` |
| 营业部目录 | `brokers` |
| 营业部统计 | `broker_top_stats` |
| 计算未来开盘收益 | `daily_quotes` |

The analysis response is ephemeral. Users can inspect source rows through MySQL or the existing research repositories; no new result table is introduced in this scope.

## Legacy Retirement

After collection jobs, API, frontend, product documentation, and tests pass:

- Delete `游资溢价分析/` and its compatibility test file.
- Remove its allowlist entry from `tests/test_cutover_contracts.py` and update compile/documentation references.
- Keep `strategy/龙虎榜_明日遴选.py` as a registered research strategy, but change its hardcoded direct invocation only if required by the new shared service contract.

## Error Handling

- Reject invalid or missing date query values with HTTP 422.
- Return HTTP 200 with `selectedCount=0` and an empty list when canonical source data has no qualifying rows.
- Return HTTP 500 with a non-secret error message for database failures; do not expose credentials or external response bodies.
- CLI exits non-zero on collection failure and prints a compact JSON error.

## Verification

- Unit tests cover CLI dispatch, date range handling, API response shape, empty results, and database failure mapping.
- Frontend tests cover API request construction and component states.
- Compatibility contracts prove no old `游资溢价分析` files remain after retirement.
- Run `uv run pytest --import-mode=importlib -q`, `npm test`, and `npm run build`.
- Product documentation must state exact old/new triggers and data locations.
