# 数据库重建与迁移

## 原则

新版 schema 的表、列、索引和约束全部使用英文。迁移先创建新表，再显式复制数据、执行阻断式校验、切换应用，最后由单独脚本删除旧表。四个脚本面向 MySQL 8；任何 gate 失败都会停止流程，不会把当前版本记录为成功。

全新环境不执行存量迁移，直接导入自包含的 `init/stock_trading_lab_v2.sql`。该文件包含 `CREATE DATABASE`、`USE` 和完整英文 DDL，不依赖 MySQL 客户端的 `SOURCE`。`init/LEGACY_stock_trading_lab_chinese_schema.sql` 是退役历史转储，禁止用于当前安装。

## 执行顺序

1. 停止写入任务和 Web 服务。
2. 使用 `mysqldump` 完整备份数据库。
3. 执行 `db/migrations/001_create_english_schema.sql`。脚本会补建缺失表，并校验所有 canonical 表的列类型、可空性和索引签名；不兼容的已有表会中止执行。
4. 执行 `db/migrations/002_migrate_legacy_data.sql`。非法 legacy JSON 或无法无损解析的自由格式营业部统计会在复制前中止，并报告源表、源列和业务键。
5. 检查 16 组 gate 输出。脚本自动比较行数、映射后去重键，以及适用的日期范围、关键金额/数量/成交量聚合和 JSON 有效性；任一差异会 `SIGNAL` 并停止。
6. 切换对应模块 repository、API 和前端。
7. 运行完整测试和人工数据抽样。
8. 资金流向完成 MySQL 回补后，校验 `fund_flow_snapshots`、`fund_flow_records` 的日期覆盖、行数、唯一键和金额样本；使用 `stock_lab.jobs.fund_flow_backfill.migrate_legacy_redis` 将旧 V1 Redis 快照按 万元到亿元校正一次并从 canonical 数据重建缓存。
9. 所有模块完成后执行 `004_upsert_legacy_data.sql`，将旧表数据单向新增或更新到英文表，保留英文表独有业务键，并记录 16 条结构化包含校验。
10. `004_legacy_containment_v1/succeeded`、16 条表级 gate、全量备份和人工抽样全部确认后，另行执行 `003_drop_legacy_schema.sql`。
11. 在运行新的韭研采集与情绪回补前，依次执行 `005_normalize_intraday_minute_identity.sql` 和 `006_create_jiuyan_collection_days.sql`。`006` 只建立日期完整性清单，不把既有韭研日期追认为完整；旧日期必须重新采集后才能供新的热门板块情绪计算使用。

## 回滚

应用切换前，删除未投入使用的新表即可回滚。应用切换后，停止服务并恢复迁移前完整备份。旧表删除脚本不属于初始化或自动升级流程，禁止在无备份情况下执行。

## 最终单向补迁

停止每日更新、采集任务和 Web 写入并完成全库备份后，通过 MySQL 客户端执行：

```bash
db/migrations/004_upsert_legacy_data.sql
```

`004` 对 16 组映射执行 `INSERT ... ON DUPLICATE KEY UPDATE`：旧表缺失键插入，同键映射字段更新，新表独有键不删除。每组 gate 要求源键唯一、目标包含全部源键、映射字段一致、目标行数不减少且迁移前目标键无丢失。

## 验证项

- 旧表源行数等于映射后 distinct key 数；重复键会阻断迁移。
- 新表必须包含全部旧表业务键，但允许保留旧表不存在的新数据。
- 所有同键映射字段必须 null-safe 一致。
- 新表迁移后行数不得减少，迁移前业务键不得丢失。
- 最早、最晚交易日期或采集日期一致（存在日期映射时）。
- 关键金额、成交量、数量、指标或样本数聚合值一致（存在可比事实列时）。
- legacy JSON 在复制前通过 `JSON_VALID`；canonical JSON 在复制后再次通过 `JSON_VALID`。
- 新 schema 中不存在非 ASCII 标识符。
- `fund_flow_records.net_inflow_100m` 必须为 `DECIMAL(20,6)`，单位为亿元；EastMoney `f62` 原始单位为元，只在 canonical 边界除以 `100000000` 一次。

`002` 开始时先提交 `migration_validations(validation_version='002_parity_v1', status='running')`，再开启数据复制事务并在事务内移除陈旧的 `002` 版本/validation。SQL 异常 handler 会回滚复制 DML、写入 `failed` 及 MySQL 错误信息并重新抛出；全部 gate 成功后才在同一事务中写入 `succeeded` 和 `schema_migrations`。因此中断、失败和成功都可跨进程观察，应用 lifespan 会拒绝 `running`/`failed` 状态。仅看脚本输出或仅看迁移版本不构成删除授权，`003` 同时检查两类状态。

