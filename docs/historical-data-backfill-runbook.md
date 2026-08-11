# 历史数据回补操作手册

数据源适用范围见[历史数据源矩阵](historical-data-source-matrix.md)。本文只记录当前仓库真实存在的命令和 Python 入口，并明确哪些功能目前受上游或入口限制。

## 状态说明

| 状态 | 含义 |
| --- | --- |
| 已支持 CLI | 可直接通过命令行执行 |
| 仅程序接口 | 代码存在，但尚无独立命令行入口 |
| 受上游限制 | 入口存在，但历史深度、验证码或接口稳定性限制实际执行 |
| 已退役/仅迁移 | 只用于旧数据导入或退役流程，不用于日常远程补数 |

## 安全规则

- MySQL 是历史事实的系统记录；Redis 只保存当日缓存、日期索引和事件。
- 先备份、再迁移、再回补、最后重算派生数据。
- 远程请求失败必须记录失败日期和实体，不得写入零值、空记录或伪造交易日。
- 任务应支持重复运行。已存在的规范记录按 repository 的跳过或 upsert 规则处理，不要清空整张表重跑。
- 不得在无完整备份、16 组 gate 和人工抽样的情况下执行 `003_drop_legacy_schema.sql`。
- 历史回补期间要避免和盘中实时 worker 争用同一上游或数据库资源，可设置 `STOCK_LAB_DISABLE_WORKERS=1` 后单独启动 Web 服务。

## 一、执行前检查

### 1. 环境和服务

确认项目根目录存在 `.env`，并且 `uv`、MySQL 8、Redis 已安装并运行。项目启动脚本还会检查 npm 和前端依赖。

```powershell
Test-Path -LiteralPath ".env"
uv sync --all-groups --frozen
```

检查 Redis 和配置加载，不执行远程采集：

```powershell
uv run --frozen python -c "from stock_lab.config import get_settings; from stock_lab.infrastructure.cache.redis_client import create_redis_client; client=create_redis_client(get_settings()); print(client.ping())"
```

启动应用：

```powershell
$env:STOCK_LAB_DISABLE_WORKERS = "1"
uv run --frozen python app.py
```

应用默认监听 `http://127.0.0.1:8527`。设置 `STOCK_LAB_DISABLE_WORKERS=1` 后不会启动盘中实时 worker，适合执行历史回补。需要实时监控时不要在同一时间启动第二个应用进程。

### 2. 数据库状态

先确认当前数据库是全新安装还是已有旧表：

- 全新环境：导入 `init/stock_trading_lab_v2.sql`，不执行旧表迁移脚本。
- 存量环境：执行迁移前先停止写入任务和 Web 服务，并用 `mysqldump` 做完整备份。

存量迁移严格按以下顺序执行：

1. `db/migrations/001_create_english_schema.sql`
2. `db/migrations/002_migrate_legacy_data.sql`
3. 检查 16 组 gate、行数、业务键、日期范围、金额/数量聚合和 JSON 有效性。
4. 切换应用并完成测试、抽样和资金流 MySQL 回补。
5. `db/migrations/004_upsert_legacy_data.sql`
6. 确认 `004_legacy_containment_v1/succeeded`、全部 gate、全量备份和人工抽样后，才允许单独执行 `db/migrations/003_drop_legacy_schema.sql`。

执行迁移后必须能够回滚到迁移前完整备份。详细 gate 和回滚要求见[数据库重建与迁移](database-migrations.md)。

## 二、推荐回补顺序

```text
交易日历和指数
  -> securities、daily_quotes
  -> 5 分钟行情、Jiuyan、龙虎榜、资金流等事实数据
  -> KDJ、市场宽度、指数情绪、热门板块情绪
  -> MySQL 日期/行数/唯一键/金额单位校验
  -> 必要时重建当日 Redis 缓存
```

不要先运行 KDJ 或情绪任务。它们只会根据当前已有事实计算，不能补齐缺失的行情、涨停或资金流数据。

## 三、日线和基础事实

### 1. 日更任务回补

状态：**已支持 CLI**。

执行单个交易日：

