# 指数周期与热门板块情绪数据任务实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 补齐从 Tushare、AkShare 和韭研公社采集原始数据，到指数周期及热门板块情绪分析落库的完整任务链。

**Architecture:** 新建 `task` 包，使用 `每日更新.py` 编排数据源、分析和 Redis 状态；数据源模块只负责采集和原始表 upsert，分析模块只负责从数据库读取、调用现有算法和写分析表。保留现有前端/API 契约，修复指数 API 对 `完整结果JSON` 的读取遗漏。

**Tech Stack:** Python 3.12、Tushare、AkShare、DrissionPage、mysql-connector/SQLAlchemy、Redis、pytest。

## Global Constraints

- 保持现有数据库表结构、API 响应字段和 `utils/热门板块情绪算法.py` 的评分口径。
- 热门板块数据源必须是韭研公社异动接口，不替换为东方财富板块数据。
- 交易日期使用 `akshare_sh000001` 交易日序列，热门板块 `样本来源日期` 必须是上一交易日。
- 所有原始表和分析表使用数据库主键幂等 upsert；重复运行不新增重复记录。
- 数据源失败或榜单不完整时不写伪造分析结果，不设置每日完成标记。
- 不启动或依赖通达信客户端。
- 不修改用户现有 `.gitignore`、`启动项目.ps1` 和 `front_run.py` 改动。

---

### Task 1: 数据源日期与原始行情更新

**Files:**
- Create: `task/__init__.py`
- Create: `task/data_sources.py`
- Test: `tests/test_task_data_sources.py`

**Interfaces:**
- Produces `交易日期列表(limit: int = 160) -> list[int]`。
- Produces `更新指数日线(start_date: int, end_date: int) -> int`。
- Produces `更新股票基础信息() -> int`。
- Produces `更新股票日线(start_date: int, end_date: int) -> int`。
- All functions return the number of inserted or updated rows and raise on an unavailable required data source.

- [ ] **Step 1: Write failing tests for date normalization and upsert payloads**

```python
def test_trading_dates_skip_weekends_and_return_ascending(monkeypatch):
    monkeypatch.setattr(data_sources, "_read_index_dates", lambda limit: [20260807, 20260806, 20260805])
    assert data_sources.交易日期列表(2) == [20260806, 20260807]


def test_index_payload_maps_akshare_columns():
    row = {"date": "2026-08-05", "open": 1, "close": 2, "high": 3, "low": 0,
           "volume": 4, "amount": 5, "amplitude": 6, "pct_chg": 7}
    assert data_sources.标准化指数行(row)["日期"] == 20260805
    assert data_sources.标准化指数行(row)["涨跌幅"] == 7


def test_stock_daily_upsert_key_is_date_and_code():
    payload = data_sources.股票日线记录({"ts_code": "600000.SH", "trade_date": 20260805,
                                      "open": 1, "high": 2, "low": 0.9, "close": 1.5,
                                      "pre_close": 1.4, "pct_chg": 7.14, "amount": 10})
    assert payload["ts_code"] == 600000
    assert payload["data_id"] == "600000_20260805"
```

- [ ] **Step 2: Run the focused tests and verify they fail**

Run: `uv run --frozen pytest tests/test_task_data_sources.py -q`

Expected: FAIL because `task.data_sources` and its normalization functions do not exist.

- [ ] **Step 3: Implement source adapters and database upserts**

Use `utils.common.pro` for Tushare. `更新股票基础信息` calls `stock_basic` with the existing fields and upserts `stock_basic` by replacing the current snapshot. `更新股票日线` calls `pro.daily` in date batches, joins `stock_basic` names, and writes `stock_daily` with `data_id="{symbol}_{trade_date}"`. The implementation must preserve `pre_close`, `pct_chg`, `amount`, and nullable market-value columns.

