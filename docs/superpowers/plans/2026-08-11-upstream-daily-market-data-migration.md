# Upstream Daily Market Data Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate upstream `_1`, `_4`, `_7`, and `_10` behavior into canonical sources, repositories, jobs, and thin task entry points for securities, daily quotes, Shanghai index history, market-value enrichment, and DDE enrichment.

**Architecture:** Provider-specific code stays in `stock_lab.infrastructure.market_data`; normalization and MySQL writes stay in `stock_lab.modules.market_data`; range orchestration stays in focused jobs. Existing English tables remain authoritative, enrichment updates never erase non-null facts with missing values, and the close-of-day job commits all market facts before Jiuyan and emotion calculations.

**Tech Stack:** Python 3.12, pandas, SQLAlchemy, Tushare, BaoStock, requests, MySQL 8, Redis locks, pytest, uv.

## Global Constraints

- Use upstream commit `8e1a3f8348bd9b10af9174b55fd94b0dca9494fb` as the business-behavior reference.
- Do not copy old Chinese SQL, import-time provider logins, `sys.path` mutation, unbounded retries, `exit()`, or Redis completion authority.
- Keep `securities`, `daily_quotes`, and `index_daily` as the only fact tables for this subproject; no schema migration is required.
- Preserve exact units: Tushare `total_mv`/`circ_mv` are ten-thousand yuan, `free_share` is ten-thousand shares, `close_price * free_share` is ten-thousand yuan, and KPL DDE is yuan.
- MySQL writes precede Redis completion state and downstream calculations.
- Missing source enrichment never overwrites an existing non-null value.
- Source and parser tests use injected clients/sessions and never access the network.
- Task modules are thin public entry points and perform no ambient I/O on import.
- The user-owned `output/.gitignore` contract failure is ignored; other failures are not ignored.
- Do not execute destructive migration `003` or live backfills while implementing this plan.

---

### Task 1: BaoStock Shanghai Index Source

**Files:**
- Modify: `src/stock_lab/infrastructure/market_data/baostock.py`
- Modify: `src/stock_lab/infrastructure/market_data/__init__.py`
- Modify: `src/stock_lab/modules/market_data/collectors.py`
- Modify: `src/stock_lab/modules/market_data/helpers.py`
- Modify: `tests/unit/infrastructure/market_data/test_baostock.py`
- Modify: `tests/test_task_data_sources.py`
- Modify: `tests/unit/modules/market_data/test_main_backfill.py`

**Interfaces:**
- Consumes: BaoStock `query_history_k_data_plus('sh.000001', BAOSTOCK_INDEX_FIELDS, start_date=request_start, end_date=request_end, frequency='d', adjustflag='3')`, where both request dates are ISO `YYYY-MM-DD` strings.
- Produces: `BaoStockSource.fetch_index_daily(start_date, end_date) -> list[dict[str, object]]` and a date-aware `MarketDataCollector.index_source(start_date, end_date)` callable.

- [ ] **Step 1: Add failing BaoStock index contract tests**

Add tests with an injected fake client that returns a 20-calendar-day buffer plus the requested rows:

```python
def test_baostock_index_source_uses_buffer_and_computes_previous_close_fields():
    client = FakeBaoStockClient(index_rows=[
        ["2026-08-06", "sh.000001", "10", "11", "12", "9", "1000", "2000", "3", "1.2", "10"],
        ["2026-08-07", "sh.000001", "11", "12", "13", "10", "1200", "2500", "3", "1.3", "9.09"],
    ])

    rows = BaoStockSource(client).fetch_index_daily(20260807, 20260807)

    assert client.index_request["code"] == "sh.000001"
    assert client.index_request["start_date"] == "2026-07-18"
    assert rows == [{
        "date": "2026-08-07",
        "open": 11.0,
        "close": 12.0,
        "high": 13.0,
        "low": 10.0,
        "volume": 12.0,
        "amount": 2500.0,
        "amplitude": (13.0 - 10.0) / 11.0 * 100,
        "pct_chg": 9.09,
        "change": 1.0,
        "turnover": 1.3,
    }]
```

Also assert login/logout occur once, malformed rows fail explicitly, empty responses return an empty list, and provider errors raise `InfrastructureError` without recursion.

- [ ] **Step 2: Run the focused source tests and verify failure**

Run:

```powershell
uv run --frozen pytest -q tests/unit/infrastructure/market_data/test_baostock.py
```

Expected: FAIL because `fetch_index_daily` does not exist.

- [ ] **Step 3: Implement the daily index source**

Add:

```python
BAOSTOCK_INDEX_FIELDS = "date,code,open,close,high,low,volume,amount,adjustflag,turn,pctChg"

class BaoStockSource:
    def fetch_index_daily(self, start_date, end_date):
        requested_start = dt.datetime.strptime(str(start_date), "%Y%m%d").date()
        requested_end = dt.datetime.strptime(str(end_date), "%Y%m%d").date()
        request_start = requested_start - dt.timedelta(days=20)
        rows = self._query_rows(
            "sh.000001",
            BAOSTOCK_INDEX_FIELDS,
            start_date=request_start.strftime("%Y-%m-%d"),
            end_date=requested_end.strftime("%Y-%m-%d"),
            frequency="d",
            adjustflag="3",
        )
        normalized = []
        previous_close = None
        for row in rows:
            trade_date = dt.datetime.strptime(row["date"], "%Y-%m-%d").date()
            close = float(row["close"])
            if previous_close not in (None, 0) and requested_start <= trade_date <= requested_end:
                normalized.append({
                    "date": row["date"],
                    "open": float(row["open"]),
                    "close": close,
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "volume": float(row["volume"]) / 100,
                    "amount": float(row["amount"]),
                    "amplitude": (float(row["high"]) - float(row["low"])) / previous_close * 100,
                    "pct_chg": float(row["pctChg"]),
                    "change": close - previous_close,
                    "turnover": float(row["turn"]),
                })
            previous_close = close
        return normalized
```

Add `_query_rows(code, fields, *, start_date, end_date, frequency, adjustflag) -> list[dict]` for the login/query/logout lifecycle shared by daily-index and five-minute requests. Preserve the current `fetch_5m_bars` behavior and error types.

Update `index_daily_from_source()` to accept BaoStock aliases `pctChg` and `turn`. Change the default collector to inject `BaoStockSource().fetch_index_daily`, and call `index_source(start_date, end_date)` from `update_index_daily`.

- [ ] **Step 4: Update collector tests for the date-aware index callable**

Replace `index_source=lambda: index_frame` fixtures with:

```python
index_source=lambda start_date, end_date: requested_ranges.append(
    (start_date, end_date)
) or index_frame
```

Assert the range is forwarded and normalized rows are upserted into `index_daily`.

- [ ] **Step 5: Run focused market-data tests**

Run:

```powershell
uv run --frozen pytest -q tests/unit/infrastructure/market_data/test_baostock.py tests/unit/modules/market_data/test_main_backfill.py tests/test_task_data_sources.py
```

Expected: PASS.

- [ ] **Step 6: Commit the index source migration**

```powershell
git add -- "src/stock_lab/infrastructure/market_data/baostock.py" "src/stock_lab/infrastructure/market_data/__init__.py" "src/stock_lab/modules/market_data/collectors.py" "src/stock_lab/modules/market_data/helpers.py" "tests/unit/infrastructure/market_data/test_baostock.py" "tests/unit/modules/market_data/test_main_backfill.py" "tests/test_task_data_sources.py"
git commit -m "feat: migrate Shanghai index collection to BaoStock"
```

### Task 2: Tushare Token Rotation And Daily-Basic Source

**Files:**
- Modify: `src/stock_lab/infrastructure/market_data/tushare.py`
- Modify: `tests/unit/infrastructure/market_data/test_official_sources.py`

**Interfaces:**
- Consumes: `TUSHARE_TOKENS` and Tushare `stock_basic`, `daily`, and `daily_basic` APIs.
- Produces: `TushareSource.fetch_daily_basic(trade_date)` and bounded token rotation for every request.

- [ ] **Step 1: Add failing token-rotation and daily-basic tests**

Add:

```python
def test_tushare_rotates_tokens_and_exhausts_once_per_token():
    calls = []
    clients = {
        "bad": Client(daily_error=RuntimeError("频率限制")),
        "good": Client(daily_result="quotes"),
    }
    source = TushareSource(
        ("bad", "good"),
        client_factory=lambda token: calls.append(token) or clients[token],
    )

    assert source.fetch_daily_quotes(20260807) == "quotes"
    assert calls == ["bad", "good"]

def test_tushare_daily_basic_uses_required_fields():
    result = source.fetch_daily_basic(20260807)
    assert client.daily_basic_call == {
        "trade_date": "20260807",
        "fields": "ts_code,trade_date,total_mv,circ_mv,free_share",
    }
```

