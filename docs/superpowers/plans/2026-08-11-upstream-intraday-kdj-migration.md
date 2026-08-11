# Upstream Intraday And KDJ Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate upstream five-minute BaoStock history and KDJ behavior into canonical jobs, restore thin `_2` and `_3_kdj` entry points, eliminate minute-identity duplicates, and add canonical KDJ to daily orchestration.

**Architecture:** BaoStock remains a lazy single-security source. A bounded bulk coordinator fetches and normalizes securities concurrently but commits each security from the coordinator thread. Compatibility KDJ exactly reproduces upstream values, while canonical KDJ persistence retains the corrected formula and joins the close-of-day critical chain.

**Tech Stack:** Python 3.12, pandas, BaoStock, SQLAlchemy/MySQL 8, `concurrent.futures`, pytest, uv, PowerShell 5.1.

## Global Constraints

- Canonical five-minute `trade_time` is the 12-digit minute `YYYYMMDDHHMM`.
- Canonical five-minute `data_id` is `{stock_code}_{trade_time}_{adjustment_flag}` using the 12-digit minute.
- Both 12-digit migrated rows and 17-digit BaoStock rows must resolve to the same identity.
- Bulk five-minute CLI requires explicit start and end dates; it never defaults to 2025 or to an unbounded all-market run.
- Bulk concurrency defaults to 4 and must remain configurable and bounded.
- Remote fetches occur before MySQL transactions; one security failure cannot roll back another security.
- Five-minute and KDJ historical facts live only in MySQL, never Redis.
- `calculate_ths_kdj` reproduces upstream warm-up, flat-window, and `m1`/`m2` values exactly.
- Canonical `calculate_kdj` retains its current expanding-window and flat-range RSV=50 semantics.
- Canonical KDJ runs after daily market facts and before Jiuyan/emotion; its failure prevents the daily completion key.
- Do not restore import-time provider login, direct SQL in task wrappers, `exit()`, recursive retry, legacy table writes, integer stock-code identity, or latest-row-only KDJ persistence.
- Continue ignoring only the user-approved `output/.gitignore` cutover assertion; every other test failure must be fixed.

---

### Task 1: Canonical Five-Minute Identity And Existing-Row Cleanup

**Files:**
- Modify: `src/stock_lab/modules/market_data/parsing.py`
- Modify: `tests/unit/modules/market_data/test_intraday_kdj.py`
- Create: `db/migrations/005_normalize_intraday_minute_identity.sql`
- Modify: `tests/integration/database/test_schema_migration.py`
- Modify: `docs/database-migrations.md`

**Interfaces:**
- Consumes: source dictionaries containing `date`, `time`, `code`, OHLCV, amount, and `adjustflag`.
- Produces: `normalize_intraday_bar(row) -> dict` with 12-digit `trade_time` and stable `data_id`; an idempotent SQL maintenance migration for already-written 17-digit rows.

- [ ] **Step 1: Update the failing parser identity tests**

Replace the expected identity in `test_intraday_bar_normalizes_source_types_and_identity` and add a 12/17-digit equivalence test:

```python
def test_intraday_bar_normalizes_source_types_and_identity():
    row = normalize_intraday_bar({
        "date": "2026-08-06",
        "time": "20260806093500000",
        "code": "sz.000001",
        "open": "10.1",
        "high": "10.8",
        "low": "9.9",
        "close": "10.5",
        "volume": "100",
        "amount": "1030.5",
        "adjustflag": "3",
    })

    assert row["trade_time"] == 202608060935
    assert row["data_id"] == "000001_202608060935_3"


def test_intraday_bar_uses_same_identity_for_minute_and_baostock_timestamp():
    base = {
        "date": "2026-08-06",
        "code": "sz.000001",
        "open": "10",
        "high": "11",
        "low": "9",
        "close": "10.5",
        "volume": "100",
        "amount": "1050",
        "adjustflag": "3",
    }

    minute = normalize_intraday_bar({**base, "time": "202608060935"})
    full = normalize_intraday_bar({**base, "time": "20260806093500000"})

    assert minute["trade_time"] == full["trade_time"] == 202608060935
    assert minute["data_id"] == full["data_id"] == "000001_202608060935_3"
```