Use `akshare.stock_zh_index_daily(symbol="sh000001")` for the index and map its date/open/close/high/low/volume/amount/amplitude/pct_chg columns into `akshare_sh000001`. Normalize dates to integer `yyyyMMdd`; use `ON DUPLICATE KEY UPDATE` for every row.

Use parameterized SQL for values and batch transactions through `db.mysql_localhost` or `db.engine`. Do not log tokens or full external responses.

- [ ] **Step 4: Run the focused tests and verify they pass**

Run: `uv run --frozen pytest tests/test_task_data_sources.py -q`

Expected: PASS.

- [ ] **Step 5: Commit the isolated task**

```text
git add task tests/test_task_data_sources.py
git commit -m "补充指数和股票原始数据任务"
```

### Task 2: 韭研公社异动采集

**Files:**
- Create: `task/_5_韭研公社异动.py`
- Test: `tests/test_jiuyan_task.py`

**Interfaces:**
- Produces `解析异动响应(response: object, date: int) -> list[dict]`。
- Produces `韭研公社异动采集(date: int) -> int`。
- `解析异动响应` returns rows with `data_id`, `date`, `板块`, `板块个股数量`, `股票代码`, `股票名称`, `code`, `涨停时间`, `几天几板`, `涨幅`, and `涨停解析`.

- [ ] **Step 1: Write failing parser tests**

```python
def test_parse_jiuyan_response_filters_limit_up_range():
    response = {"data": [{"板块": "机器人", "板块个股数量": 12,
                           "股票代码": "600000", "股票名称": "示例", "涨幅": 9.8,
                           "涨停时间": "09:35:00", "几天几板": "2天2板"},
                          {"板块": "机器人", "板块个股数量": 12,
                           "股票代码": "000001", "涨幅": 8.2}]}
    rows = jiuyan.解析异动响应(response, 20260805)
    assert len(rows) == 1
    assert rows[0]["data_id"] == "20260805_机器人_600000"


def test_parse_empty_response_returns_incomplete_error():
    with pytest.raises(jiuyan.IncompleteJiuyanResponse):
        jiuyan.解析异动响应({"data": []}, 20260805)
```

- [ ] **Step 2: Run the parser tests and verify they fail**

Run: `uv run --frozen pytest tests/test_jiuyan_task.py -q`

Expected: FAIL because the parser and exception do not exist.

- [ ] **Step 3: Implement response parsing and browser collection**

Use `driver_chrome.初始化页面("jiuyan-action", url, background=True)` and start `page.listen` for `/jystock-app/api/v1/action/field`. Support JSON response bodies and the site’s JSONP/text wrapper. Validate that the response contains at least one valid board and stock row before writing.

Normalize stock codes to integers, parse percentage values as floats, preserve the source board count, and generate `data_id` from date, board name, and stock code. Write rows in one transaction with `INSERT ... ON DUPLICATE KEY UPDATE`. Retry a closed page up to three times with a fresh page; return a nonzero failure by raising `IncompleteJiuyanResponse` after the retry limit.

- [ ] **Step 4: Run parser tests and a mocked browser collection test**

Run: `uv run --frozen pytest tests/test_jiuyan_task.py -q`

Expected: PASS, with no real browser or network access required by the tests.

- [ ] **Step 5: Commit the isolated task**

```text
git add task/_5_韭研公社异动.py tests/test_jiuyan_task.py
git commit -m "补充韭研公社异动采集任务"
```

### Task 3: 指数周期与热门板块分析落库

**Files:**
- Create: `task/emotion_analysis.py`
- Modify: `实时监控/情绪周期.py:73-83`
- Test: `tests/test_emotion_analysis.py`

**Interfaces:**
- Produces `落库指数周期(date: int) -> int`。
- Produces `落库热门板块情绪(date: int, source_date: int) -> int`。
- Produces `批量上证市场宽度(date: int) -> dict` for the current trading day.

- [ ] **Step 1: Write failing mapping and dependency tests**