```powershell
uv run --frozen python -m task.每日更新 --date 20260810
```

执行最近 N 个已知交易日：

```powershell
uv run --frozen python -m task.每日更新 --backfill 160
```

入口是 `task/每日更新.py`，参数含义如下：

- `--date YYYYMMDD`：只处理一个交易日，必须和本地交易日历匹配。
- `--backfill N`：处理本地 `index_daily` 中最新 N 个交易日，不是任意开始日期和结束日期。
- 任务最多按当前本地日历向前读取 160 个交易日用于计算。
- 任务按 index → securities/daily quotes → 市值/DDE → Jiuyan → 情绪顺序执行，写入或更新 `index_daily`、`securities`、`daily_quotes`、`jiuyan_actions` 和情绪表。
- 同一日期有 Redis 完成标记，标记存在时返回 `skipped`；锁 TTL 为 6 小时，完成标记 TTL 为 7 天。

### 2. 日更任务的依赖和失败处理

日更任务依赖 MySQL、Redis、行情源、Tushare token 和 Jiuyan 浏览器/网络访问。某个日期失败时任务会继续处理其他日期，但最终返回 `failed`，必须根据返回结果只重跑失败日期：

```powershell
uv run --frozen python -m task.每日更新 --date 20260810
```

不要因为完成标记存在就直接删除整批数据。先查看该日期四张事实表和两张情绪表是否完整，再决定是否清除单日完成标记或使用 repository upsert 修复。

### 3. 作者市场数据入口

状态：**已支持 CLI**。

证券和日线范围更新：

```powershell
uv run --frozen python -m task._1_日k数据更新 --start-date 20260101 --end-date 20260810
```

增加 `--force` 会重新请求范围内所有本地交易日并 upsert；默认跳过已有日线日期。

上证指数范围更新：

```powershell
uv run --frozen python -m task._4_上证指数日k --start-date 20260101 --end-date 20260810
```

当前 source 是 BaoStock `sh.000001` 日频。任务额外请求开始日前 20 个日历日，用前收计算振幅和涨跌额，再只写请求范围。

市值和自由流通字段：

```powershell
uv run --frozen python -m task._7_市值信息每日更新 --start-date 20260101 --end-date 20260810
```

使用 Tushare `daily_basic`。`total_market_value`、`circulating_market_value`、`free_float_market_value` 单位万元，`free_float_shares` 单位万股。默认只填空字段；`--force` 允许有效新值更新已有值，但 source 空值仍不擦除 MySQL 非空事实。

KPL DDE：

```powershell
uv run --frozen python -m task._10_开盘啦dde读取 --start-date 20260101 --end-date 20260810 --max-workers 4 --timeout 20 --retries 3
```

`dde_net_amount` 单位元。所有 worker 共用默认 0.5 秒全局请求间隔；部分证券失败时保留已提交行、打印失败证券并返回非零退出码。重新执行默认只补空值；`--force` 才覆盖有效已有值。上述四个入口都直接写 MySQL，不把历史事实或完成事实写入 Redis。

## 四、独立事实数据

### 1. 5 分钟行情

状态：**仅程序接口**。

入口：`stock_lab.jobs.intraday_bars_5m.update_intraday_bars_5m(start_date, end_date, ts_code)`。

示例：

```powershell
uv run --frozen python -c "from stock_lab.jobs.intraday_bars_5m import update_intraday_bars_5m; print(update_intraday_bars_5m(20260101, 20260810, '000001.SZ'))"
```

注意：

- 当前源是 BaoStock，不是 AkShare。
- 调用按股票和日期范围执行，建议一次只处理一只股票，并把失败的 `ts_code` 写入人工清单。
- 当前任务没有内置重试；异常时先确认 BaoStock 登录、代码后缀和日期范围，再重跑该股票。
- 目标表是 `intraday_bars_5m`，唯一标识由代码、日期、时间和复权标记规范化生成，重复运行使用 upsert。
- AkShare 分钟接口的历史深度通常不足以完成长期 5 分钟回补，不能直接替换 BaoStock。

### 2. Jiuyan 异动

状态：**仅程序接口**、**受上游限制**。