- [ ] **Step 2: Run the parser test and verify failure**

Run:

```powershell
uv run --frozen pytest -q tests/unit/modules/market_data/test_intraday_kdj.py
```

Expected: FAIL because 12-digit timestamps are rejected and 17 digits are preserved.

- [ ] **Step 3: Normalize to minute precision**

Change the time validation and identity block to:

```python
trade_time_raw = str(row.get("time") or "").strip()
if not trade_date or len(trade_time_raw) < 12 or not trade_time_raw.isdigit():
    raise DataValidationError("Invalid intraday date or time")
trade_time_text = trade_time_raw[:12]
if int(trade_time_text[:8]) != trade_date:
    raise DataValidationError("Intraday date and time do not match")
trade_time = int(trade_time_text)
```

Keep `data_id` as `f"{symbol}_{trade_time}_{adjustment_flag}"`.

- [ ] **Step 4: Add the canonical cleanup migration contract**

Create `005_normalize_intraday_minute_identity.sql` using a temporary table inside one transaction:

```sql
START TRANSACTION;

DROP TEMPORARY TABLE IF EXISTS `intraday_bars_5m_minute_normalized`;

CREATE TEMPORARY TABLE `intraday_bars_5m_minute_normalized`
LIKE `intraday_bars_5m`;

INSERT INTO `intraday_bars_5m_minute_normalized` (
  `data_id`, `trade_date`, `trade_time`, `stock_code`, `open_price`,
  `high_price`, `low_price`, `close_price`, `volume`, `turnover`,
  `adjustment_flag`
)
SELECT
  CONCAT(
    `stock_code`, '_', LEFT(CAST(`trade_time` AS CHAR), 12), '_',
    `adjustment_flag`
  ),
  `trade_date`,
  CAST(LEFT(CAST(`trade_time` AS CHAR), 12) AS UNSIGNED),
  `stock_code`, `open_price`, `high_price`, `low_price`, `close_price`,
  `volume`, `turnover`, `adjustment_flag`
FROM `intraday_bars_5m`
ORDER BY CHAR_LENGTH(CAST(`trade_time` AS CHAR)), `trade_time`
ON DUPLICATE KEY UPDATE
  `trade_date` = VALUES(`trade_date`),
  `trade_time` = VALUES(`trade_time`),
  `stock_code` = VALUES(`stock_code`),
  `open_price` = VALUES(`open_price`),
  `high_price` = VALUES(`high_price`),
  `low_price` = VALUES(`low_price`),
  `close_price` = VALUES(`close_price`),
  `volume` = VALUES(`volume`),
  `turnover` = VALUES(`turnover`),
  `adjustment_flag` = VALUES(`adjustment_flag`);

DELETE FROM `intraday_bars_5m`;

INSERT INTO `intraday_bars_5m` (
  `data_id`, `trade_date`, `trade_time`, `stock_code`, `open_price`,
  `high_price`, `low_price`, `close_price`, `volume`, `turnover`,
  `adjustment_flag`
)
SELECT
  `data_id`, `trade_date`, `trade_time`, `stock_code`, `open_price`,
  `high_price`, `low_price`, `close_price`, `volume`, `turnover`,
  `adjustment_flag`
FROM `intraday_bars_5m_minute_normalized`;

DROP TEMPORARY TABLE `intraday_bars_5m_minute_normalized`;
COMMIT;
```

Add `NORMALIZE_INTRADAY_PATH` to the migration test and assert the SQL contains the 12-digit `LEFT`, temporary-table rebuild, duplicate-key collapse, transaction, and no legacy table reference.

- [ ] **Step 5: Run parser and migration contract tests**

Run:

```powershell
uv run --frozen pytest -q tests/unit/modules/market_data/test_intraday_kdj.py tests/integration/database/test_schema_migration.py
```

Expected: PASS.

- [ ] **Step 6: Document migration execution order and commit**

Document that `005` runs after canonical schema/data migration and before new five-minute backfills. Then commit:

