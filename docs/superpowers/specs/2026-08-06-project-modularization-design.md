# 项目模块化重构设计

## 背景

当前项目已经包含行情采集、实时监控、情绪分析、每日任务、策略研究、龙虎榜分析和 Vue 前端等多个业务方向，但代码主要按历史脚本逐步堆积在根目录、中文目录和通用 `utils/` 目录中。`app.py` 同时承担 FastAPI 组装、后台线程、定时任务和前端进程启动，导致启动边界、业务边界和基础设施边界相互耦合。

本次重构采用渐进式迁移。正式实现进入新的 Python 包，旧入口暂时保留为兼容包装；每个模块迁移后独立验证，最终再删除旧实现。重构工作在独立分支 `refactor/modularize-project` 进行。

## 目标

- 建立清晰的应用启动、配置、基础设施、业务模块和任务调度边界。
- 将外部数据源、数据库、Redis、浏览器和通达信依赖隔离在基础设施层。
- 让核心业务服务可以脱离 FastAPI、真实数据库和网络单独测试。
- 保持迁移阶段可运行，避免 API 重复注册、后台任务双启动和数据库双写。
- 统一前端模块边界、API 客户端和共享组件。
- 整理研究脚本与生产运行代码的关系。
- 同步更新 README、环境安装、架构、开发和迁移文档。

## 非目标

- 第一阶段不重写策略研究脚本的交易逻辑和历史实验结果。
- 不强制立即修改现有数据库表结构。
- 不将所有历史文件一次性移动后再统一修复。
- 不把通达信实时工具纳入 Web 服务的默认启动路径。
- 不在本次重构中改变股票研究和交易辅助功能的业务口径。

## 总体架构

正式 Python 包位于 `src/stock_lab/`：

```text
src/stock_lab/
├── bootstrap/
│   ├── application.py       # FastAPI 应用创建
│   ├── lifecycle.py         # 启动和关闭流程
│   └── workers.py           # 后台线程或调度器管理
├── config/
│   ├── settings.py          # 环境变量和配置对象
│   └── defaults.py          # 默认业务参数
├── shared/
│   ├── errors.py            # 统一异常
│   ├── logging.py           # 日志初始化
│   ├── time.py              # 交易日和时间工具
│   └── types.py             # 通用类型
├── infrastructure/
│   ├── database/            # SQLAlchemy、MySQL 会话和事务
│   ├── cache/               # Redis 客户端、锁和状态
│   ├── browser/             # Chrome/DrissionPage 适配器
│   ├── market_data/         # Tushare、AkShare、Baostock
│   └── tdx/                 # 通达信文件和实时插件
├── modules/
│   ├── market_data/
│   ├── fund_flow/
│   ├── strategy_pick/
│   ├── emotion/
│   ├── premarket/
│   ├── dragon_tiger/
│   └── research/
├── api/
│   ├── routes/
│   ├── schemas/
│   └── dependencies.py
└── jobs/
    ├── scheduler.py
    ├── daily_update.py
    └── realtime_monitor.py
```

依赖方向固定为：

```text
api -> modules -> infrastructure
jobs -> modules -> infrastructure
modules -> shared
infrastructure -> shared
shared 不依赖业务模块
```

业务模块使用统一结构：

```text
module/
├── api.py          # 路由
├── service.py      # 用例和业务编排
├── repository.py   # 数据读写
├── schemas.py      # 输入输出模型
├── domain.py       # 领域算法或领域对象
└── jobs.py         # 模块专属后台任务，可选
```

## 迁移阶段

### 阶段一：基础设施与应用启动

迁移配置、MySQL、Redis、日志、FastAPI 生命周期、后台线程管理和前端启动逻辑。`app.py` 变为调用新应用工厂的薄包装，不改变现有端口和基本启动方式。

### 阶段二：市场数据与情绪

迁移 `task/data_sources.py`、`task/emotion_analysis.py`、情绪周期、热门板块算法和每日更新中的相关编排。数据源先转换为标准化数据，再由服务调用领域算法，最后通过 repository 落库。

```text
数据源适配器 -> market_data service -> emotion service -> repository -> API / daily job
```