```python
def test_index_result_maps_all_json_columns():
    result = {"交易日期": 20260805, "周期状态": "发酵", "周期分数": 64.5,
              "指数": {"收盘": 100}, "市场宽度": {"上涨家数": 2000},
              "分项得分": {"趋势": 20}, "信号": [], "最近走势": [], "波动图": []}
    row = emotion_analysis.指数结果转数据库行(result)
    assert row["日期"] == 20260805
    assert row["完整结果JSON"]["周期状态"] == "发酵"
    assert row["市场宽度JSON"]["上涨家数"] == 2000


def test_hot_board_analysis_requires_both_board_dates(monkeypatch):
    monkeypatch.setattr(emotion_analysis, "读取板块股票池", lambda date: [] if date == 20260804 else [{"股票代码": 1}])
    with pytest.raises(emotion_analysis.MissingEmotionSource):
        emotion_analysis.落库热门板块情绪(20260805, 20260804)
```

- [ ] **Step 2: Run focused tests and verify failure**

Run: `uv run --frozen pytest tests/test_emotion_analysis.py -q`

Expected: FAIL because `task.emotion_analysis` does not exist.

- [ ] **Step 3: Implement index width and result mapping**

Read `stock_daily` with the same main-board/non-ST SQL already defined in `实时监控/情绪周期.py`. Calculate one width row for the requested date and upsert `t_指数情绪周期_市场宽度`. Call `读取上证指数日线` and `读取市场宽度数据`, then `计算指数周期结果`; map nested fields into the DDL columns and serialize JSON fields with `ensure_ascii=False`. Require the requested date to exist in both source sets before writing.

- [ ] **Step 4: Implement hot-board source loading and analysis upsert**

Load rows from `t_韭研公社异动解析` for `source_date` and `date`, group by board, deduplicate stock codes, and bulk-load `stock_daily` quotes for the current date. Call `热门板块情绪算法.生成每日分析` once per board. Map every scalar field in `实时监控/热门板块情绪.py`’s `查询分析结果` projection and serialize `判定依据` to `判定依据JSON`. Require both dates to have complete source rows; otherwise raise `MissingEmotionSource` without writing.

- [ ] **Step 5: Fix the index API projection**

Add `完整结果JSON` to the `SELECT` in `读取最新指数周期落库结果`. Add a regression test that supplies a row with this column and confirms `转换指数周期落库行` returns the stored complete result.

- [ ] **Step 6: Run focused tests**

Run: `uv run --frozen pytest tests/test_emotion_analysis.py -q`

Expected: PASS.

- [ ] **Step 7: Commit the isolated task**

```text
git add task/emotion_analysis.py 实时监控/情绪周期.py tests/test_emotion_analysis.py
git commit -m "补充指数和热门板块情绪落库"
```

### Task 4: 每日更新编排与历史回补

**Files:**
- Create: `task/每日更新.py`
- Modify: `app.py:65-68,100-101` only if the task completion contract requires it
- Test: `tests/test_daily_update.py`

**Interfaces:**
- `tasks(date: str | int) -> dict` runs one trading date and returns counts.
- `backfill(days: int = 60) -> dict` runs available trading dates oldest-first.
- `tasks` sets `每日更新.py:{date}` only after all required analysis writes succeed.

- [ ] **Step 1: Write failing orchestration tests**