```powershell
git add -- "src/stock_lab/modules/market_data/parsing.py" "tests/unit/modules/market_data/test_intraday_kdj.py" "db/migrations/005_normalize_intraday_minute_identity.sql" "tests/integration/database/test_schema_migration.py" "docs/database-migrations.md"
git commit -m "fix: normalize five-minute bar identity"
```

### Task 2: BaoStock Five-Minute Range Validation

**Files:**
- Modify: `src/stock_lab/infrastructure/market_data/baostock.py`
- Modify: `tests/unit/infrastructure/market_data/test_baostock.py`

**Interfaces:**
- Consumes: `fetch_5m_bars(start_date, end_date, ts_code)` values accepted by `_iso_date` and `_baostock_code`.
- Produces: inclusive valid range requests; `DataValidationError` before login when the normalized start date is later than the end date.

- [ ] **Step 1: Add a failing reversed-range test**

```python
def test_five_minute_source_rejects_reversed_range_before_login():
    client = Client(Result([]))

    with pytest.raises(DataValidationError, match="range"):
        BaoStockSource(client=client).fetch_5m_bars(
            20260807,
            20260806,
            "000001.SZ",
        )

    assert client.login_count == 0
```

- [ ] **Step 2: Run the focused source test and verify failure**

Run:

```powershell
uv run --frozen pytest -q tests/unit/infrastructure/market_data/test_baostock.py::test_five_minute_source_rejects_reversed_range_before_login
```

Expected: FAIL because the source currently submits the reversed request.

- [ ] **Step 3: Validate normalized ISO dates before `_query_rows`**

Implement:

```python
start_iso = _iso_date(start_date)
end_iso = _iso_date(end_date)
if start_iso > end_iso:
    raise DataValidationError(
        f"Invalid BaoStock five-minute range: {start_date!r}-{end_date!r}"
    )
return self._query_rows(
    _baostock_code(ts_code),
    BAOSTOCK_5M_FIELDS,
    start_date=start_iso,
    end_date=end_iso,
    frequency="5",
    adjustflag="3",
)
```

- [ ] **Step 4: Run the complete BaoStock source test**

Run:

```powershell
uv run --frozen pytest -q tests/unit/infrastructure/market_data/test_baostock.py
```

Expected: PASS.

- [ ] **Step 5: Commit range validation**

```powershell
git add -- "src/stock_lab/infrastructure/market_data/baostock.py" "tests/unit/infrastructure/market_data/test_baostock.py"
git commit -m "fix: validate BaoStock intraday ranges"
```

### Task 3: Bounded Five-Minute History Coordinator

**Files:**
- Modify: `src/stock_lab/jobs/intraday_bars_5m.py`
- Create: `tests/unit/jobs/test_intraday_backfill.py`
- Modify: `tests/unit/jobs/test_market_data_jobs.py`

**Interfaces:**
- Consumes: `fetch_intraday_bars_5m(start_date, end_date, ts_code, source=None) -> list[dict]`, `repository.securities() -> list[dict]`, and `repository.upsert_intraday_bars_5m(rows) -> int`.
- Produces: `backfill_intraday_bars_5m(start_date, end_date, *, stock_codes=None, source_factory=None, repository=None, max_workers=4) -> dict`.

- [ ] **Step 1: Add failing coordinator tests**

Create fake sources and repository that assert:

```python
def test_intraday_backfill_processes_explicit_codes_and_sorts_results():
    result = backfill_intraday_bars_5m(
        20260806,
        20260807,
        stock_codes=["600000.SH", "000001.SZ"],
        source_factory=SourceFactory(),
        repository=Repository(),
        max_workers=2,
    )

    assert result == {
        "status": "success",
        "updated": 2,
        "processed_codes": ["000001.SZ", "600000.SH"],
        "empty_codes": [],
        "failed": [],
    }
```

Add separate tests for canonical-universe lookup, partial failure with successful writes retained, all-empty failure, malformed-row failure isolated to one security, empty universe validation, and `max_workers <= 0` validation.

The fake repository must record the thread identifier used by every upsert and assert every write occurs on the coordinator thread.

- [ ] **Step 2: Run the coordinator tests and verify import failure**

Run:

```powershell
uv run --frozen pytest -q tests/unit/jobs/test_intraday_backfill.py
```

Expected: collection FAIL because `backfill_intraday_bars_5m` does not exist.

