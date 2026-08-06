# 项目架构

## 目标结构

正式 Python 代码位于 `src/stock_lab/`，根目录旧脚本只作为渐进迁移兼容入口。

```text
src/stock_lab/
├── api/              # FastAPI 路由组装
├── bootstrap/        # 应用工厂、生命周期、worker 和前端进程
├── config/           # 类型化配置和默认值
├── infrastructure/   # MySQL、Redis、浏览器和第三方数据源
├── jobs/             # 定时任务和长时间运行任务
├── modules/          # 按业务域组织的正式实现
└── shared/           # 异常、日志、时间和通用类型
```

`stock_lab.modules.market_data` owns the shared repository boundary for
`securities`, `daily_quotes`, and `index_daily`. It returns canonical English rows
and preserves string identifiers, including leading zeroes and exchange suffixes.
Legacy-shaped DataFrame aliases are limited to compatibility adapters. Active
research strategies execute through `stock_lab.modules.research` against canonical
market-data, fund-flow, and dragon-tiger repositories.

## 依赖规则

```text
api -> modules -> infrastructure
jobs -> modules -> infrastructure
modules -> shared
infrastructure -> shared
```

`shared` 不依赖业务模块。领域算法不直接导入 FastAPI、Redis、浏览器或数据库连接。外部数据在 adapter 边界转换成英文领域模型。

资金流向和策略选股的浏览器采集、解析、调度、快照、事件和 SSE broker 均由
`stock_lab.modules.fund_flow`、`stock_lab.modules.strategy_pick` 与
`stock_lab.infrastructure.browser` 拥有。兼容脚本只转发，不注册旧 REST 路由，也不访问旧 Redis 键。
应用组装会把同一个 `Settings` 显式绑定到浏览器 page factory；Chrome profile 使用该配置的
`project_root`，旧标签页策略使用 `browser_close_old_tabs`，组合路径不重新读取全局配置。
资金流向 worker 还会把停止事件传入初始化、监听和采集边界，并在退出时执行幂等且不抛出的资源清理。

`stock_lab.modules.emotion.index_cycle` 和 `stock_lab.modules.emotion.hot_board`
拥有指数及热门板块算法。正式 job 只传递英文规范字段；中文模块仅为直接脚本路径提供薄转发。

## 应用启动

`stock_lab.bootstrap.application.create_app()` 创建 FastAPI 应用。调用方提供的同一个 `Settings` 对象会显式传给路由、service factory、基础设施 client 和 worker 组装，不会在应用工厂中被忽略或替换为全局配置。路由只注册一次，worker 只在 lifespan 启动。启动时会读取 `002_parity_v1`；`running` 或 `failed` 状态会阻止 worker 和 Web 服务启动。根目录 `app.py` 保留 `app` 对象和直接启动能力，但不再包含路由或调度实现。

MySQL 连接池按第一次查询创建，Redis 客户端创建时不执行网络请求，因此导入模块不会等待外部服务。

## 命名规则

- Python 文件、模块、函数、方法和变量使用英文 `snake_case`。
- 类、异常和数据模型使用英文 `PascalCase`。
- 常量使用英文 `UPPER_SNAKE_CASE`。
- 数据库表、列、索引和新版 API JSON 字段使用英文。
- 中文只用于界面文案、日志、领域展示值、第三方原始值和临时兼容入口。

## 数据库

数据库使用版本化 SQL 迁移。`001` 可在中断后重跑，但会根据 `information_schema` 校验完整列和索引签名，已有不兼容表会直接中止。`002` 先持久化 `running`，再在 MySQL 支持事务的 DML 范围内复制和校验；异常 handler 回滚 DML 并持久化 `failed`，只有全部 16 组 gate 成功才提交 `succeeded` 和迁移版本。应用逐模块切换后，`003` 还必须验证 `001`、`002` 与该成功状态，才允许删除任何旧表。详细流程见 `docs/database-migrations.md`。

MySQL 执行、断线有限重试和 DataFrame 批量写入由 `stock_lab.infrastructure.database.operations` 拥有。`utils.db` 仅保留历史名称投影，不实现重试循环或递归写入。

`stock_lab.modules.ths` owns canonical read-only access to `ths_boards`,
`ths_board_constituents`, and `ths_stock_relations`. These tables are archived
reference data populated only by the legacy-data import migration. There is no
runtime producer or consumer, so the module accepts an injected database query
callable and deliberately has no engine, collector, job, API, or write method.
The three legacy THS tables can be dropped after import parity is confirmed; the
English tables remain import-only after that retirement.

TDX official code lives in `stock_lab.infrastructure.tdx` and
`stock_lab.modules.tdx`. The latter owns parsing and monitor signal logic; the
former owns lazy optional-client integration. The Chinese files under `实时监控/`
are compatibility launchers only, and official TDX code does not import
`config.py` or `PyMySQL`.
