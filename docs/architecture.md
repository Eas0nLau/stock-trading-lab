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
Legacy aliases are limited to `utils/common.py` and `utils/account.py` adapters for
the strategy files that have not migrated yet. Strategy and TDX monitor rewrites are
explicitly deferred.

## 依赖规则

```text
api -> modules -> infrastructure
jobs -> modules -> infrastructure
modules -> shared
infrastructure -> shared
```

`shared` 不依赖业务模块。领域算法不直接导入 FastAPI、Redis、浏览器或数据库连接。外部数据在 adapter 边界转换成英文领域模型。

策略选股的浏览器采集仍由 `实时监控/策略选股.py` 提供兼容 adapter；策略配置、快照、事件、当前入选状态和 SSE broker 由 `stock_lab.modules.strategy_pick` 正式模块拥有。

## 应用启动

`stock_lab.bootstrap.application.create_app()` 创建 FastAPI 应用。路由只注册一次，worker 只在 lifespan 启动。根目录 `app.py` 保留 `app` 对象和直接启动能力，但不再包含路由或调度实现。

MySQL 连接池按第一次查询创建，Redis 客户端创建时不执行网络请求，因此导入模块不会等待外部服务。

## 命名规则

- Python 文件、模块、函数、方法和变量使用英文 `snake_case`。
- 类、异常和数据模型使用英文 `PascalCase`。
- 常量使用英文 `UPPER_SNAKE_CASE`。
- 数据库表、列、索引和新版 API JSON 字段使用英文。
- 中文只用于界面文案、日志、领域展示值、第三方原始值和临时兼容入口。

## 数据库

数据库使用版本化 SQL 迁移。新 schema 先建立，存量数据显式复制和校验，应用逐模块切换后才允许执行旧表删除脚本。详细流程见 `docs/database-migrations.md`。

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
