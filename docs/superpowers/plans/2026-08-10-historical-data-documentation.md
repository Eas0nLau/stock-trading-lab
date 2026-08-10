# Historical Data Documentation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create two Chinese handover documents that define current-project historical-data source choices and provide a truthful, executable backfill runbook.

**Architecture:** Keep source governance separate from operations. The source matrix records semantic coverage and provider decisions; the runbook records dependency order, real CLI/API entry points, pacing, idempotency, SQL validation, and recovery procedures. Both documents cite current code and official provider documentation, cross-link to each other, and clearly separate current behavior from planned work.

**Tech Stack:** Markdown, Python 3.12, uv, FastAPI, MySQL 8, Redis, AkShare, Tushare, BaoStock, DrissionPage, PowerShell, ripgrep.

## Global Constraints

- Write both handover documents in Chinese.
- Preserve exact code spelling for commands, API names, environment variables, table names, field names, and source identifiers.
- Do not include the upstream-repository audit or its missing-task history in either final document.
- Document only commands and Python entry points that exist in the current repository.
- Label workflows as `已支持 CLI`, `仅程序接口`, `受上游限制`, or `已退役/仅迁移`.
- Treat MySQL as the historical system of record and Redis as current-day cache, indexes, and events.
- Never recommend fabricating zero or empty records after remote-source failures.
- Describe the intended AkShare fund-flow rate policy as planned until production code actually uses it.
- Do not present the current direct-EastMoney fund-flow adapter as an AkShare workflow.
- Do not execute network collectors, database migrations, or destructive schema scripts while writing the documents.

---

### Task 1: Current-Project Historical Data Source Matrix

**Files:**
- Create: `docs/historical-data-source-matrix.md`
- Reference: `docs/superpowers/specs/2026-08-10-historical-data-documentation-design.md`
- Reference: `src/stock_lab/modules/market_data/collectors.py`
- Reference: `src/stock_lab/jobs/fund_flow_backfill.py`
- Reference: `src/stock_lab/jobs/intraday_bars_5m.py`
- Reference: `src/stock_lab/jobs/kdj_indicators.py`
- Reference: `src/stock_lab/modules/market_data/jiuyan.py`
- Reference: `src/stock_lab/infrastructure/market_data/dragon_tiger.py`
- Reference: `src/stock_lab/modules/emotion/jobs.py`
- Reference: `requirements.txt`

**Interfaces:**
- Consumes: Current collector/job contracts and official AkShare documentation.
- Produces: A stable decision matrix consumed by the operator runbook through a relative Markdown link.

- [ ] **Step 1: Create the document header, decision legend, and evidence rules**

Start the file with these sections:

```markdown
# 历史数据源矩阵

本文只描述当前项目需要的历史数据及推荐来源。具体执行步骤见 [历史数据回补操作手册](historical-data-backfill-runbook.md)。

## 判定说明

| 判定 | 含义 |
| --- | --- |
| 可直接使用 | AkShare 字段语义和历史能力可满足当前表的核心事实字段 |
| 部分可用 | 可覆盖部分字段或有限历史，不能单独完成全量回补 |
| 不可使用 | AkShare 没有对应数据或没有可接受的历史能力 |
| 语义不一致 | 存在相似字段，但不能替代当前项目的原始业务定义 |

## 使用原则

- AkShare 是上游站点的 Python 适配层，不是独立数据权威。
- 历史事实写入 MySQL；Redis 只保存当日缓存、索引和事件。
- 派生指标从规范事实表重算，不从第三方下载同名结果。
- 上游失败必须保留失败状态，不写入零值或空记录。
```

- [ ] **Step 2: Add the complete source decision table**

Use these columns exactly:

```markdown
| 数据集 | 当前目标表/用途 | 当前来源与入口 | AkShare API | 判定 | 主要限制 | 推荐方案 |
```

Add one row for each of these datasets, with the specified minimum conclusion:

1. `securities`: AkShare partial; current Tushare contract remains preferred because one AkShare call does not reproduce all canonical fields.
2. `daily_quotes`: AkShare partial; `stock_zh_a_hist` supplies OHLCV but not every project field such as vendor-specific DDE and complete historical market-value semantics.
3. `index_daily`: AkShare direct; document current index collector and `stock_zh_index_daily*` choices.
4. trading dates: AkShare partial; `tool_trade_date_hist_sina` must not be the sole 2026 calendar without freshness verification.
5. `intraday_bars_5m`: AkShare limited; retain BaoStock for the current job and note AkShare minute-depth constraints.
6. current industry/concept board catalog and constituents: AkShare direct for current snapshots, not historical membership.
7. historical THS board relations: unavailable/semantic mismatch; preserve imported archival tables.
8. board fund-flow history: AkShare partial and upstream-limited; name/code drift and EastMoney response stability must be documented.
9. individual and market fund flow: AkShare partial, provider-controlled history depth.
10. `dde_net_amount`: semantic mismatch; do not replace with generic main-fund-flow fields.
11. limit-up pools: AkShare partial and recent-date limited.
12. `jiuyan_actions`: unavailable; preserve Jiuyan collector because editorial reasons and board grouping are not reproduced.
13. `dragon_tiger`, `brokers`, and `broker_listing_history`: AkShare partial/semantic mismatch; current THS collector remains authoritative for the project contract.
14. financial statements and indicators: AkShare direct for future expansion, currently outside the mandatory backfill chain unless a canonical target is added.
15. margin financing: AkShare direct but exchange-specific and date-by-date.
16. northbound flows and holdings: AkShare partial due disclosure and history limitations.
17. IPO/new-stock data: AkShare direct, with version-dependent API availability.
18. dividends/allotments: AkShare direct with unit/date normalization requirements.
19. chip distribution: AkShare partial, recent-history limited.
20. `kdj_indicators`: unavailable as a source decision; recompute locally from `daily_quotes` with project parameters.
21. `index_market_breadth`, `index_emotion_daily`, and `hot_board_emotion_daily`: derived locally; do not download substitutes.

For every AkShare row, include exact API names and note whether the project pin `akshare==1.17.54` differs materially from current `1.18.83` documentation.

- [ ] **Step 3: Add provider guidance and source-specific pacing**

Add sections for AkShare, Tushare, BaoStock, Jiuyan, THS, and EastMoney browser collection. Include these decisions:

```markdown
## 请求频率与稳定性

- AkShare：串行调用；普通批量任务至少间隔 1 秒。连接失败采用有限次数指数退避。接口实际受其上游站点约束。
- Tushare：遵守 token 权限和积分频率；当前代码遇到“频率”错误等待 65 秒后重试。
- BaoStock：按证券、日期范围串行执行，完成后注销会话；当前 5 分钟任务没有内置重试。
- 韭研公社：默认全局请求间隔为 60 至 105 秒，并可能需要人工完成滑块验证。
- 同花顺：当前龙虎榜采集器仅对连接和超时错误重试，缺少统一请求间隔，批量回补应控制日期范围。
- 东方财富浏览器采集：仅用于盘中实时链路；浏览器会话成功不代表 requests 历史接口可用。
```

- [ ] **Step 4: Add official references and current-code evidence**

Link at minimum:

- `https://akshare.akfamily.xyz/data/stock/stock.html`
- `https://akshare.akfamily.xyz/data/index/index.html`
- `https://akshare.akfamily.xyz/data/tool/tool.html`
- `https://github.com/akfamily/akshare/tree/release-v1.17.54`
- `https://github.com/akfamily/akshare/tree/release-v1.18.83`

Use relative links for current repository files. Do not link to or summarize the original upstream repository.

- [ ] **Step 5: Verify matrix scope and terminology**

Run:

```powershell
rg -n "可直接使用|部分可用|不可使用|语义不一致" docs/historical-data-source-matrix.md
rg -n "stock_sector_fund_flow_hist|stock_concept_fund_flow_hist|stock_zh_a_hist|tool_trade_date_hist_sina" docs/historical-data-source-matrix.md
rg -n "原始仓库|upstream repository|缺失的 task" docs/historical-data-source-matrix.md
```

Expected:

- All four decision labels and all required AkShare APIs are present.
- The final command returns no matches.

- [ ] **Step 6: Commit the source matrix**

```powershell
git add -- "docs/historical-data-source-matrix.md"
git commit -m "docs: add historical data source matrix"
```

### Task 2: Historical Data Backfill Operator Runbook