`jiuyan_collection_days` 是韭研日期完整性的唯一事实来源。采集事务同时替换当日 `jiuyan_actions` 并写入来源计数、接受计数和响应指纹；Redis 状态或通知不能替代该清单。没有 `status='complete'` 清单的历史日期保持未验证状态。

## 当前切换状态

`index_daily`、`securities`、`daily_quotes`、`intraday_bars_5m`、`kdj_indicators`、`index_market_breadth`、`index_emotion_daily`、`hot_board_emotion_daily` 和 `jiuyan_actions` 已接入正式 repository、任务或新版 API。

市场数据的正式访问边界是 `stock_lab.modules.market_data`。Repository 只返回英文规范列：
`securities.ts_code`、`securities.symbol`、`daily_quotes.ts_code`、
`daily_quotes.trade_date`、`daily_quotes.open_price`、`daily_quotes.close_price` 和
`index_daily.trade_date` 等。代码值按字符串处理，补齐股票代码的前导零并保留交易所后缀。
共享旧工具仅在适配器边界恢复 `open`、`close`、`pre_close` 等历史键；这不改变存量数据库迁移的备份、校验和回滚要求。

龙虎榜和营业部的正式访问边界是 `stock_lab.modules.dragon_tiger`。采集、分析和活跃策略查询已切换到 `dragon_tiger`、`broker_listing_history`、`broker_top_stats`、`brokers` 和 `daily_quotes`；旧中文路径只保留无导入副作用的执行适配器，因此龙虎榜相关代码不再阻塞旧表删除。

同花顺的 `ths_boards`、`ths_board_constituents` 和 `ths_stock_relations` 是归档参考数据，正式访问边界是只读的 `stock_lab.modules.ths`。仓储使用注入查询，不提供 engine 或写方法；项目没有这些表的运行时采集器或消费者，`002_migrate_legacy_data.sql` 是唯一导入路径。三组 executable gate 会检查行数、映射后 distinct key 和采集日期范围，并纳入统一成功状态；仍应抽样比较板块、成分股和股票关系字段。对应旧表只能在全部 16 组 gate 成功且所有应用切换完成后随 `003` 删除；英文表之后保持仅导入的归档状态。

KDJ 与 5 分钟行情的正式写入和活跃策略读取已切换到 `kdj_indicators` 与 `intraday_bars_5m`。KDJ 迁移和新任务都按规范 `ts_code` 与日期生成稳定标识，4xxxxx/8xxxxx 代码统一映射为 `.BJ`；5 分钟行情迁移和新任务都按补齐后的六位代码、时间和复权标记重新生成相同标识，因此重复运行更新同一记录。旧 `task._2_分时数据获取_5分k` 仅投影历史列表字段，不再访问旧表，并同时接受历史 `stock=` 关键字与位置 `code` 参数。

在继续运行新的 5 分钟历史任务前，停止相关写入并执行 `005_normalize_intraday_minute_identity.sql`。该迁移在 SERIALIZABLE 事务中把 BaoStock 17 位时间和旧迁移的 12 位时间统一为 `YYYYMMDDHHMM`，通过临时表折叠同一证券、分钟和复权标记的重复行，并在源/归一化/目标计数全部通过后记录 `migration_validations` 与 `schema_migrations`；异常会回滚并记录失败。

在启用新的韭研采集和热门板块范围回补前执行 `006_create_jiuyan_collection_days.sql`。迁移只创建 manifest 表并记录版本，不会把旧 `jiuyan_actions` 日期自动声明为完整。新采集在同一 MySQL 事务中替换目标日 actions、写入来源计数与 SHA-256 指纹并核对持久化行数；只有该 manifest 能授权新的热门板块计算，Redis 标记不能替代。

应用代码切换已经完成：韭研、情绪、资金流向、策略选股、龙虎榜、研究策略和兼容脚本均不再读取旧表或旧 Redis 键，正式代码也不反向导入中文实现。该状态由 `tests/test_cutover_contracts.py` 强制检查。执行 `003_drop_legacy_schema.sql` 前仍必须停止应用、完成全库备份、确认 `001`/`002`/`004`、`004_legacy_containment_v1/succeeded` 和 16 条表级 gate，并完成人工抽样。数据库 guard 是必要条件，不替代这些步骤。