- [ ] **Step 3: Implement scope resolution and worker fetches**

Add imports for `ThreadPoolExecutor`, `as_completed`, `normalize_ts_code`, and `DataValidationError`.

Use this shape:

```python
def backfill_intraday_bars_5m(
    start_date,
    end_date,
    *,
    stock_codes=None,
    source_factory=None,
    repository=None,
    max_workers=4,
):
    repository = repository or _default_repository()
    max_workers = int(max_workers)
    if max_workers <= 0:
        raise DataValidationError("max_workers must be greater than zero")
    if stock_codes is None:
        stock_codes = [row["ts_code"] for row in repository.securities()]
    codes = sorted({normalize_ts_code(code) for code in stock_codes if code})
    if not codes:
        raise DataValidationError("No securities available for intraday backfill")
    source_factory = source_factory or BaoStockSource

    def fetch(code):
        return fetch_intraday_bars_5m(
            start_date,
            end_date,
            code,
            source=source_factory(),
        )
```

Submit only fetch/normalization work to the executor. Iterate completed futures in the coordinator thread, call `repository.upsert_intraday_bars_5m(rows)` there, and accumulate deterministic result fields.

- [ ] **Step 4: Implement result status rules**

Use these exact rules:

```python
if result["failed"]:
    result["status"] = "failed"
elif not result["processed_codes"] and len(result["empty_codes"]) == len(codes):
    result["status"] = "failed"
```

Sort `processed_codes`, `empty_codes`, and `failed` by `stock_code`. Do not write Redis state.

- [ ] **Step 5: Run all intraday job tests**

Run:

```powershell
uv run --frozen pytest -q tests/unit/jobs/test_intraday_backfill.py tests/unit/jobs/test_market_data_jobs.py tests/unit/modules/market_data/test_intraday_kdj.py
```

Expected: PASS.

- [ ] **Step 6: Commit the coordinator**

```powershell
git add -- "src/stock_lab/jobs/intraday_bars_5m.py" "tests/unit/jobs/test_intraday_backfill.py" "tests/unit/jobs/test_market_data_jobs.py"
git commit -m "feat: add bounded intraday history backfill"
```

### Task 4: Restore The Upstream Five-Minute Task Surface

**Files:**
- Modify: `task/_2_分时数据获取_5分k.py`
- Modify: `tests/unit/compatibility/test_intraday_wrapper.py`
- Modify: `tests/test_cutover_contracts.py`

**Interfaces:**
- Consumes: `fetch_intraday_bars_5m` and `backfill_intraday_bars_5m` from Task 3.
- Produces: upstream names `get_data`, `process_stock_batch`, `main`, and an import-safe CLI.

- [ ] **Step 1: Add failing compatibility and CLI tests**

Add tests that monkeypatch `_backfill_intraday_bars_5m` and require:

```python
assert module.main(
    20260801,
    20260807,
    stock_codes=["000001.SZ"],
    max_workers=2,
) == {"status": "success"}
assert calls == [{
    "start_date": 20260801,
    "end_date": 20260807,
    "stock_codes": ["000001.SZ"],
    "max_workers": 2,
}]
```

Require `process_stock_batch((["000001.SZ"], 20260801, 20260807))` to delegate with `max_workers=1`. Add CLI parser tests for required dates, repeated `--stock-code`, and `--max-workers`.

Update the existing legacy row expectation so `time` is `202608060935`, while preserving the ten-column order and current compact numeric string projection.

- [ ] **Step 2: Run wrapper tests and verify failure**

Run:

```powershell
uv run --frozen pytest -q tests/unit/compatibility/test_intraday_wrapper.py
```

Expected: FAIL because `main`, `process_stock_batch`, and CLI parsing are absent and time remains 17 digits.

- [ ] **Step 3: Add thin delegating functions**

Import the bulk function as `_backfill_intraday_bars_5m` and implement:

```python
def process_stock_batch(args):
    stock_codes, start_date, end_date = args
    return _backfill_intraday_bars_5m(
        start_date,
        end_date,
        stock_codes=stock_codes,
        max_workers=1,
    )


def main(start_date, end_date, stock_codes=None, max_workers=4):
    return _backfill_intraday_bars_5m(
        start_date,
        end_date,
        stock_codes=stock_codes,
        max_workers=max_workers,
    )
```