**Files:**
- Create: `docs/historical-data-backfill-runbook.md`
- Reference: `docs/historical-data-source-matrix.md`
- Reference: `启动项目.ps1`
- Reference: `环境安装.md`
- Reference: `task/每日更新.py`
- Reference: `task/fund_flow_backfill.py`
- Reference: `task/_5_韭研公社异动.py`
- Reference: `task/emotion_analysis.py`
- Reference: `src/stock_lab/jobs/intraday_bars_5m.py`
- Reference: `src/stock_lab/jobs/kdj_indicators.py`
- Reference: `src/stock_lab/modules/dragon_tiger/api.py`
- Reference: `docs/database-migrations.md`
- Reference: `init/stock_trading_lab_v2.sql`

**Interfaces:**
- Consumes: The source choices and limits documented by Task 1.
- Produces: The handover entry point for first deployment, current-year backfill, one-day repair, and interrupted-run recovery.

- [ ] **Step 1: Create the runbook header, status legend, and safety rules**

Start with:

```markdown
# 历史数据回补操作手册

数据源适用范围见 [历史数据源矩阵](historical-data-source-matrix.md)。本文只记录当前仓库真实存在的命令和 Python 入口。

## 状态说明

| 状态 | 含义 |
| --- | --- |
| 已支持 CLI | 可直接通过命令行执行 |
| 仅程序接口 | 代码存在，但尚无独立命令行入口 |
| 受上游限制 | 入口存在，但历史深度、验证码或接口稳定性限制实际执行 |
| 已退役/仅迁移 | 只用于旧数据导入或退役流程，不用于日常远程补数 |

## 安全规则

- MySQL 是历史事实源，Redis 仅用于当日缓存、索引和事件。
- 先备份、再迁移、再回补、最后重算派生数据。
- 不得把网络失败转换成零值或空记录。
- 不得在无完整备份和 16 组 gate 的情况下执行 `003_drop_legacy_schema.sql`。
```

- [ ] **Step 2: Document environment and service preflight**

Include exact checks for `.env`, `uv`, MySQL, Redis, dependency synchronization, imports, and API startup. Use the real application port:

```powershell
uv sync --all-groups --frozen
uv run --frozen python -c "from stock_lab.config import get_settings; from stock_lab.infrastructure.cache.redis_client import create_redis_client; print(create_redis_client(get_settings()).ping())"
uv run --frozen python app.py
```

State that `app.py` listens on `http://127.0.0.1:8527` and starts realtime workers unless `STOCK_LAB_DISABLE_WORKERS=1` is set. Recommend disabling workers during controlled historical backfills that share provider or database resources.

- [ ] **Step 3: Document database initialization and legacy migration**

Separate fresh installation from legacy migration:

- Fresh installation imports `init/stock_trading_lab_v2.sql` and does not run legacy migration scripts.
- Existing legacy databases follow `001_create_english_schema.sql`, `002_migrate_legacy_data.sql`, application cutover and validation, `004_upsert_legacy_data.sql`, then separately approved `003_drop_legacy_schema.sql`.
- Copy the backup, stop-writer, 16-gate, `004_legacy_containment_v1/succeeded`, and rollback requirements from `docs/database-migrations.md` without weakening them.

- [ ] **Step 4: Document the supported daily market-data CLI**

Include these exact commands and behavior:

```powershell
uv run --frozen python -m task.每日更新 --date 20260810
uv run --frozen python -m task.每日更新 --backfill 160
```

Document that the job updates `securities`, `daily_quotes`, `index_daily`, and `jiuyan_actions`, then writes hot-board and index-emotion derivatives. It uses the latest 160 local index dates, a six-hour Redis lock, and a seven-day completion marker. Explain that `--backfill N` means the latest N known trading dates, not an arbitrary start/end range.

- [ ] **Step 5: Document non-CLI fact-data entry points**

Include executable Python examples with real signatures:

```powershell
uv run --frozen python -c "from stock_lab.jobs.intraday_bars_5m import update_intraday_bars_5m; print(update_intraday_bars_5m(20260101, 20260810, '000001.SZ'))"
uv run --frozen python -c "from task._5_韭研公社异动 import 韭研公社异动采集; print(韭研公社异动采集(20260810))"
```