Assert all-token failure raises `InfrastructureError` containing the method and final error, with no infinite loop.

- [ ] **Step 2: Run the official-source tests and verify failure**

Run:

```powershell
uv run --frozen pytest -q tests/unit/infrastructure/market_data/test_official_sources.py
```

Expected: FAIL because `client_factory` and `fetch_daily_basic` do not exist.

- [ ] **Step 3: Implement lazy bounded token rotation**

Use this public shape:

```python
class TushareSource:
    def __init__(self, tokens, client_factory=None):
        self.tokens = tuple(tokens)
        self._client_factory = client_factory
        self._clients = {}

    def _client(self, token):
        if token not in self._clients:
            if self._client_factory is None:
                import tushare
                factory = tushare.pro_api
            else:
                factory = self._client_factory
            self._clients[token] = factory(token)
        return self._clients[token]

    def _call(self, method_name, **kwargs):
        errors = []
        for token in self.tokens:
            try:
                return getattr(self._client(token), method_name)(**kwargs)
            except Exception as error:
                errors.append(error)
        if not self.tokens:
            raise InfrastructureError("Tushare token is required for stock collection")
        raise InfrastructureError(
            f"Tushare {method_name} failed for all {len(self.tokens)} tokens: {errors[-1]}"
        ) from errors[-1]

    def fetch_daily_quotes(self, trade_date):
        return self._call("daily", ts_code="", trade_date=str(trade_date))

    def fetch_daily_basic(self, trade_date):
        return self._call(
            "daily_basic",
            trade_date=str(trade_date),
            fields="ts_code,trade_date,total_mv,circ_mv,free_share",
        )
```

Keep `fetch_securities()` using `_call("stock_basic", exchange="", list_status="L", fields="ts_code,symbol,name,area,industry,market,list_date,list_status")`.

Clients remain lazy and cached by token. Do not sleep inside the adapter; collector/job pacing owns delays.

- [ ] **Step 4: Run source tests**

Run:

```powershell
uv run --frozen pytest -q tests/unit/infrastructure/market_data/test_official_sources.py
```

Expected: PASS.

- [ ] **Step 5: Commit the Tushare source contract**

```powershell
git add -- "src/stock_lab/infrastructure/market_data/tushare.py" "tests/unit/infrastructure/market_data/test_official_sources.py"
git commit -m "feat: add bounded Tushare daily-basic source"
```

### Task 3: Null-Preserving Daily-Quote Enrichment Repository

**Files:**
- Modify: `src/stock_lab/modules/market_data/repository.py`
- Modify: `src/stock_lab/modules/market_data/helpers.py`
- Modify: `tests/unit/modules/market_data/test_market_data_repository.py`
- Create: `tests/unit/modules/market_data/test_market_data_enrichment.py`

**Interfaces:**
- Consumes: normalized rows containing `ts_code`, `trade_date`, and allowed enrichment fields.
- Produces: `MarketDataRepository.update_daily_quote_enrichment(rows, fields, only_missing=False) -> int`, `market_cap_from_source(row, close_price)`, and `dde_from_source(row)`.

- [ ] **Step 1: Add failing normalization tests**

Add:

```python
def test_market_cap_normalization_preserves_tushare_units():
    row = market_cap_from_source({
        "ts_code": "000001.SZ",
        "trade_date": "20260807",
        "total_mv": "10000",
        "circ_mv": "8000",
        "free_share": "500",
    }, close_price=12.5)
    assert row == {
        "ts_code": "000001.SZ",
        "trade_date": 20260807,
        "total_market_value": 10000.0,
        "circulating_market_value": 8000.0,
        "free_float_shares": 500.0,
        "free_float_market_value": 6250.0,
    }

def test_dde_normalization_keeps_yuan():
    assert dde_from_source({
        "stock_code": "1", "trade_date": "2026-08-07", "dde": "325000000"
    }) == {
        "ts_code": "000001.SZ", "trade_date": 20260807, "dde_net_amount": 325000000.0
    }
```

- [ ] **Step 2: Add failing SQL contract tests**

Use a fake SQLAlchemy engine/connection and assert:

```python
repository.update_daily_quote_enrichment(
    rows,
    fields=("total_market_value", "circulating_market_value"),
    only_missing=False,
)
```

generates `COALESCE(:total_market_value, total_market_value)` so a null source cannot erase a fact. With `only_missing=True`, assert the SQL only replaces a target column when it is null. Reject fields outside:

```python
{
    "total_market_value",
    "circulating_market_value",
    "free_float_shares",
    "free_float_market_value",
    "dde_net_amount",
}
```

- [ ] **Step 3: Run enrichment tests and verify failure**

Run:

```powershell
uv run --frozen pytest -q tests/unit/modules/market_data/test_market_data_enrichment.py tests/unit/modules/market_data/test_market_data_repository.py
```

Expected: FAIL because the normalizers and enrichment method do not exist.

- [ ] **Step 4: Implement normalization and enrichment updates**

Implement one parameterized `UPDATE daily_quotes` executemany transaction keyed by normalized `(ts_code, trade_date)`. Do not insert rows when the base daily quote is absent. Return the affected row count reported by the connection result.

- [ ] **Step 5: Run repository and normalization tests**

Run:

```powershell
uv run --frozen pytest -q tests/unit/modules/market_data/test_market_data_enrichment.py tests/unit/modules/market_data/test_market_data_repository.py
```

Expected: PASS.

- [ ] **Step 6: Commit the enrichment boundary**

```powershell
git add -- "src/stock_lab/modules/market_data/repository.py" "src/stock_lab/modules/market_data/helpers.py" "tests/unit/modules/market_data/test_market_data_repository.py" "tests/unit/modules/market_data/test_market_data_enrichment.py"
git commit -m "feat: add null-preserving quote enrichment"
```

### Task 4: Market-Value Backfill Job And Upstream Entry Point

**Files:**
- Create: `src/stock_lab/jobs/market_cap_backfill.py`
- Create: `task/_7_市值信息每日更新.py`
- Create: `tests/unit/jobs/test_market_cap_backfill.py`
- Create: `tests/unit/compatibility/test_market_cap_task.py`

**Interfaces:**
- Consumes: `TushareSource.fetch_daily_basic(trade_date)`, repository trading dates/base quotes, and `update_daily_quote_enrichment`.
- Produces: `update_market_cap(start_date, end_date, *, source=None, repository=None, force=False, rate_delay=0.2, sleep=time.sleep) -> dict` and thin task aliases `更新`, `主函数`, `update`, `main`.

- [ ] **Step 1: Add failing market-cap job tests**

Cover descending trading dates, source fields, quote intersection, free-float calculation, pacing, force behavior, empty dates, and no Redis writes:

```python
def test_market_cap_backfill_updates_existing_quotes_newest_first():
    result = update_market_cap(
        20260806,
        20260807,
        source=FakeDailyBasicSource(),
        repository=FakeRepository(),
        rate_delay=0.2,
        sleep=sleeps.append,
    )
    assert source.calls == [20260807, 20260806]
    assert repository.fields == (
        "total_market_value",
        "circulating_market_value",
        "free_float_shares",
        "free_float_market_value",
    )
    assert result["failed_dates"] == []
```

An empty source response must record the date as failed and must not update MySQL. `force=False` uses null-preserving updates; `force=True` allows valid non-null values to replace existing values but still preserves them when the source value is null.

- [ ] **Step 2: Run the job test and verify failure**

Run:

```powershell
uv run --frozen pytest -q tests/unit/jobs/test_market_cap_backfill.py
```

Expected: FAIL because the module does not exist.

- [ ] **Step 3: Implement the market-cap job**

Return this stable result contract:

```python
{
    "status": "success" | "failed",
    "updated": int,
    "processed_dates": list[int],
    "failed_dates": list[int],
    "errors": list[dict],
}
```

Use MySQL `index_daily` dates rather than Redis markers. Read existing base quotes for each date to obtain closes and valid symbols before applying enrichment.

- [ ] **Step 4: Add the thin upstream-named task module**

`task/_7_市值信息每日更新.py` must contain argument parsing and aliases only:

```python
def 更新(start_date=None, end_date=None, only_missing=True):
    return update_market_cap(start_date, end_date, force=not only_missing)

def 主函数(start_date=None, end_date=None, force=False):
    return update_market_cap(start_date, end_date, force=force)

update = 更新
main = 主函数
```

