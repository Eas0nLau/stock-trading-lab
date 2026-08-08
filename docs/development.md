# 开发指南

## 环境

```powershell
uv sync --all-groups
npm --prefix front install
```

复制 `.env.example` 为 `.env` 并填写 MySQL 必填配置。Redis、Tushare、DeepSeek 和通达信配置按功能选填。

## 启动

```powershell
uv run python app.py
```

后端监听 `8527`，前端 Vite 监听 `9527`。也可以运行 `启动项目.ps1` 完成依赖检查和启动。

## 测试

```powershell
uv run pytest -q
uv run python -m compileall -q src task 实时监控 utils strategy tests
npm --prefix front test
npm --prefix front run build
```

测试通过 `tests/conftest.py` 使用非敏感数据库占位配置，不会连接真实数据库。集成测试若需要 MySQL，必须创建独立测试库并显式标记。

## 模块开发

新业务进入 `src/stock_lab/modules/<domain>/`，每个模块按需要包含 `api.py`、`service.py`、`repository.py`、`schemas.py`、`domain.py` 和 `jobs.py`。不要向 `utils/`、`实时监控/` 或 `task/` 增加新的正式实现。

TDX integration belongs in `src/stock_lab/infrastructure/tdx/`; TDX parsing and
monitor logic belongs in `src/stock_lab/modules/tdx/`. Keep TDX client loading
lazy so unit tests and imports do not require a local TDX installation.

每项行为变更先写失败测试。领域算法优先使用纯数据输入输出；数据库、缓存和第三方接口通过构造参数或协议注入。

`tests/test_cutover_contracts.py` 是迁移边界测试。新增正式代码不得导入兼容目录、定义中文标识符或恢复旧表/旧 Redis 键；兼容文件不得重新承载路由、网络、浏览器、算法和持久化实现。

## 提交边界

配置、基础设施、应用组装、单个业务模块和数据库迁移分别提交。每个提交都必须能运行对应测试，禁止把大批文件移动和行为改动混在同一提交中。
