# 数据库重建与迁移

## 原则

新版 schema 的表、列、索引和约束全部使用英文。迁移不直接覆盖旧表：先创建新表，再显式复制数据、校验、切换应用，最后由单独脚本删除旧表。

## 执行顺序

1. 停止写入任务和 Web 服务。
2. 使用 `mysqldump` 完整备份数据库。
3. 执行 `db/migrations/001_create_english_schema.sql`。
4. 执行 `db/migrations/002_migrate_legacy_data.sql`。
5. 比较新旧表行数、主键数量、日期范围和关键金额汇总。
6. 切换对应模块 repository、API 和前端。
7. 运行完整测试和人工数据抽样。
8. 所有模块完成后，单独审批并执行 `003_drop_legacy_schema.sql`。

## 回滚

应用切换前，删除未投入使用的新表即可回滚。应用切换后，停止服务并恢复迁移前完整备份。旧表删除脚本不属于初始化或自动升级流程，禁止在无备份情况下执行。

## 验证项

- 每张表迁移前后行数一致，去重策略导致的差异必须有记录。
- 主键和唯一键不存在重复。
- 最早、最晚交易日期一致。
- 关键金额、成交量和样本数聚合值一致。
- JSON 字段可以由 MySQL 解析。
- 新 schema 中不存在非 ASCII 标识符。

## 当前切换状态

`index_daily`、`securities`、`daily_quotes`、`intraday_bars_5m`、`kdj_indicators`、`index_market_breadth`、`index_emotion_daily` 和 `hot_board_emotion_daily` 已接入正式 repository、任务或新版 API。`jiuyan_actions` 已被新版情绪 job 读取，但采集任务仍需完成写入切换。

市场数据的正式访问边界是 `stock_lab.modules.market_data`。Repository 只返回英文规范列：
`securities.ts_code`、`securities.symbol`、`daily_quotes.ts_code`、
`daily_quotes.trade_date`、`daily_quotes.open_price`、`daily_quotes.close_price` 和
`index_daily.trade_date` 等。代码值按字符串处理，补齐股票代码的前导零并保留交易所后缀。
共享旧工具仅在适配器边界恢复 `open`、`close`、`pre_close` 等历史键；这不改变存量数据库迁移的备份、校验和回滚要求。

龙虎榜和营业部的正式访问边界是 `stock_lab.modules.dragon_tiger`。采集、分析和活跃策略查询已切换到 `dragon_tiger`、`broker_listing_history`、`broker_top_stats`、`brokers` 和 `daily_quotes`；旧中文路径只保留无导入副作用的执行适配器，因此龙虎榜相关代码不再阻塞旧表删除。

同花顺的 `ths_boards`、`ths_board_constituents` 和 `ths_stock_relations` 是归档参考数据，正式访问边界是只读的 `stock_lab.modules.ths`。仓储使用注入查询，不提供 engine 或写方法；项目没有这些表的运行时采集器或消费者，`002_migrate_legacy_data.sql` 是唯一导入路径。执行该脚本后必须检查三组验证结果的 `legacy_rows` 与 `new_rows`，并抽样比较板块、成分股和股票关系字段。三组数据均确认一致后，对应三张旧同花顺表可以随 `003_drop_legacy_schema.sql` 删除；英文表之后仍保持仅导入的归档状态。

KDJ 与 5 分钟行情的正式写入和活跃策略读取已切换到 `kdj_indicators` 与 `intraday_bars_5m`。KDJ 迁移和新任务都按规范 `ts_code` 与日期生成稳定标识，4xxxxx/8xxxxx 代码统一映射为 `.BJ`；5 分钟行情迁移和新任务都按补齐后的六位代码、时间和复权标记重新生成相同标识，因此重复运行更新同一记录。旧 `task._2_分时数据获取_5分k` 仅投影历史列表字段，不再访问旧表，并同时接受历史 `stock=` 关键字与位置 `code` 参数。

同花顺运行时代码已无旧表引用，不再单独阻塞旧同花顺表删除，但删除前仍必须完成上述迁移一致性检查。韭研采集、实时监控和其他研究脚本的旧表切换尚未全部完成，因此仍禁止整体执行 `003_drop_legacy_schema.sql`。