Add `--start-date`, `--end-date`, and `--force`. Importing the module must not load Tushare, MySQL, or Redis.

- [ ] **Step 5: Run job and compatibility tests**

Run:

```powershell
uv run --frozen pytest -q tests/unit/jobs/test_market_cap_backfill.py tests/unit/compatibility/test_market_cap_task.py
```

Expected: PASS.

- [ ] **Step 6: Commit market-cap backfill**

```powershell
git add -- "src/stock_lab/jobs/market_cap_backfill.py" "task/_7_市值信息每日更新.py" "tests/unit/jobs/test_market_cap_backfill.py" "tests/unit/compatibility/test_market_cap_task.py"
git commit -m "feat: migrate daily market-cap enrichment"
```

### Task 5: Thread-Safe Request Pacing And KPL DDE Source

**Files:**
- Create: `src/stock_lab/shared/rate_limit.py`
- Create: `src/stock_lab/infrastructure/market_data/kpl.py`
- Modify: `src/stock_lab/infrastructure/market_data/__init__.py`
- Create: `tests/unit/shared/test_rate_limit.py`
- Create: `tests/unit/infrastructure/market_data/test_kpl_source.py`

**Interfaces:**
- Produces: `RequestRateLimiter(min_interval_seconds, monotonic=time.monotonic, sleep=time.sleep).wait()` and `KplDdeSource.fetch_daily_dde(stock_code, *, count=100, start_date=None, end_date=None, timeout=20, retries=3) -> list[dict]`.

- [ ] **Step 1: Add failing global pacing tests**

Use a fake clock and two threads to prove `wait()` serializes slots and advances at least the configured interval. Assert `min_interval_seconds=0` does not sleep.

- [ ] **Step 2: Add failing KPL request and parsing tests**

Cover:

- six-digit normalization for integer, Tushare, and prefixed codes;
- `GetDaDanKLine2New` request fields and per-instance device ID;
- page sizes up to 600 and pagination until the start date;
- duplicate dates keeping the first result;
- numeric DDE in yuan;
- malformed dates/values skipped;
- HTTP, JSON, and nonzero `errcode` retries with `0.5 * attempt` delay;
- exhausted retry raising `InfrastructureError`;
- the shared limiter called before every POST.

Use an injected session returning fixed JSON such as:

```python
{"errcode": "0", "Date": ["20260807", "20260806"], "DDJE": ["325000000", "-50000000"]}
```

- [ ] **Step 3: Run pacing/source tests and verify failure**

Run:

```powershell
uv run --frozen pytest -q tests/unit/shared/test_rate_limit.py tests/unit/infrastructure/market_data/test_kpl_source.py
```

Expected: FAIL because the modules do not exist.

- [ ] **Step 4: Implement the limiter and KPL adapter**

Use constructor injection:

```python
class KplDdeSource:
    def __init__(self, session=None, limiter=None, sleep=time.sleep, device_id=None):
        self.session = session or requests.Session()
        self.session.headers.update(KPL_HEADERS)
        self.limiter = limiter or RequestRateLimiter(0.5)
        self.sleep = sleep
        self.device_id = device_id or str(uuid.uuid4())
```

Default to `RequestRateLimiter(0.5)`. Create the UUID when the source instance is constructed, not at module import. Return plain dictionaries with `stock_code`, `trade_date`, and `dde`; do not import pandas or database code.

- [ ] **Step 5: Run pacing/source tests**

Run:

```powershell
uv run --frozen pytest -q tests/unit/shared/test_rate_limit.py tests/unit/infrastructure/market_data/test_kpl_source.py
```

Expected: PASS.

- [ ] **Step 6: Commit the KPL source**

```powershell
git add -- "src/stock_lab/shared/rate_limit.py" "src/stock_lab/infrastructure/market_data/kpl.py" "src/stock_lab/infrastructure/market_data/__init__.py" "tests/unit/shared/test_rate_limit.py" "tests/unit/infrastructure/market_data/test_kpl_source.py"
git commit -m "feat: add rate-limited KPL DDE source"
```

### Task 6: DDE Backfill Job And Upstream Entry Point

**Files:**
- Create: `src/stock_lab/jobs/dde_backfill.py`
- Create: `task/_10_开盘啦dde读取.py`
- Create: `tests/unit/jobs/test_dde_backfill.py`
- Create: `tests/unit/compatibility/test_dde_task.py`

