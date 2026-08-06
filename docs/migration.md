# 代码迁移映射

| 旧入口 | 新入口 | 状态 |
| --- | --- | --- |
| `config.py` | `stock_lab.config` | 已建立兼容投影 |
| `utils/mysql_base.py` | `stock_lab.infrastructure.database` | 已建立惰性兼容层 |
| `utils/redis_base.py` | `stock_lab.infrastructure.cache` | 已建立兼容层 |
| `app.py` | `stock_lab.bootstrap.application` | 已建立兼容入口 |
| `front_run.py` | `stock_lab.bootstrap.frontend` | 已建立兼容入口 |
| `app.py` 后台线程 | `stock_lab.jobs.realtime_monitor` | 已迁移装配和定时任务分发，不再删除其他进程持有的任务锁 |
| `实时监控/资金流向.py` | `stock_lab.modules.fund_flow` | V1 REST/SSE、Redis 写入和前端已迁移；浏览器解析暂作 adapter |
| `实时监控/策略选股.py` | `stock_lab.modules.strategy_pick` | V1 REST/SSE、Redis 读写、前端和 worker 已迁移；浏览器调度与解析暂作 adapter |
| `实时监控/情绪周期.py` | `stock_lab.modules.emotion` | 英文 API 和数据读写已迁移；旧算法暂作适配器 |
| `实时监控/热门板块情绪.py` | `stock_lab.modules.emotion` | 英文 API 和查询已迁移；旧路由暂时保留 |
| `task/每日更新.py` | `stock_lab.jobs.daily_update` | 正式英文编排和 V1 幂等状态已迁移；旧路径为 CLI/调用兼容入口 |
| `task/盘前纪要.py` | `stock_lab.jobs.premarket_summary` | 正式提取、INI 输出和 V1 幂等状态已迁移；公开仓库需注入来源 adapter |
| `task/emotion_analysis.py` | `stock_lab.modules.emotion.jobs` | 已移除旧表写入，仅转发到正式英文表 job |
| `task/data_sources.py` | `index_daily` / `securities` / `daily_quotes` | 默认写入已切换英文表 |
| `task/_2_分时数据获取_5分k.py` | `stock_lab.jobs.intraday_bars_5m` | 已恢复薄兼容入口；正式采集写入 `intraday_bars_5m` |
| `stock_lab.modules.market_data` | `securities` / `daily_quotes` / `index_daily` | canonical repository and model contract established |
| KDJ 更新与策略 SQL | `stock_lab.jobs.kdj_indicators` / `kdj_indicators` | 已切换英文任务、列名和表名 |
| `游资溢价分析/` | `stock_lab.modules.dragon_tiger` | canonical models, parsers, repositories, collectors, and premium analysis migrated; executable paths are thin adapters |
| `strategy/` | `stock_lab.modules.research` | 待研究模块迁移 |

TDX monitor migration
---------------------

`stock_lab.infrastructure.tdx` owns the lazy TDX plugin adapter, while
`stock_lab.modules.tdx` owns English parsing, snapshot, global-alert, auction,
and securities-universe logic. `实时监控/tdx_全局监控.py` and
`实时监控/tdx_竞价监控.py` remain executable compatibility launchers. The
auction universe is read through `MarketDataRepository.securities()`; official
code does not open a direct PyMySQL connection.

兼容文件只允许转发。业务模块完成英文 API、数据库、前端和测试迁移后，更新本表并删除对应旧入口。

Market-data repository migration
--------------------------------

`stock_lab.modules.market_data` is the owner of canonical English models and SQL for
`securities`, `daily_quotes`, and `index_daily`. Repository outputs use `ts_code`,
`symbol`, `open_price`, `close_price`, `previous_close`, and the other schema column
names exactly as stored. `utils/common.py` and `utils/account.py` remain thin adapters
for existing strategy callers and may expose legacy-shaped aliases only after the
repository query. A bare numeric code is padded to six digits; an exchange suffix is
preserved, so `1.SZ` becomes `000001.SZ` and never becomes an integer.

The 57 strategy files, TDX monitor files, and unrelated research SQL remain deferred
consumers. They can migrate to the repository interfaces without depending on the
legacy tables.

