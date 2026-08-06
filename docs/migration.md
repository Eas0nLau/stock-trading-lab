# 代码迁移映射

| 旧入口 | 新入口 | 状态 |
| --- | --- | --- |
| `config.py` | `stock_lab.config` | 已建立兼容投影 |
| `utils/mysql_base.py` | `stock_lab.infrastructure.database` | 已建立惰性兼容层 |
| `utils/redis_base.py` | `stock_lab.infrastructure.cache` | 已建立兼容层 |
| `app.py` | `stock_lab.bootstrap.application` | 已建立兼容入口 |
| `front_run.py` | `stock_lab.bootstrap.frontend` | 已建立兼容入口 |
| `app.py` 后台线程 | `stock_lab.jobs.realtime_monitor` | 已迁移装配逻辑 |
| `实时监控/资金流向.py` | `stock_lab.modules.fund_flow` | 待业务模块迁移 |
| `实时监控/策略选股.py` | `stock_lab.modules.strategy_pick` | 待业务模块迁移 |
| `实时监控/情绪周期.py` | `stock_lab.modules.emotion` | 待业务模块迁移 |
| `task/每日更新.py` | `stock_lab.jobs.daily_update` | 待业务模块迁移 |
| `strategy/` | `stock_lab.modules.research` | 待研究模块迁移 |

兼容文件只允许转发。业务模块完成英文 API、数据库、前端和测试迁移后，更新本表并删除对应旧入口。
