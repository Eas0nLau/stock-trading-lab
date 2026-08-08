# Dragon Tiger Premium Product Design

## Goal

Replace the legacy `游资溢价分析/` executable wrappers with a canonical collection CLI, a read-only premium-analysis API, and a Vue page that lets users trigger and inspect the analysis.

## Product Meaning

龙虎榜 records stocks and broker seats that appear on the exchange disclosure list. 游资溢价分析 uses broker history to estimate the average two-trading-day open-to-open return after a qualifying broker purchase, then selects current stocks associated with brokers whose historical sample and average return pass the configured thresholds.

The product is research assistance, not an automatic trading signal. Results depend on the selected dates, available daily quotes, broker-history coverage, net-buy threshold, and minimum sample count.

## Entry Points

### Collection CLI

All commands use the root `.env` database/Redis configuration:

```powershell
uv run python -m stock_lab.jobs.dragon_tiger collect-listings --date 20260806
uv run python -m stock_lab.jobs.dragon_tiger collect-listings --start-date 20260404 --end-date 20260806
uv run python -m stock_lab.jobs.dragon_tiger collect-broker-directory
uv run python -m stock_lab.jobs.dragon_tiger collect-broker-history
```

Collection writes only canonical tables and can be rerun through repository upsert behavior. It is deliberately not triggered from an HTTP request because external pages can be slow or unavailable.

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

The endpoint analyzes existing canonical data only. It does not collect data, write analysis results, or mutate Redis.

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

After CLI, API, frontend, product documentation, and tests pass:

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
