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
| `实时监控/策略选股.py` | `stock_lab.modules.strategy_pick` | 待业务模块迁移 |
| `实时监控/情绪周期.py` | `stock_lab.modules.emotion` | 英文 API 和数据读写已迁移；旧算法暂作适配器 |
| `实时监控/热门板块情绪.py` | `stock_lab.modules.emotion` | 英文 API 和查询已迁移；旧路由暂时保留 |
| `task/每日更新.py` | `stock_lab.modules.emotion.jobs` | 情绪 job 已迁移；调度入口仍为兼容文件 |
| `task/data_sources.py` | `index_daily` / `securities` / `daily_quotes` | 默认写入已切换英文表 |
| `strategy/` | `stock_lab.modules.research` | 待研究模块迁移 |

兼容文件只允许转发。业务模块完成英文 API、数据库、前端和测试迁移后，更新本表并删除对应旧入口。

前端 `IndexCycle.vue` 和 `HotBoardEmotion.vue` 已使用 `/api/v1/emotion/*` 与英文模型字段。旧 `/api/emotion/*` 和 `/api/hot-board-emotion/*` 已停止注册，避免读取不再更新的旧表。

`FundFlow.vue` 已使用 `/api/v1/fund-flow/{flow_type}/dates`、`/history/{trade_date}` 和 `/api/v1/fund-flow/stream`，内部模型统一为英文 camelCase。采集快照写入 `fund_flow:v1:{flow_type}:history:{trade_date}`，日期索引写入 `fund_flow:v1:{flow_type}:dates`，同一采集时间重复写入时替换最后一帧。旧 `/api/zijin/*` 已停止注册；`实时监控/资金流向.py` 仅保留浏览器采集兼容逻辑，策略选股仍待完成独立迁移。