```python
def test_tasks_runs_sources_before_analysis(monkeypatch):
    calls = []
    monkeypatch.setattr(daily, "更新股票基础信息", lambda: calls.append("basic") or 1)
    monkeypatch.setattr(daily, "更新股票日线", lambda start, end: calls.append("daily") or 2)
    monkeypatch.setattr(daily, "更新指数日线", lambda start, end: calls.append("index") or 1)
    monkeypatch.setattr(daily, "韭研公社异动采集", lambda date: calls.append("jiuyan") or 3)
    monkeypatch.setattr(daily, "落库热门板块情绪", lambda date, source: calls.append("hot") or 4)
    monkeypatch.setattr(daily, "落库指数周期", lambda date: calls.append("index_emotion") or 1)
    result = daily.tasks(20260805)
    assert calls == ["basic", "daily", "index", "jiuyan", "hot", "index_emotion"]
    assert result["状态"] == "success"


def test_failed_source_does_not_set_completion_key(monkeypatch):
    monkeypatch.setattr(daily, "更新股票基础信息", lambda: (_ for _ in ()).throw(RuntimeError("source down")))
    with pytest.raises(RuntimeError):
        daily.tasks(20260805)
    assert not daily.db.redis_con_localhost.exists("每日更新.py:20260805")
```

- [ ] **Step 2: Run orchestration tests and verify failure**

Run: `uv run --frozen pytest tests/test_daily_update.py -q`

Expected: FAIL because the task module and orchestration functions do not exist.

- [ ] **Step 3: Implement Redis lock and single-day orchestration**

Use `SET run_check:每日更新.py value NX EX 21600`. Resolve the previous trading date from the index date list. Skip a completed date unless an explicit force option is supplied. Call Tasks 1-3 in order. Always release the lock in `finally`; do not delete another process’s lock value. Return source and analysis row counts.

- [ ] **Step 4: Implement 60-trading-day backfill**

Get the newest available index dates, select the oldest `days` dates, and call `tasks` oldest-first. Continue only for dates whose prerequisites are available; collect failures in the return summary and leave failed dates unmarked. Do not treat missing historical Jiuyan dates as successful.

- [ ] **Step 5: Re-enable optional task import compatibility**

Ensure `from task import 每日更新, 盘前纪要` works with the existing optional import in `app.py`. Keep `盘前纪要` absent/optional; creating the new `task` package must not make the application fail when only the daily task is present. Add package exports only for modules that exist.

- [ ] **Step 6: Run orchestration tests and commit**

Run: `uv run --frozen pytest tests/test_daily_update.py -q`

Expected: PASS.

```text
git add task/每日更新.py task/__init__.py tests/test_daily_update.py app.py
git commit -m "接入每日情绪数据更新流水线"
```

### Task 5: End-to-end verification and operational entry points

**Files:**
- Modify: `task/每日更新.py`
- Create: `tests/test_emotion_pipeline_integration.py`

- [ ] **Step 1: Add fixture-backed integration test**

Use monkeypatch fixtures for Tushare, AkShare, Chrome listener and database calls. Run one complete date and assert that the expected upsert payloads exist for all three analysis tables, then run the same date again and assert the primary-key payloads are unchanged in count.

- [ ] **Step 2: Add CLI entry points**

Support:

```text
uv run --frozen python -m task.每日更新 --date 20260805
uv run --frozen python -m task.每日更新 --backfill 60
```

The CLI must return exit code 0 only when every requested date succeeds, and print the date and failed stage for each failure.

- [ ] **Step 3: Run the complete test suite and static checks**

Run:

```text
uv run --frozen pytest -q
uv run --frozen python -m py_compile task/data_sources.py task/_5_韭研公社异动.py task/emotion_analysis.py task/每日更新.py
git diff --check
```

Expected: all tests pass, compilation exits 0, and `git diff --check` reports no errors.

- [ ] **Step 4: Run a controlled real-data smoke test**

With MySQL, Redis, `.env`, and Chrome available, run one known trading date through `--date`. Query row counts and min/max dates for `stock_daily`, `akshare_sh000001`, `t_韭研公社异动解析`, `t_指数情绪周期_每日分析`, and `t_热门板块情绪_每日分析`; then request `/api/emotion/current` and `/api/hot-board-emotion/current?days=30` and assert both return `状态=success` when Jiuyan data is available.

- [ ] **Step 5: Commit verification and entry-point changes**

```text
git add task tests/test_emotion_pipeline_integration.py
git commit -m "增加情绪数据任务集成验证"
```