**Interfaces:**
- Consumes: `KplDdeSource`, `MarketDataRepository.daily_quotes`, and `update_daily_quote_enrichment`.
- Produces: `update_dde(start_date, end_date, *, source=None, repository=None, force=False, max_workers=4, timeout=20, retries=3) -> dict`, plus upstream names `读取历史日K_DDE`, `更新`, `主函数`, `fetch_daily_dde`, `update`, and `main`.

- [ ] **Step 1: Add failing DDE orchestration tests**

Add tests asserting:

```python
def test_dde_backfill_fetches_each_pending_symbol_and_updates_only_dde():
    result = update_dde(
        20260806,
        20260807,
        source=FakeDdeSource(),
        repository=FakeRepository(),
        max_workers=2,
    )
    assert set(source.calls) == {
        ("000001.SZ", 20260806, 20260807),
        ("600000.SH", 20260806, 20260807),
    }
    assert repository.fields == ("dde_net_amount",)
    assert result == {
        "status": "success",
        "updated": 4,
        "processed_codes": ["000001.SZ", "600000.SH"],
        "empty_codes": [],
        "failed": [],
    }
```

Also cover partial failure returning `status='failed'`, keeping successful MySQL writes, deterministic sorted results despite concurrency, `force=False` only filling null values, and no Redis operations.

- [ ] **Step 2: Run the DDE job test and verify failure**

Run:

```powershell
uv run --frozen pytest -q tests/unit/jobs/test_dde_backfill.py
```

Expected: FAIL because the job does not exist.

- [ ] **Step 3: Implement bounded concurrent DDE orchestration**

Query distinct pending symbols from canonical `daily_quotes` for the range. Keep `max_workers` configurable and default it to 4. The source-level limiter globally paces all worker requests. Write one completed symbol at a time or in bounded batches so a long backfill does not retain all frames in memory.

Do not hide failures. Return each failed code and error text in `failed`; the later `task_runs` subproject will persist this result. The close-of-day integration must reject a failed result and avoid its Redis completion marker.

- [ ] **Step 4: Add the thin upstream-named DDE task module**

Expose:

```python
def 读取历史日K_DDE(stock_code, count=100, start_date=None, end_date=None, timeout=20, retries=3):
    rows = KplDdeSource().fetch_daily_dde(
        stock_code,
        count=count,
        start_date=start_date,
        end_date=end_date,
        timeout=timeout,
        retries=retries,
    )
    return pd.DataFrame(rows, columns=["stock_code", "trade_date", "dde"])

def 更新(start_date=None, end_date=None, only_missing=True, max_workers=4, timeout=20, retries=3):
    return update_dde(
        start_date,
        end_date,
        force=not only_missing,
        max_workers=max_workers,
        timeout=timeout,
        retries=retries,
    )

def 主函数(start_date=None, end_date=None, force=False, max_workers=4, timeout=20, retries=3):
    return update_dde(
        start_date,
        end_date,
        force=force,
        max_workers=max_workers,
        timeout=timeout,
        retries=retries,
    )
```

The single-stock function delegates to `KplDdeSource` and performs only the upstream-compatible DataFrame projection with columns `stock_code`, `trade_date`, and `dde`; update functions delegate to `update_dde`. Do not expose the old direct-SQL helpers or intraday DDE until a canonical intraday target is designed. The compatibility test must assert the DataFrame columns and row values.

Add a CLI with `--start-date`, `--end-date`, `--force`, `--max-workers` (default 4), `--timeout` (default 20), and `--retries` (default 3). Exit nonzero when the result status is `failed` and print the structured result so failed symbols can be resumed.

- [ ] **Step 5: Run DDE and compatibility tests**

Run:

```powershell
uv run --frozen pytest -q tests/unit/jobs/test_dde_backfill.py tests/unit/compatibility/test_dde_task.py
```

Expected: PASS.

- [ ] **Step 6: Commit DDE backfill**

```powershell
git add -- "src/stock_lab/jobs/dde_backfill.py" "task/_10_开盘啦dde读取.py" "tests/unit/jobs/test_dde_backfill.py" "tests/unit/compatibility/test_dde_task.py"
git commit -m "feat: migrate KPL DDE enrichment"
```

### Task 7: Upstream Daily And Index Task Entry Points