Add `_cli(argv=None)` with required `--start-date`, required `--end-date`, repeatable `--stock-code`, and integer `--max-workers` defaulting to 4. Print JSON and return exit code 0 only for `status='success'`.

- [ ] **Step 4: Preserve wrapper constraints**

Add `"task/_2_分时数据获取_5分k.py": 140` to `WRAPPER_LIMITS` and verify it contains no direct provider, database, Redis, requests, SQLAlchemy, or legacy table access. Keep `get_data` support for positional `code` and keyword-only `stock`.

- [ ] **Step 5: Run compatibility and cutover tests**

Run:

```powershell
uv run --frozen pytest -q tests/unit/compatibility/test_intraday_wrapper.py tests/test_cutover_contracts.py -k "not output_directory_tracks_only_ignore_policy"
```

Expected: PASS.

- [ ] **Step 6: Commit the `_2` entry point**

```powershell
git add -- "task/_2_分时数据获取_5分k.py" "tests/unit/compatibility/test_intraday_wrapper.py" "tests/test_cutover_contracts.py"
git commit -m "feat: restore upstream intraday task surface"
```

### Task 5: Upstream-Compatible KDJ Calculation

**Files:**
- Modify: `src/stock_lab/modules/market_data/indicators.py`
- Create: `tests/unit/modules/market_data/test_ths_kdj_compatibility.py`
- Modify: `tests/unit/modules/market_data/test_intraday_kdj.py`

**Interfaces:**
- Consumes: pandas DataFrame columns `trade_date`, `low`, `high`, and `close`; positive integer parameters `n`, `m1`, and `m2`.
- Produces: `calculate_ths_kdj(frame, n=9, m1=3, m2=3) -> pandas.DataFrame` with columns `trade_date`, `k`, `d`, and `j`, without changing canonical `calculate_kdj`.

- [ ] **Step 1: Add upstream golden tests**

Create tests using a ten-row DataFrame. Assert:

```python
result = calculate_ths_kdj(frame, n=9, m1=3, m2=3)

assert list(result.columns) == ["trade_date", "k", "d", "j"]
assert result.loc[0, ["k", "d", "j"]].tolist() == [50.0, 50.0, 50.0]
assert result.loc[1, "k"] == pytest.approx(33.3333333333)
assert result.loc[1, "d"] == pytest.approx(44.4444444444)
assert result.loc[1, "j"] == pytest.approx(11.1111111111)
```

Add a flat-window fixture whose RSV remains zero, a non-default `n=3, m1=2, m2=4` fixture, and parameterized invalid values `(0, 3, 3)`, `(9, 0, 3)`, and `(9, 3, 0)` raising `DataValidationError`.

Retain the existing canonical KDJ assertions unchanged to prove the two contracts remain different.

- [ ] **Step 2: Run golden tests and verify import failure**

Run:

```powershell
uv run --frozen pytest -q tests/unit/modules/market_data/test_ths_kdj_compatibility.py tests/unit/modules/market_data/test_intraday_kdj.py
```

Expected: collection FAIL because `calculate_ths_kdj` does not exist.

- [ ] **Step 3: Implement the pure compatibility algorithm**

Add a local pandas import inside the function and implement:

```python
def calculate_ths_kdj(frame, n=9, m1=3, m2=3):
    n, m1, m2 = int(n), int(m1), int(m2)
    if min(n, m1, m2) <= 0:
        raise DataValidationError("KDJ n, m1, and m2 must be positive")
    required = {"trade_date", "low", "high", "close"}
    missing = required - set(frame.columns)
    if missing:
        raise DataValidationError(
            "KDJ frame missing columns: " + ", ".join(sorted(missing))
        )
    result = frame.copy()
    lowest = result["low"].rolling(window=n).min()
    highest = result["high"].rolling(window=n).max()
    result["rsv"] = (
        (result["close"] - lowest) / (highest - lowest) * 100
    ).replace([float("inf"), float("-inf")], 0).fillna(0)
    result["k"] = 50.0
    result["d"] = 50.0
    for index in range(1, len(result)):
        result.loc[result.index[index], "k"] = (
            (1 - 1 / m1) * result.iloc[index - 1]["k"]
            + result.iloc[index]["rsv"] / m1
        )
        result.loc[result.index[index], "d"] = (
            (1 - 1 / m2) * result.iloc[index - 1]["d"]
            + result.iloc[index]["k"] / m2
        )
    result["j"] = 3 * result["k"] - 2 * result["d"]
    return result[["trade_date", "k", "d", "j"]]
```