Label both as `仅程序接口`; additionally label Jiuyan as `受上游限制`. Document BaoStock's one-stock-per-call behavior, no built-in retry, Jiuyan's 60-105 second pacing, date-match validation, and slider-verification recovery.

- [ ] **Step 6: Document the dragon-tiger API workflow**

Use the current FastAPI paths and port:

```powershell
$body = @{ startDate = 20260101; latestDate = 20260810 } | ConvertTo-Json
$job = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8527/api/v1/dragon-tiger/collection-jobs" -ContentType "application/json" -Body $body
Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8527/api/v1/dragon-tiger/collection-jobs/$($job.jobId)"
```

Document that the creation response returns `jobId`, then describe the inclusive date requirement, local `daily_quotes` dependency, Redis single-job lock, THS retries, stable IDs, and stale broker-page cache risk.

- [ ] **Step 7: Document fund-flow history truthfully**

Include the current command:

```powershell
uv run --frozen python -m task.fund_flow_backfill --days 365 --rate-delay 1.0 --retries 3 --retry-delay 2.0
```

Label it `受上游限制`. State explicitly:

- current production default is `EastMoneyFundFlowSource`, not `AkShareFundFlowSource`;
- the default endpoint is currently `push2his.eastmoney.com/api/qt/stock/fflow/daykline/get`;
- the README claim that the command currently uses AkShare is stale;
- the current CLI is calendar-day based and has no `--year` option;
- the planned target is strict AkShare industry/concept history with global one-second pacing and exponential retry, but operators must not assume that change exists yet;
- MySQL targets are `fund_flow_snapshots` and `fund_flow_records`, and only current-day data is cached in Redis;
- existing snapshots are skipped and missing source dates must fail visibly.

- [ ] **Step 8: Document local derived recomputations**

Include exact Python calls:

```powershell
uv run --frozen python -c "from stock_lab.jobs.kdj_indicators import update_kdj_indicators; print(update_kdj_indicators(20260101, 20260810))"
uv run --frozen python -c "from task.emotion_analysis import 落库指数周期; print(落库指数周期(20260810))"
uv run --frozen python -c "from task.emotion_analysis import 落库热门板块情绪; print(落库热门板块情绪(20260810, 20260807))"
```

Label them `仅程序接口`. Document prerequisite tables and the rule that facts must be complete before recomputation. Explain KDJ's full-history read through `end_date`, output filtering to the requested range, default period 9, and stable upsert behavior.

- [ ] **Step 9: Add workflow-specific SQL validation templates**

Provide runnable MySQL templates for these checks:

```sql
SELECT MIN(trade_date), MAX(trade_date), COUNT(*) FROM index_daily;
SELECT MIN(trade_date), MAX(trade_date), COUNT(*) FROM daily_quotes;
SELECT trade_date, COUNT(*) FROM daily_quotes GROUP BY trade_date ORDER BY trade_date DESC LIMIT 10;
SELECT MIN(trade_time), MAX(trade_time), COUNT(*) FROM intraday_bars_5m;
SELECT MIN(trade_date), MAX(trade_date), COUNT(*) FROM kdj_indicators;
SELECT MIN(trade_date), MAX(trade_date), COUNT(*) FROM jiuyan_actions;
SELECT MIN(trade_date), MAX(trade_date), COUNT(*) FROM dragon_tiger;
SELECT MIN(trade_date), MAX(trade_date), COUNT(*) FROM fund_flow_snapshots;
SELECT MIN(s.trade_date), MAX(s.trade_date), COUNT(*)
FROM fund_flow_records r
JOIN fund_flow_snapshots s ON s.snapshot_id = r.snapshot_id;
SELECT MIN(net_inflow_100m), MAX(net_inflow_100m), COUNT(*) FROM fund_flow_records;
SELECT MIN(trade_date), MAX(trade_date), COUNT(*) FROM index_emotion_daily;
SELECT MIN(trade_date), MAX(trade_date), COUNT(*) FROM hot_board_emotion_daily;
```

Before finalizing, verify every date-column name against `init/stock_trading_lab_v2.sql` and replace any mismatch with the exact schema name. Add duplicate-key checks based on each table's primary or unique key and representative sample queries for amount units.

- [ ] **Step 10: Add four operator checklists and recovery rules**