入口：`task._5_韭研公社异动.韭研公社异动采集(date)`。

示例：

```powershell
uv run --frozen python -c "from task._5_韭研公社异动 import 韭研公社异动采集; print(韭研公社异动采集(20260810))"
```

注意：

- 目标表是 `jiuyan_actions`，主键 `data_id` 按日期和板块/股票规范化生成。
- 返回数据的日期必须和请求日期一致；日期不一致时视为失败。
- 当前实现请求时隙默认随机等待 60 至 105 秒，最多尝试 2 次。
- 出现滑块或人工验证时暂停任务，在浏览器完成验证后重新执行失败日期。
- AkShare 没有 Jiuyan 编辑内容、涨停原因和项目板块归类的同语义接口，不能替换此任务。

### 3. 龙虎榜

状态：**仅程序接口**、**受上游限制**。该流程通过当前 FastAPI HTTP 接口启动，没有独立 CLI。

启动任务接口：

```powershell
$body = @{ startDate = 20260101; latestDate = 20260810 } | ConvertTo-Json
$job = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8527/api/v1/dragon-tiger/collection-jobs" -ContentType "application/json" -Body $body
Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8527/api/v1/dragon-tiger/collection-jobs/$($job.jobId)"
```

接口要求 `startDate <= latestDate`，并且日期必须存在于本地 `daily_quotes` 交易日历。任务状态通过返回的 `jobId` 查询，完成状态和失败原因以查询结果为准。

目标表包括 `dragon_tiger`、`brokers`、`broker_listing_history`。当前源是同花顺，稳定业务键由采集器生成；对连接和超时错误默认最多尝试 3 次，每次等待 0.5 秒。营业部页面缓存没有 TTL，长时间运行后要注意缓存陈旧。

AkShare 的 `stock_lhb_*` 接口可作为对照，但其东方财富字段、营业部 ID、业务键和同花顺结果不保证一致，不能无校验替换当前龙虎榜事实。

## 五、资金流历史

状态：**受上游限制**。

当前命令：

```powershell
uv run --frozen python -m task.fund_flow_backfill --days 365 --rate-delay 1.0 --retries 3 --retry-delay 2.0
```

当前实现必须如实理解：

- 默认源是 `EastMoneyFundFlowSource`，不是 `AkShareFundFlowSource`。
- 当前历史地址是 `https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get`，该地址在本机验证过会出现远端断开。
- README 中“当前命令使用 AkShare”的描述已经过时，不能据此判断运行结果。
- `--days` 是自然日回看，不是 `--year`；当前命令没有只回补 2026 年的 `--year` 参数。
- MySQL 目标是 `fund_flow_snapshots` 和 `fund_flow_records`，其中 `fund_flow_records.net_inflow_100m` 单位是亿元。
- 当前默认 writer 只把当天数据写入 Redis 历史缓存；历史事实以 MySQL 为准。
- 已存在的 `(flow_type, trade_date)` snapshot 会跳过；源数据缺失会报告失败日期，不会补零。

AkShare 目标改造方案是：行业使用 `stock_sector_fund_flow_hist`，概念使用 `stock_concept_fund_flow_hist`，所有请求串行共用至少 1 秒间隔，失败按有限次数指数退避，并支持按 2026 年交易日回补。在代码完成该改造并通过真实接口验证前，不要把上面的现有命令当作 AkShare 回补命令。

## 六、派生数据重算

### 1. KDJ

状态：**仅程序接口**。

入口：`stock_lab.jobs.kdj_indicators.update_kdj_indicators(start_date, end_date, stock_codes=None, repository=None, period=9)`。

```powershell
uv run --frozen python -c "from stock_lab.jobs.kdj_indicators import update_kdj_indicators; print(update_kdj_indicators(20260101, 20260810))"
```

任务会读取截至 `end_date` 的完整 `daily_quotes`，用默认 `period=9` 计算，再只写入请求日期范围。先补齐日线，不要用第三方 KDJ 结果替代项目计算。目标表是 `kdj_indicators`，按 `ts_code` 和 `trade_date` upsert。

### 2. 指数和热门板块情绪