- [ ] **Step 4: Run both KDJ formula suites**

Run:

```powershell
uv run --frozen pytest -q tests/unit/modules/market_data/test_ths_kdj_compatibility.py tests/unit/modules/market_data/test_intraday_kdj.py
```

Expected: PASS and existing canonical expected values remain unchanged.

- [ ] **Step 5: Commit the compatibility formula**

```powershell
git add -- "src/stock_lab/modules/market_data/indicators.py" "tests/unit/modules/market_data/test_ths_kdj_compatibility.py" "tests/unit/modules/market_data/test_intraday_kdj.py"
git commit -m "feat: add upstream-compatible KDJ calculation"
```

### Task 6: Restore `_3_kdj` With Canonical Persistence

**Files:**
- Modify: `src/stock_lab/jobs/kdj_indicators.py`
- Create: `task/_3_kdj.py`
- Modify: `tests/unit/jobs/test_market_data_jobs.py`
- Create: `tests/unit/compatibility/test_kdj_task.py`
- Modify: `tests/test_cutover_contracts.py`

**Interfaces:**
- Consumes: canonical `calculate_kdj`, repository trading dates/daily quotes/upsert, and compatibility `calculate_ths_kdj` from Task 5.
- Produces: `update_latest_kdj_indicators(stock_codes=None, repository=None, period=9) -> int`; task names `calculate_ths_kdj`, `save_code_kdj`, `save_daily_kdj`, and CLI.

- [ ] **Step 1: Add failing canonical latest-date tests**

Extend the fake repository with `trading_dates(limit)` and assert:

```python
count = update_latest_kdj_indicators(
    stock_codes=["000001.SZ"],
    repository=repository,
)

assert repository.requested_stock_codes == ["000001.SZ"]
assert repository.kdj_rows[0]["trade_date"] == 20260806
assert count == 1
```

Add a test that an empty trading calendar raises `DataValidationError("No trading date")`.

- [ ] **Step 2: Add failing `_3_kdj` compatibility tests**

Require:

```python
assert module.save_code_kdj("000001.SZ") == 1
assert module.save_daily_kdj(20260801, 20260807) == 2
assert calls == [
    ("latest", ["000001.SZ"]),
    ("range", 20260801, 20260807, None),
]
```

Import `calculate_ths_kdj` from `stock_lab.modules.market_data.indicators` in the test and assert `module.calculate_ths_kdj is calculate_ths_kdj`. Test explicit one-date behavior, reversed ranges, CLI `--start-date/--end-date`, repeated `--stock-code`, and import safety.

- [ ] **Step 3: Run focused tests and verify failures**

Run:

```powershell
uv run --frozen pytest -q tests/unit/jobs/test_market_data_jobs.py tests/unit/compatibility/test_kdj_task.py
```

Expected: FAIL because latest-date job and `_3_kdj.py` are absent.

- [ ] **Step 4: Implement latest-date canonical job**

Add:

```python
def update_latest_kdj_indicators(stock_codes=None, repository=None, period=9):
    repository = repository or _default_repository()
    dates = repository.trading_dates(1)
    if not dates:
        raise DataValidationError("No trading date available for KDJ update")
    trade_date = max(int(value) for value in dates)
    return update_kdj_indicators(
        trade_date,
        trade_date,
        stock_codes=stock_codes,
        repository=repository,
        period=period,
    )
```

Import `DataValidationError` and add explicit start/end validation in `update_kdj_indicators` before repository reads.

- [ ] **Step 5: Implement the thin task module**

Use private aliases for monkeypatchable delegates:

```python
from stock_lab.jobs.kdj_indicators import (
    update_kdj_indicators as _update_kdj_indicators,
    update_latest_kdj_indicators as _update_latest_kdj_indicators,
)
from stock_lab.modules.market_data.indicators import calculate_ths_kdj


def save_code_kdj(ts_code, start_date=None, end_date=None, period=9):
    if start_date is None and end_date is None:
        return _update_latest_kdj_indicators(
            stock_codes=[ts_code],
            period=period,
        )
    start_date = start_date if start_date is not None else end_date
    end_date = end_date if end_date is not None else start_date
    return _update_kdj_indicators(
        start_date,
        end_date,
        stock_codes=[ts_code],
        period=period,
    )
```

Implement `save_daily_kdj` with the same latest/range rule and `stock_codes=None`. Add `_cli(argv=None)` that accepts optional dates, repeated `--stock-code`, and `--period`; no dates means latest canonical trading date.

- [ ] **Step 6: Add wrapper cutover constraints and run tests**

Add `"task/_3_kdj.py": 120` to `WRAPPER_LIMITS`. Run:

```powershell
uv run --frozen pytest -q tests/unit/jobs/test_market_data_jobs.py tests/unit/compatibility/test_kdj_task.py tests/test_cutover_contracts.py -k "not output_directory_tracks_only_ignore_policy"
```

Expected: PASS.

- [ ] **Step 7: Commit `_3_kdj` migration**

```powershell
git add -- "src/stock_lab/jobs/kdj_indicators.py" "task/_3_kdj.py" "tests/unit/jobs/test_market_data_jobs.py" "tests/unit/compatibility/test_kdj_task.py" "tests/test_cutover_contracts.py"
git commit -m "feat: restore upstream KDJ task surface"
```

### Task 7: Add Canonical KDJ To Daily Orchestration

**Files:**
- Modify: `src/stock_lab/jobs/daily_update.py`
- Modify: `tests/unit/jobs/test_daily_update.py`
- Modify: `tests/test_emotion_pipeline_integration.py`

**Interfaces:**
- Consumes: `DailyUpdateCollector.update_kdj(trade_date) -> int` delegating to `update_kdj_indicators(trade_date, trade_date)`.
- Produces: close-of-day order index → securities/quotes → market cap/DDE → KDJ → Jiuyan/emotion, with `counts['kdj']`.

- [ ] **Step 1: Update failing orchestration expectations**

Add to each fake collector:

```python
def update_kdj(self, trade_date):
    self.calls.append(("kdj", trade_date))
    return 6
```

Shift later fake counts and require this order:

```python
[
    "trading_dates",
    ("index_daily", start_date, trade_date),
    "securities",
    ("daily_quotes", start_date, trade_date),
    ("market_cap", trade_date),
    ("dde", trade_date),
    ("kdj", trade_date),
    ("board_actions", trade_date),
    ("hot_board", trade_date, source_trade_date),
    ("index_emotion", trade_date),
]
```

Add a test where `update_kdj` raises `RuntimeError("kdj failed")`; assert the Redis lock is released and the completion key is absent.

- [ ] **Step 2: Run daily tests and verify failure**

Run:

```powershell
uv run --frozen pytest -q tests/unit/jobs/test_daily_update.py tests/test_emotion_pipeline_integration.py tests/test_daily_update_wrapper.py
```

Expected: FAIL because KDJ is absent from daily orchestration.

- [ ] **Step 3: Add lazy KDJ delegation and count**

Add:

```python
def update_kdj(self, trade_date):
    from stock_lab.jobs.kdj_indicators import update_kdj_indicators

    return update_kdj_indicators(trade_date, trade_date)
```

Call it after DDE succeeds and before `collect_board_actions`, and add:

```python
"kdj": kdj_count,
```

to `counts`. Do not catch the KDJ exception; the existing `finally` must release the lock and completion must remain unwritten.

- [ ] **Step 4: Run daily orchestration tests**

Run:

```powershell
uv run --frozen pytest -q tests/unit/jobs/test_daily_update.py tests/test_emotion_pipeline_integration.py tests/test_daily_update_wrapper.py
```

Expected: PASS.

- [ ] **Step 5: Commit daily KDJ orchestration**