Add sections named exactly:

- `首次部署`
- `当年历史回补`
- `单日修复`
- `中断后续跑`

For `当年历史回补`, use 2026 as the worked example but describe how to replace the year. Order the steps as index/calendar, securities/daily quotes, independent facts, Jiuyan/dragon-tiger/fund flow, KDJ/emotion, validation. Do not claim that current `--backfill` or fund-flow `--days` exactly implements a calendar year; explain the current limitation.

Recovery rules must include completion-marker behavior, Redis job locks, source-specific retries, browser verification, and the smallest safe rerun scope.

- [ ] **Step 11: Verify runbook commands and forbidden claims**

Run parser/import checks without executing remote data collection:

```powershell
uv run --frozen python -m task.每日更新 --help
uv run --frozen python -m task.fund_flow_backfill --help
uv run --frozen python -c "from stock_lab.jobs.intraday_bars_5m import update_intraday_bars_5m; from stock_lab.jobs.kdj_indicators import update_kdj_indicators; from task._5_韭研公社异动 import 韭研公社异动采集; from task.emotion_analysis import 落库指数周期, 落库热门板块情绪; print('BACKFILL_IMPORTS_OK')"
rg -n "原始仓库|upstream repository|缺失的 task" docs/historical-data-backfill-runbook.md
rg -n "当前.*AkShare|默认.*AkShare" docs/historical-data-backfill-runbook.md
```

Expected:

- Both help commands exit successfully.
- Import check prints `BACKFILL_IMPORTS_OK`.
- Original-repository references are absent.
- Any AkShare statement is explicitly marked planned rather than current production behavior.

- [ ] **Step 12: Commit the operator runbook**

```powershell
git add -- "docs/historical-data-backfill-runbook.md"
git commit -m "docs: add historical data backfill runbook"
```

### Task 3: Cross-Document Consistency And Final Verification

**Files:**
- Modify: `docs/historical-data-source-matrix.md`
- Modify: `docs/historical-data-backfill-runbook.md`

**Interfaces:**
- Consumes: Both completed handover documents.
- Produces: A consistent, reviewable documentation set with no unsupported commands or contradictory source claims.

- [ ] **Step 1: Compare every runbook workflow with the source matrix**

Confirm that each runbook source matches the matrix recommendation or is explicitly identified as current legacy behavior awaiting change. Pay particular attention to fund flow, minute bars, dragon-tiger semantics, Jiuyan, DDE, trading calendar, and derived indicators.

- [ ] **Step 2: Scan for placeholders, stale claims, and missing cross-links**

Run:

```powershell
rg -n "T[B]D|T[O]DO|PLACE[H]OLDER|待[补]充|稍后[填]写" docs/historical-data-source-matrix.md docs/historical-data-backfill-runbook.md
rg -n "historical-data-backfill-runbook.md" docs/historical-data-source-matrix.md
rg -n "historical-data-source-matrix.md" docs/historical-data-backfill-runbook.md
git diff --check
```

Expected:

- Placeholder scan returns no matches.
- Each cross-link appears once or more.
- `git diff --check` reports no whitespace errors.

- [ ] **Step 3: Verify schema names and current public interfaces**

Run targeted searches:

```powershell
rg -n "CREATE TABLE.*(securities|daily_quotes|index_daily|intraday_bars_5m|kdj_indicators|jiuyan_actions|dragon_tiger|fund_flow_snapshots|fund_flow_records|index_emotion_daily|hot_board_emotion_daily)" init/stock_trading_lab_v2.sql
rg -n "def (update_intraday_bars_5m|update_kdj_indicators|韭研公社异动采集|落库指数周期|落库热门板块情绪)" src task
rg -n "collection-jobs" src/stock_lab/modules/dragon_tiger
```

Correct the documentation if any table, date column, function signature, route, or response field differs from the source.

- [ ] **Step 4: Review the final diff and commit consistency fixes**

```powershell
git status --short
git diff -- docs/historical-data-source-matrix.md docs/historical-data-backfill-runbook.md
git add -- "docs/historical-data-source-matrix.md" "docs/historical-data-backfill-runbook.md"
git commit -m "docs: verify historical data handover guidance"
```

Do not create an empty commit if no consistency fixes are needed.