状态：**仅程序接口**。

```powershell
uv run --frozen python -c "from task.emotion_analysis import 落库指数周期; print(落库指数周期(20260810))"
uv run --frozen python -c "from task.emotion_analysis import 落库热门板块情绪; print(落库热门板块情绪(20260810, 20260807))"
```

入口分别是 `task.emotion_analysis.落库指数周期(date)` 和 `task.emotion_analysis.落库热门板块情绪(date, source_date)`。

- 指数情绪依赖 `index_daily`、`daily_quotes` 和市场宽度事实。
- 热门板块情绪依赖当前日期的 `jiuyan_actions` 和前一交易日 `source_date` 的样本。
- 目标表是 `index_market_breadth`、`index_emotion_daily` 和 `hot_board_emotion_daily`。
- 派生任务使用 upsert，缺少基础事实时不能通过重复运行解决，必须先补基础表。

## 七、MySQL 验收 SQL

以下查询用于检查日期覆盖和行数；执行前先确认数据库连接指向目标环境。

```sql
SELECT COUNT(*) FROM securities;
SELECT MIN(trade_date), MAX(trade_date), COUNT(*) FROM index_daily;
SELECT MIN(trade_date), MAX(trade_date), COUNT(*) FROM daily_quotes;
SELECT trade_date, COUNT(*) FROM daily_quotes GROUP BY trade_date ORDER BY trade_date DESC LIMIT 10;
SELECT MIN(trade_time), MAX(trade_time), COUNT(*) FROM intraday_bars_5m;
SELECT MIN(trade_date), MAX(trade_date), COUNT(*) FROM kdj_indicators;
SELECT MIN(trade_date), MAX(trade_date), COUNT(*) FROM jiuyan_actions;
SELECT MIN(trade_date), MAX(trade_date), COUNT(*) FROM dragon_tiger;
SELECT COUNT(*) FROM brokers;
SELECT MIN(trade_date), MAX(trade_date), COUNT(*) FROM broker_listing_history;
SELECT MIN(trade_date), MAX(trade_date), COUNT(*) FROM fund_flow_snapshots;
SELECT MIN(s.trade_date), MAX(s.trade_date), COUNT(*)
FROM fund_flow_records r
JOIN fund_flow_snapshots s ON s.snapshot_id = r.snapshot_id;
SELECT MIN(net_inflow_100m), MAX(net_inflow_100m), COUNT(*) FROM fund_flow_records;
SELECT MIN(trade_date), MAX(trade_date), COUNT(*) FROM index_market_breadth;
SELECT MIN(trade_date), MAX(trade_date), COUNT(*) FROM index_emotion_daily;
SELECT MIN(trade_date), MAX(trade_date), COUNT(*) FROM hot_board_emotion_daily;
```

重复键检查示例：

```sql
SELECT ts_code, trade_date, COUNT(*) AS duplicate_count
FROM daily_quotes
GROUP BY ts_code, trade_date
HAVING COUNT(*) > 1;

SELECT flow_type, trade_date, collected_at, COUNT(*) AS duplicate_count
FROM fund_flow_snapshots
GROUP BY flow_type, trade_date, collected_at
HAVING COUNT(*) > 1;

SELECT snapshot_id, board_code, COUNT(*) AS duplicate_count
FROM fund_flow_records
GROUP BY snapshot_id, board_code
HAVING COUNT(*) > 1;

SELECT stock_code, trade_date, trade_time, adjustment_flag, COUNT(*) AS duplicate_count
FROM intraday_bars_5m
GROUP BY stock_code, trade_date, trade_time, adjustment_flag
HAVING COUNT(*) > 1;

SELECT ts_code, trade_date, COUNT(*) AS duplicate_count
FROM kdj_indicators
GROUP BY ts_code, trade_date
HAVING COUNT(*) > 1;

SELECT trade_date, board_name, stock_code, COUNT(*) AS duplicate_count
FROM jiuyan_actions
GROUP BY trade_date, board_name, stock_code
HAVING COUNT(*) > 1;

SELECT data_id, COUNT(*) AS duplicate_count
FROM dragon_tiger
GROUP BY data_id
HAVING COUNT(*) > 1;
```