```powershell
git add -- "src/stock_lab/jobs/daily_update.py" "tests/unit/jobs/test_daily_update.py" "tests/test_emotion_pipeline_integration.py"
git commit -m "feat: recalculate KDJ in daily updates"
```

### Task 8: Documentation And Full Verification

**Files:**
- Modify: `docs/historical-data-source-matrix.md`
- Modify: `docs/historical-data-backfill-runbook.md`
- Modify: `docs/database-migrations.md`
- Modify: `docs/migration.md`
- Modify: `README.md`

**Interfaces:**
- Produces: operator guidance matching canonical minute identity, bounded `_2` CLI, dual KDJ formulas, `_3_kdj` entry points, and daily KDJ ordering.

- [ ] **Step 1: Update operator documentation**

Document all of the following explicitly:

- `005_normalize_intraday_minute_identity.sql` collapses existing 12/17-digit duplicates before further five-minute collection;
- canonical five-minute times are 12-digit minutes and BaoStock values are unadjusted (`adjustflag=3`);
- `_2` requires explicit dates, accepts repeated securities, defaults to bounded concurrency 4, and returns structured failures;
- `_2.get_data` remains only for active legacy strategy consumers;
- `calculate_ths_kdj` reproduces author results but is not the canonical writer;
- `_3_kdj` save functions write canonical corrected KDJ values;
- no-date `_3_kdj` runs the latest canonical trading date;
- KDJ runs in the daily critical chain after market facts and before Jiuyan/emotion;
- five-minute facts and KDJ facts are MySQL-authoritative and have no Redis fact storage.

- [ ] **Step 2: Run import and CLI checks without provider requests**

Run:

```powershell
uv run --frozen python -c "import importlib; modules=['task._2_分时数据获取_5分k','task._3_kdj']; [importlib.import_module(name) for name in modules]; print('UPSTREAM_INTRADAY_KDJ_IMPORTS_OK')"
uv run --frozen python -m task._2_分时数据获取_5分k --help
uv run --frozen python -m task._3_kdj --help
```

Expected: all commands exit zero without BaoStock login, database connection, Redis access, or network requests.

- [ ] **Step 3: Run focused verification**

Run:

```powershell
uv run --frozen pytest -q --import-mode=importlib tests/unit/infrastructure/market_data/test_baostock.py tests/unit/jobs/test_intraday_backfill.py tests/unit/jobs/test_market_data_jobs.py tests/unit/modules/market_data/test_intraday_kdj.py tests/unit/modules/market_data/test_ths_kdj_compatibility.py tests/unit/compatibility/test_intraday_wrapper.py tests/unit/compatibility/test_kdj_task.py tests/unit/jobs/test_daily_update.py tests/test_emotion_pipeline_integration.py tests/test_daily_update_wrapper.py tests/integration/database/test_schema_migration.py
```

Expected: PASS.

- [ ] **Step 4: Run full verification**

Run:

```powershell
uv run --frozen pytest -q --import-mode=importlib
uv run --frozen pytest -q --import-mode=importlib -k "not output_directory_tracks_only_ignore_policy"
uv run --frozen python -m compileall src task tests
git diff --check
git status --short
```

Expected: the unfiltered suite has only the user-approved `output/.gitignore` failure; the filtered suite passes; compilation and diff checks pass. Fix every other failure before completion.

- [ ] **Step 5: Request independent code review**

Review the complete implementation range against:

```text
docs/superpowers/specs/2026-08-11-upstream-intraday-kdj-migration-design.md
docs/superpowers/plans/2026-08-11-upstream-intraday-kdj-migration.md
```

The reviewer must inspect minute identity migration safety, provider concurrency, partial-write behavior, formula separation, wrapper import safety, daily completion suppression, and missing tests. Fix all Critical and Important findings and rerun Step 4.

- [ ] **Step 6: Commit documentation and final consistency changes**

```powershell
git add -- "docs/historical-data-source-matrix.md" "docs/historical-data-backfill-runbook.md" "docs/database-migrations.md" "docs/migration.md" "README.md"
git commit -m "docs: document intraday and KDJ migration"
```

Do not create an empty commit when no documentation or consistency changes remain.