Five-minute bars and KDJ
-----------------------

`stock_lab.infrastructure.market_data.BaoStockSource` is a lazy adapter: importing
the application does not import, log in to, or contact BaoStock. The official job
depends only on `IntradayBarSource.fetch_5m_bars()` so tests and alternate sources
can be injected without network access. Source rows are normalized to English
columns before `MarketDataRepository` upserts deterministic `data_id` values into
`intraday_bars_5m`.

`stock_lab.jobs.kdj_indicators` reads canonical `daily_quotes`, calculates K, D,
and J independently for each `ts_code`, and upserts `kdj_indicators`. Active KDJ
and five-minute strategy SQL now reads the English tables; SQL aliases preserve
historical `J`, `J2`, `date`, `time`, `open`, and `close` consumer shapes. The
Chinese five-minute task module contains no source or persistence implementation.

前端 `IndexCycle.vue` 和 `HotBoardEmotion.vue` 已使用 `/api/v1/emotion/*` 与英文模型字段。旧 `/api/emotion/*` 和 `/api/hot-board-emotion/*` 已停止注册，避免读取不再更新的旧表。

`FundFlow.vue` 已使用 `/api/v1/fund-flow/{flow_type}/dates`、`/history/{trade_date}` 和 `/api/v1/fund-flow/stream`，内部模型统一为英文 camelCase。采集快照写入 `fund_flow:v1:{flow_type}:history:{trade_date}`，日期索引写入 `fund_flow:v1:{flow_type}:dates`，同一采集时间重复写入时替换最后一帧。迁移期间，显式 adapter 同步更新旧 `fund_flow:history:*`、`fund_flow_概念:history:*` 和对应 `latest` 键，供情绪周期与历史策略等直接消费者读取；V1 读取也可翻译旧历史。旧 `/api/zijin/*` 已停止注册；SSE 由 API 与采集线程所在的单一应用进程内 broker 管理订阅和清理，不使用 Redis Pub/Sub。`实时监控/资金流向.py` 仅保留浏览器采集兼容逻辑，策略选股仍待完成独立迁移。

`StrategyPickMonitor.vue` 和 `App.vue` 已使用 `front/src/modules/strategy-pick`，请求 `/api/v1/strategy-pick/*` 并使用 camelCase view model。正式模块写入 `strategy_pick:v1:strategies`、`strategy_pick:v1:{strategy_id}:latest`、`history:{date}`、`events:{date}`、`selected_state`、`dates` 和全局事件键；显式 legacy adapter 在迁移期读取/更新旧 `策略选股:*` 键，供仍直接读取旧键的策略代码使用。旧 `/api/strategy-pick/*` 已停止注册；SSE 使用单一应用进程内 broker，并在连接关闭时清理订阅。浏览器策略页面和响应解析仍由兼容 adapter 承担，worker 通过官方 collector 写入 V1。

Dragon-tiger and broker migration
---------------------------------

`stock_lab.modules.dragon_tiger` owns the canonical English models, source
parsers, repository SQL, collector orchestration, and broker-premium analysis
for `dragon_tiger`, `broker_listing_history`, `broker_top_stats`, and `brokers`.
Premium analysis reads `daily_quotes` through `MarketDataRepository`. The old
`游资溢价分析` files contain only executable adapters and perform no work when
imported. Active strategy dragon-tiger queries use canonical tables and columns;
Chinese aliases remain only where historical DataFrame consumers require them.

Scheduled jobs migration
------------------------

`stock_lab.jobs.daily_update` owns the daily source and emotion-job order,
trading-date window, backfill results, and `stock_lab:jobs:v1:daily_update:*`
state. `stock_lab.jobs.premarket_summary` owns source-independent ordered stock
extraction, INI output, and `stock_lab:jobs:v1:premarket_summary:*` state. Both
use `stock_lab.infrastructure.cache.RedisJobLock`, whose expiring token is
released atomically only by its owner.

The public repository has no surviving `task/盘前纪要.py` collector implementation
or historical source adapter. Premarket runs therefore require an injected source;
without one they return `disabled` and leave state unchanged. The Chinese daily,
premarket, and emotion-analysis modules are import-safe forwarding wrappers.