### 阶段三：实时监控

迁移资金流向、策略选股、浏览器采集和 SSE 推送。

```text
采集器 -> 标准化器 -> 服务 -> Redis 状态/快照 -> SSE API
```

应用启动时只允许新调度器创建后台任务。旧入口只能转发调用，不能重复注册 API 或创建线程。

### 阶段四：研究与实验

将 `strategy/` 和 `游资溢价分析/` 按研究领域归档到 `research/`。历史脚本先保持内容稳定，通过策略注册表或命令行入口统一发现和运行，不在第一轮逐个重写策略逻辑。

## 兼容层

- `app.py` 转发到 `stock_lab.bootstrap.application`。
- `config.py` 转发到新 Settings，同时暂时暴露旧配置变量。
- `task/每日更新.py` 转发到 `jobs.daily_update`。
- `实时监控/*.py` 转发到对应业务模块。
- `utils/` 停止新增业务代码，迁移完成的能力从中移除或标记废弃。
- 旧 API 路径在迁移期间保留；新接口可逐步引入 `/api/v1`。
- 数据库访问通过新 repository 隔离，现有表结构先保持不变。

兼容模块只允许转发，不复制业务实现。每个兼容入口都应记录目标模块和弃用说明。

## 错误处理与运行状态

统一定义：`ConfigurationError`、`InfrastructureError`、`DataValidationError`、`JobExecutionError` 和 `DomainError`。

- API 层将内部异常转换为统一 JSON 错误响应。
- Job 层记录任务名、交易日、数据源、阶段和异常原因。
- 外部采集使用有限重试和递增等待。
- 数据库批量写入使用事务，失败回滚。
- Redis 锁必须设置过期时间，异常时释放。
- 数据不完整时不写入伪造分析结果。
- 后台线程异常必须记录并更新任务状态，不能静默退出。

实时任务、每日任务和兼容层必须有明确的单实例保护，避免双采集和双写。

## 前端模块化

```text
front/src/
├── app/              # 应用初始化、标签页注册
├── modules/
│   ├── fund-flow/
│   ├── strategy-pick/
│   ├── emotion/
│   └── hot-board-emotion/
├── shared/
│   ├── api/
│   ├── components/
│   ├── composables/
│   └── utils/
└── views/
```

页面不直接拼接重复的请求逻辑；API 客户端、SSE、通知和标签页状态放到共享或对应业务模块。现有页面和接口字段先保持行为一致，模块迁移后再逐步收紧类型和响应模型。

## 测试策略

```text
tests/
├── unit/             # 配置、领域算法、解析器、共享工具
├── integration/      # 数据库、缓存、模块、任务
├── api/              # 路由响应和错误映射
└── contract/         # 旧导入入口和 API 兼容性
```

测试要求：

- 领域算法不依赖真实数据库和网络。
- 外部数据源通过协议和 fake adapter 测试。
- 每个任务覆盖成功、失败、重试、锁释放和幂等执行。
- API 覆盖正常响应、空数据和异常响应。
- 兼容测试验证旧入口可以调用新实现。
- 前端执行 `npm run build`，并覆盖核心 API 客户端和 SSE 逻辑。
- CI 执行 Python 测试、前端构建、导入检查和基础格式检查。

## 文档更新

重构同步更新：

- `README.md`：目录、启动方式、模块边界和迁移说明。
- `环境安装.md`：环境准备、数据库、Redis、Node.js 和启动命令。
- `docs/architecture.md`：架构图、依赖规则和数据流。
- `docs/development.md`：代码规范、模块开发、测试和调试方式。
- `docs/migration.md`：旧入口到新模块的映射表。
- `.env.example`：配置分组、必填项和可选项。

## 完成标准

- 新应用入口可以独立启动 FastAPI。
- 旧入口能够转发到新实现。
- API、任务和实时监控不会重复注册或重复启动。
- 核心业务模块可以脱离 Web 入口单独测试。
- 前端完成模块化整理并成功构建。
- 现有功能在迁移后继续可用。
- 文档与实际目录、命令和配置一致。
- 测试覆盖迁移边界、任务幂等和后台任务生命周期。
