# 代码迁移映射

| 旧入口 | 新入口 | 状态 |
| --- | --- | --- |
| `config.py` | `stock_lab.config` | 已建立兼容投影 |
| `utils/mysql_base.py` | `stock_lab.infrastructure.database` | 已建立惰性兼容层 |
| `utils/redis_base.py` | `stock_lab.infrastructure.cache` | 已建立兼容层 |
| `app.py` | `stock_lab.bootstrap.application` | 已建立兼容入口 |
| `front_run.py` | `stock_lab.bootstrap.frontend` | 已建立兼容入口 |
| `app.py` 后台线程 | `stock_lab.jobs.realtime_monitor` | 已迁移装配逻辑 |
| `实时监控/资金流向.py` | `stock_lab.modules.fund_flow` | V1 REST/SSE、Redis 写入和前端已迁移；浏览器解析暂作 adapter |
| `实时监控/策略选股.py` | `stock_lab.modules.strategy_pick` | V1 REST/SSE、Redis 读写、前端和 worker 已迁移；浏览器调度与解析暂作 adapter |
| `实时监控/情绪周期.py` | `stock_lab.modules.emotion` | 英文 API 和数据读写已迁移；旧算法暂作适配器 |
| `实时监控/热门板块情绪.py` | `stock_lab.modules.emotion` | 英文 API 和查询已迁移；旧路由暂时保留 |
| `task/每日更新.py` | `stock_lab.modules.emotion.jobs` | 情绪 job 已迁移；调度入口仍为兼容文件 |
| `task/data_sources.py` | `index_daily` / `securities` / `daily_quotes` | 默认写入已切换英文表 |
| `strategy/` | `stock_lab.modules.research` | 待研究模块迁移 |

兼容文件只允许转发。业务模块完成英文 API、数据库、前端和测试迁移后，更新本表并删除对应旧入口。

前端 `IndexCycle.vue` 和 `HotBoardEmotion.vue` 已使用 `/api/v1/emotion/*` 与英文模型字段。旧 `/api/emotion/*` 和 `/api/hot-board-emotion/*` 已停止注册，避免读取不再更新的旧表。

`FundFlow.vue` 已使用 `/api/v1/fund-flow/{flow_type}/dates`、`/history/{trade_date}` 和 `/api/v1/fund-flow/stream`，内部模型统一为英文 camelCase。采集快照写入 `fund_flow:v1:{flow_type}:history:{trade_date}`，日期索引写入 `fund_flow:v1:{flow_type}:dates`，同一采集时间重复写入时替换最后一帧。迁移期间，显式 adapter 同步更新旧 `fund_flow:history:*`、`fund_flow_概念:history:*` 和对应 `latest` 键，供情绪周期与历史策略等直接消费者读取；V1 读取也可翻译旧历史。旧 `/api/zijin/*` 已停止注册；SSE 由 API 与采集线程所在的单一应用进程内 broker 管理订阅和清理，不使用 Redis Pub/Sub。`实时监控/资金流向.py` 仅保留浏览器采集兼容逻辑，策略选股仍待完成独立迁移。

`StrategyPickMonitor.vue` 和 `App.vue` 已使用 `front/src/modules/strategy-pick`，请求 `/api/v1/strategy-pick/*` 并使用 camelCase view model。正式模块写入 `strategy_pick:v1:strategies`、`strategy_pick:v1:{strategy_id}:latest`、`history:{date}`、`events:{date}`、`selected_state`、`dates` 和全局事件键；显式 legacy adapter 在迁移期读取/更新旧 `策略选股:*` 键，供仍直接读取旧键的策略代码使用。旧 `/api/strategy-pick/*` 已停止注册；SSE 使用单一应用进程内 broker，并在连接关闭时清理订阅。浏览器策略页面和响应解析仍由兼容 adapter 承担，worker 通过官方 collector 写入 V1。