资金流单位抽样：

```sql
SELECT s.flow_type, s.trade_date, r.board_code, r.board_name,
       r.net_inflow_100m
FROM fund_flow_records r
JOIN fund_flow_snapshots s ON s.snapshot_id = r.snapshot_id
ORDER BY s.trade_date DESC, r.net_inflow_100m DESC
LIMIT 20;
```

`fund_flow_records.net_inflow_100m` 必须按亿元解释；EastMoney `f62` 等元单位字段只能在 canonical 边界转换一次。

## 八、操作清单

### 首次部署

1. 配置 `.env`、Tushare token、MySQL 和 Redis。
2. 运行 `uv sync --all-groups --frozen`，导入 `init/stock_trading_lab_v2.sql`。
3. 先填充 `index_daily` 和 `securities`，确认交易日历可用。
4. 运行 `task.每日更新 --backfill N` 补齐日线和 Jiuyan/情绪依赖。
5. 按需补 5 分钟、龙虎榜和资金流事实。
6. 最后运行 KDJ 和情绪派生任务。
7. 执行本手册的日期、行数、唯一键和金额单位 SQL。

### 当年历史回补

以 2026 年为例，先确定本地 `index_daily` 已包含 2026 年完整交易日序列，再按以下顺序执行：

1. 用日更 CLI 按交易日补 `securities`、`daily_quotes` 和指数数据。
2. 用 `_7` 和 `_10` 补齐市值及 DDE，并处理结构化失败日期/证券。
3. 对需要分钟级回测的证券调用 5 分钟程序接口。
4. 按日期范围运行龙虎榜 API，按单日调用 Jiuyan。
5. 资金流执行前先确认实际 source 类和上游状态；当前命令不等于 AkShare 年度回补。
6. 日线和 Jiuyan 完整后按交易日重算 KDJ、市场宽度和两类情绪。
7. 对每张目标表执行日期覆盖、行数和重复键检查。

当前 `--backfill N` 只表示最近 N 个本地交易日，资金流 `--days` 只表示自然日窗口；两者都不能直接宣称“完整 2026 年”。

### 单日修复

1. 查出目标日期在 `index_daily`、`daily_quotes`、`jiuyan_actions` 和相关事实表的缺失情况。
2. 只重跑该日期的日更、Jiuyan、龙虎榜或资金流入口，不删除整年数据。
3. 确认事实数据落库后，再运行该日期的 KDJ 和情绪任务。
4. 删除或等待该日期的 Redis 完成标记前，先确认没有其他 worker 正在运行；优先使用 upsert 和任务返回状态。
5. 重新执行该日期的 SQL 抽样和唯一键检查。

### 中断后续跑

1. 保留失败输出，按失败日期和实体建立重跑清单。
2. 检查 Redis job lock、日更完成标记和 MySQL 已存在 snapshot，不要重复启动同一批并发任务。
3. 日更任务可按单日 `--date` 重跑；5 分钟、Jiuyan 和龙虎榜按失败证券/日期/任务范围重跑。
4. 资金流按 MySQL 中缺失的 `flow_type` 和 `trade_date` 重跑，源接口失败时暂停而不是补零。
5. 基础事实补齐后再重算派生数据；派生失败不需要重新抓取远程事实。
6. 完成 SQL 验收后再恢复实时 worker。

## 九、无效或禁止的操作

- 不要直接把 `stock_zh_a_hist` 的结果写进 `daily_quotes`，除非完成字段、复权、单位和供应商语义映射。
- 不要用 AkShare 当前板块成分股回填过去日期的历史成员关系。
- 不要用 generic 主力净流入替换 `dde_net_amount`。
- 不要把 `push2his.eastmoney.com` 当前失败误认为浏览器实时资金流也必然失败；两条链路需要分别验收。
- 不要在没有备份和 gate 的情况下执行 `003_drop_legacy_schema.sql`。
- 不要用 `SELECT COUNT(*)` 单独判断回补成功；必须同时检查日期覆盖、唯一键、关键字段和样本单位。
