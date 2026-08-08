# Redis 仅缓存化设计

## 原则

MySQL 保存所有业务事实、历史、配置和可审计状态。Redis 仅保存可重建的缓存、短期锁、完成标记和实时事件通知，并且除实时订阅队列外必须设置 TTL。

## 策略选股

新增 `strategy_definitions`、`strategy_pick_snapshots`、`strategy_pick_stocks` 和 `strategy_pick_events`。动态策略字段保存为 MySQL JSON。旧 `策略选股:*` 和现有 `strategy_pick:v1:*` 历史合并迁移，按策略、采集日期时间、股票代码和事件 ID 去重。

API 和采集器以 MySQL 为事实源。Redis 只缓存当天 latest/history/events 和 SSE 通知，缓存缺失时从 MySQL 回填。

## 资金流向

现有 MySQL 表继续作为事实源。Redis 只保留当天 V1 快照、Top-N 图表和日期缓存；旧 `fund_flow:*`、`fund_flow_概念:*` 历史 key 在校验后删除。

## 保留的 Redis 状态

每日更新完成标记和任务锁保留，必须有 TTL。历史回补、策略定义、历史事件、历史快照和业务配置不得只存在 Redis。

## 安全流程

迁移前备份 MySQL 和 Redis。先复制并校验，再切换 API/采集器，最后清理旧 key。不得执行 `003_drop_legacy_schema.sql`。