**Files:**
- Create: `task/_1_日k数据更新.py`
- Create: `task/_4_上证指数日k.py`
- Delete: `task/data_sources.py`
- Modify: `tests/test_task_data_sources.py`
- Modify: `tests/test_cutover_contracts.py`
- Create: `tests/unit/compatibility/test_upstream_market_tasks.py`

**Interfaces:**
- Produces: upstream-compatible `task._1_日k数据更新.main(start_date, end_date, force=False)` and `task._4_上证指数日k.update(start_date, end_date)` thin entry points.

- [ ] **Step 1: Add failing thin-wrapper tests**

Test imports have no provider, MySQL, or Redis side effects. Inject canonical functions and assert forwarding:

```python
def test_upstream_daily_task_forwards_exact_range(monkeypatch):
    calls = []
    monkeypatch.setattr(module, "update_securities", lambda: calls.append("securities") or 1)
    monkeypatch.setattr(
        module,
        "update_daily_quotes",
        lambda start, end, force=False: calls.append((start, end, force)) or 2,
    )
    assert module.main(20260801, 20260807, force=True) == {
        "securities": 1, "daily_quotes": 2
    }
    assert calls == ["securities", (20260801, 20260807, True)]
```

Assert `_4.update()` delegates to canonical `update_index_daily`.

- [ ] **Step 2: Run compatibility tests and verify failure**

Run:

```powershell
uv run --frozen pytest -q tests/unit/compatibility/test_upstream_market_tasks.py
```

Expected: FAIL because the upstream-named modules do not exist.

- [ ] **Step 3: Implement the thin modules and force-capable quote update**

Add `force=False` to `MarketDataCollector.update_daily_quotes` and public `update_daily_quotes`. With `force=True`, request every trading date in range and upsert it; with `force=False`, preserve current gap-only behavior.

Add CLI arguments `--start-date`, `--end-date`, and `--force` to `_1`; add `--start-date` and `--end-date` to `_4`. Fix the upstream broken one-argument script behavior by requiring both range endpoints.

- [ ] **Step 4: Remove the invented compatibility module**

Delete `task/data_sources.py`. Move normalization assertions to canonical helper/collector tests and change any remaining test imports to `stock_lab.modules.market_data.collectors`. Remove the obsolete `task/data_sources.py` size entry from `tests/test_cutover_contracts.py`.

- [ ] **Step 5: Run compatibility and market-data tests**

Run:

```powershell
uv run --frozen pytest -q tests/unit/compatibility/test_upstream_market_tasks.py tests/test_task_data_sources.py tests/test_cutover_contracts.py tests/unit/modules/market_data
```

Expected: PASS except the explicitly ignored `output/.gitignore` contract assertion when it is selected by the cutover file.

- [ ] **Step 6: Commit task entry-point migration**

```powershell
git add -- "task/_1_日k数据更新.py" "task/_4_上证指数日k.py" "tests/test_task_data_sources.py" "tests/test_cutover_contracts.py" "tests/unit/compatibility/test_upstream_market_tasks.py" "src/stock_lab/modules/market_data/collectors.py"
git add -u -- "task/data_sources.py"
git commit -m "refactor: replace invented market task wrappers"
```

### Task 8: Close-Of-Day Market Fact Ordering

**Files:**
- Modify: `src/stock_lab/jobs/daily_update.py`
- Modify: `tests/unit/jobs/test_daily_update.py`
- Modify: `tests/test_emotion_pipeline_integration.py`

**Interfaces:**
- Consumes: `update_index_daily`, `update_securities`, `update_daily_quotes`, `update_market_cap`, and `update_dde`.
- Produces: fact-first daily-update ordering with market-cap and DDE counts included in the result.

- [ ] **Step 1: Update the failing orchestration expectation**

Extend `FakeCollector` with:

```python
def update_market_cap(self, trade_date):
    self.calls.append(("market_cap", trade_date))
    return {"status": "success", "updated": 4, "failed_dates": []}

def update_dde(self, trade_date):
    self.calls.append(("dde", trade_date))
    return {"status": "success", "updated": 5, "failed": []}
```

Require this order:

```python
[
    "trading_dates",
    ("index_daily", start_date, trade_date),
    "securities",
    ("daily_quotes", start_date, trade_date),
    ("market_cap", trade_date),
    ("dde", trade_date),
    ("board_actions", trade_date),
    ("hot_board", trade_date, source_trade_date),
    ("index_emotion", trade_date),
]
```

