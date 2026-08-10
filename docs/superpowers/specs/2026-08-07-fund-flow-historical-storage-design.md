# 资金流向历史存储与回补设计

## 目标

资金流向历史以 MySQL 为事实源，Redis 只承担当日分钟快照、日期列表、Top-N 矩阵缓存和实时事件通知。历史回补范围为从当前交易日向前一年。

## 数据契约

- `flow_type`：`industry` 或 `concept`。
- `trade_date`：交易日整数。
- `collected_at`：采集时间。
- `board_code`、`board_name`、`leader`：板块维度。
- `net_inflow_100m`：亿元，MySQL 使用 `DECIMAL(20,6)`。
- EastMoney 原始 `f62` 单位为元，进入 canonical 层统一除以 `100000000`；已存在旧 Redis 数据按同一规则校正一次。
- API 返回保留 canonical 数值，前端金额、坐标轴、tooltip 和标签统一四舍五入到 2 位。

## 表与索引

- `fund_flow_snapshots` 保存每个采集批次的日期、时间、类型和记录数量。
- `fund_flow_records` 保存板块记录，唯一键为 `snapshot_id + board_code`。
- 按 `flow_type + trade_date + collected_at`、`flow_type + trade_date` 建索引。

## 回补策略

- 每个交易日保存一份每日汇总，回补任务按日期倒序执行，遇到已存在批次跳过。
- 当前接口继续写 Redis，并在同一采集成功后写 MySQL；MySQL 写入失败不得刷新 Redis 成功状态。
- Redis 缺失时 API 从 MySQL 读取并回填缓存。
- 一年历史数据源通过可注入 adapter 提供；测试使用 fake，真实运行使用配置的数据源。无法取得的日期记录失败原因，不伪造空数据。

## 安全与验证

- 迁移前备份 Redis/MySQL。
- 校验单位转换、日期覆盖、唯一键、记录数和金额范围。
- 不执行 `003_drop_legacy_schema.sql`；旧 Redis key 和旧表在人工抽样确认前保留。