Add tests that either market-cap or DDE result with `status='failed'` raises `JobExecutionError`, releases the Redis lock, and does not write the completion key.

- [ ] **Step 2: Run daily-update tests and verify failure**

Run:

```powershell
uv run --frozen pytest -q tests/unit/jobs/test_daily_update.py tests/test_emotion_pipeline_integration.py
```

Expected: FAIL because market-cap/DDE stages and ordering are absent.

- [ ] **Step 3: Implement fact-first orchestration**

Add lazy `DailyUpdateCollector.update_market_cap(trade_date)` and `update_dde(trade_date)` methods. Execute index before securities/quotes, then enrichment, then Jiuyan and emotion. Validate each enrichment result status and copy its `updated` integer into:

```python
"market_cap": int,
"dde": int,
```

in `counts`. Keep the existing token-protected Redis lock and completion TTL until the later `task_runs` subproject replaces completion authority.

- [ ] **Step 4: Run orchestration tests**

Run:

```powershell
uv run --frozen pytest -q tests/unit/jobs/test_daily_update.py tests/test_emotion_pipeline_integration.py tests/test_daily_update_wrapper.py
```

Expected: PASS.

- [ ] **Step 5: Commit daily ordering**

```powershell
git add -- "src/stock_lab/jobs/daily_update.py" "tests/unit/jobs/test_daily_update.py" "tests/test_emotion_pipeline_integration.py"
git commit -m "feat: run daily market facts before analysis"
```

### Task 9: Documentation And Full Verification

**Files:**
- Modify: `docs/historical-data-source-matrix.md`
- Modify: `docs/historical-data-backfill-runbook.md`
- Modify: `docs/migration.md`

**Interfaces:**
- Produces: operator guidance matching the migrated provider and task behavior.

- [ ] **Step 1: Update source and operator documentation**

Document:

- BaoStock is now the canonical Shanghai-index source;
- `_1`, `_4`, `_7`, and `_10` are thin runnable entry points;
- exact force/range behavior;
- Tushare token rotation and daily-basic units;
- DDE endpoint, yuan units, 0.5-second global request interval, bounded concurrency, and partial-failure output;
- market-cap/DDE facts live in `daily_quotes` and never in Redis;
- `task/data_sources.py` has been removed.

- [ ] **Step 2: Run import and CLI checks without live requests**

Run:

```powershell
uv run --frozen python -c "import importlib; modules=['task._1_日k数据更新','task._4_上证指数日k','task._7_市值信息每日更新','task._10_开盘啦dde读取']; [importlib.import_module(name) for name in modules]; print('UPSTREAM_MARKET_TASK_IMPORTS_OK')"
uv run --frozen python -m task._1_日k数据更新 --help
uv run --frozen python -m task._4_上证指数日k --help
uv run --frozen python -m task._7_市值信息每日更新 --help
uv run --frozen python -m task._10_开盘啦dde读取 --help
```

Expected: all commands exit zero and no provider login or network request occurs.

- [ ] **Step 3: Run focused verification**

Run:

```powershell
uv run --frozen pytest -q --import-mode=importlib tests/unit/infrastructure/market_data tests/unit/modules/market_data tests/unit/jobs/test_market_cap_backfill.py tests/unit/jobs/test_dde_backfill.py tests/unit/jobs/test_daily_update.py tests/unit/compatibility/test_market_cap_task.py tests/unit/compatibility/test_dde_task.py tests/unit/compatibility/test_upstream_market_tasks.py tests/test_emotion_pipeline_integration.py tests/test_daily_update_wrapper.py
```

Expected: PASS.

- [ ] **Step 4: Run the full suite and static checks**

Run:

```powershell
uv run --frozen pytest -q --import-mode=importlib
uv run --frozen python -m compileall src task tests
git diff --check
git status --short
```

Expected: all tests pass except the user-owned `output/.gitignore` contract assertion; compilation and diff checks pass. Any other failure must be fixed before completion.

- [ ] **Step 5: Commit documentation and final consistency fixes**

```powershell
git add -- "docs/historical-data-source-matrix.md" "docs/historical-data-backfill-runbook.md" "docs/migration.md"
git commit -m "docs: document upstream daily market tasks"
```

Do not create an empty commit when no documentation or consistency changes remain.
