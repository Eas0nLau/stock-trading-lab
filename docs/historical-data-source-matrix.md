# 历史数据源矩阵

本文只描述当前项目需要的历史数据、推荐来源和 AkShare 的适用范围。具体执行步骤见[历史数据回补操作手册](historical-data-backfill-runbook.md)。

## 判定说明

| 判定 | 含义 |
| --- | --- |
| 可直接使用 | AkShare 的字段语义和历史能力可以满足当前表的核心事实字段 |
| 部分可用 | 可以覆盖部分字段或有限历史，不能单独完成全量回补 |
| 不可使用 | AkShare 没有对应数据，或历史能力不足以支持当前业务 |
| 语义不一致 | 存在相似字段，但不能替代当前项目的原始业务定义 |

## 总体原则

- AkShare 是多个上游站点的 Python 适配层，不是独立数据权威。使用 AkShare 时仍然要按对应上游的历史深度、频率限制和稳定性验收。
- MySQL 是历史事实的系统记录。Redis 只保存当日缓存、日期索引和事件；Redis 丢失不应触发全量远程重抓。
- KDJ、市场宽度、指数情绪和热门板块情绪是派生数据，应从规范事实表本地重算，不从第三方下载同名结果。
- 上游失败必须保留失败状态并记录失败日期、证券或板块，不得写入零值、空记录或伪造交易日。
- 同一数据集必须固定字段语义、单位、复权方式和交易日口径。不能因为 AkShare 有同名字段就直接替换。

## 数据源决策矩阵

| 数据集 | 当前目标表/用途 | 当前来源与入口 | AkShare API | 判定 | 主要限制 | 推荐方案 |
| --- | --- | --- | --- | --- | --- | --- |
| 证券列表与基础信息 | `securities`，股票代码、名称、交易所和上市状态 | Tushare `stock_basic`，由 `collectors.update_securities()` 调用 | `stock_info_a_code_name`；`stock_individual_info_em`；`stock_profile_cninfo` | 部分可用 | `stock_info_a_code_name` 只有代码和名称；逐股接口无法一次复现项目的 `area`、`market`、`list_status` 等规范字段 | 保持当前 Tushare 规范；只有在明确字段映射和限速后才评估 AkShare 替代 |
| A 股日线行情和市值 | `daily_quotes` | Tushare `daily` 与 `daily_basic`；入口 `task._1_日k数据更新`、`task._7_市值信息每日更新` | `stock_zh_a_hist` | 部分可用 | AkShare 可提供 OHLCV，但不能直接保证 Tushare 市值、自由流通股本和项目全部字段同口径 | 保持当前 Tushare 规范；`total_mv`/`circ_mv` 单位万元，`free_share` 单位万股，空 enrichment 不覆盖 MySQL 非空事实 |
| 指数日线 | `index_daily` | `BaoStockSource.fetch_index_daily()` 调用 `sh.000001` 日频后写入 canonical 表；入口 `task._4_上证指数日k` | `stock_zh_index_daily_em`；`stock_zh_index_daily`；`stock_zh_index_daily_tx` | 可直接使用 | 不同上游的成交量、成交额和历史起始时间可能不同；必须统一日期和金额单位 | 当前使用 BaoStock 并以 20 日历天缓冲计算前收、振幅和涨跌额；切换前先做样本对照 |
| 交易日历 | `index_daily` 日期序列及任务交易日选择 | 当前项目从本地指数数据生成交易日序列 | `tool_trade_date_hist_sina` | 部分可用 | 文档数据可能滞后，不能未经检查作为未来年份唯一日历；当前日更依赖本地 `index_daily` | 以已落库 `index_daily.trade_date` 为运行日历；首次初始化后再用 AkShare 或其他来源校验缺口 |
| 5 分钟行情 | `intraday_bars_5m`，策略回测和盘中分析 | BaoStock `query_history_k_data_plus`，入口 `update_intraday_bars_5m()` | `stock_zh_a_hist_min_em`；`stock_zh_a_minute` | 部分可用 | AkShare 1 分钟历史通常只有最近数个交易日，其他周期历史深度受上游控制；不能保证完整年度回补 | 继续使用当前 BaoStock 入口，按证券和日期范围串行补数；AkShare 仅适合短窗口核验 |
| 行业、概念板块当前目录 | 资金流板块目录、当前板块选择 | 东方财富实时接口；历史资金流适配器中的板块目录 | `stock_board_industry_name_em`；`stock_board_concept_name_em`；`stock_sector_fund_flow_rank` | 可直接使用 | 目录和代码会变化；`stock_sector_fund_flow_rank` 是排行结果，不是稳定的历史目录快照 | 采集时保存板块代码和名称；回补任务应使用落库目录或同次请求得到的代码，不按名称长期猜测 |
| 当前板块成分股 | 板块展示和龙头辅助信息 | 东方财富板块接口 | `stock_board_industry_cons_em`；`stock_board_concept_cons_em` | 可直接使用 | 只表示当前成分股，没有可靠的历史 as-of 成分关系 | 只用于当前快照和辅助展示；历史回测不能把当前成分股倒灌到过去 |
| 历史行业/概念成分关系 | `ths_boards`、`ths_board_constituents`、`ths_stock_relations` 归档参考 | 同花顺归档导入 | `stock_industry_change_cninfo` 仅能提供部分行业变更 | 不可使用 | AkShare 没有同语义的历史概念成员关系；板块 `*_hist_em` 是指数行情，不是历史成分股 | 保留归档数据；需要历史成员关系时使用原始归档或重新设计带生效日期的数据源 |
| 行业/概念板块价格历史 | 板块走势分析 | 东方财富板块行情 | `stock_board_industry_hist_em`；`stock_board_concept_hist_em` | 可直接使用 | 板块代码、名称和分类会漂移；需要记录抓取时的代码和名称 | 仅在业务需要板块价格时使用；不要将其当作资金流历史 |
| 行业/概念板块资金流历史 | `fund_flow_snapshots`、`fund_flow_records` | 当前默认 `EastMoneyFundFlowSource` 直连 `push2his.eastmoney.com`；目标方案是 `AkShareFundFlowSource` | `stock_sector_fund_flow_hist`；`stock_concept_fund_flow_hist` | 部分可用 | AkShare 当前历史函数仍依赖东方财富旧历史接口；板块名称到代码映射可能变化；返回异常时可能没有 `data.klines`；历史深度由上游控制 | 按项目改造目标使用 AkShare，串行限速并记录失败；在改造完成前不要把现有直连 EastMoney 实现描述为 AkShare |
| 个股资金流历史 | 个股资金流研究 | 东方财富 | `stock_individual_fund_flow` | 部分可用 | 通常只返回近期有限交易日，不保证多年完整历史；资金流定义是东方财富口径 | 只用于近期研究或补充，不作为完整长期事实表的唯一来源 |
| 大盘资金流历史 | 市场级资金流研究 | 东方财富 | `stock_market_fund_flow` | 部分可用 | 历史深度受上游控制，字段与板块资金流不完全相同 | 需要时单独落库并保留来源字段；不能与板块或个股资金流混用 |
| `dde_net_amount` | `daily_quotes.dde_net_amount`，策略信号 | KPL/LonghuVIP `GetDaDanKLine2New`；入口 `task._10_开盘啦dde读取` | 个股主力资金流相关接口 | 语义不一致 | 主力净流入、大单净流入和 KPL DDE 是不同算法定义 | 保持 KPL DDE 元单位；全局请求间隔默认 0.5 秒、并发默认 4，只更新 MySQL，失败证券结构化返回 |
| 涨停池 | 热门板块情绪的辅助数据 | Jiuyan actions 和项目情绪任务 | `stock_zt_pool_em`；`stock_zt_pool_previous_em` 等 | 部分可用 | 主要支持近期日期；没有项目所需的完整长期编辑语义 | AkShare 只能做近期辅助校验；项目 `jiuyan_actions` 仍用 Jiuyan |
| Jiuyan 异动与涨停原因 | `jiuyan_actions`、热门板块情绪 | Jiuyan 页面和 `/jystock-app/api/v1/action/field`，入口 `collect_jiuyan_actions()` | 无对应 API | 不可使用 | AkShare 没有韭研公社编辑内容、`limit_up_reason` 和项目板块归类语义；可能触发滑块验证 | 保留 Jiuyan 浏览器/网络采集；严格校验返回日期匹配请求日期 |
| 龙虎榜明细 | `dragon_tiger` | 同花顺采集器，经 `/api/v1/dragon-tiger/collection-jobs` 启动 | `stock_lhb_detail_em`；`stock_lhb_stock_detail_em` | 语义不一致 | AkShare 东方财富龙虎榜字段和同花顺字段、业务键、营业部列不保证一致 | 继续使用当前同花顺规范；AkShare 只能作为对照或另建供应商字段 |
| 营业部与上榜历史 | `brokers`、`broker_listing_history` | 同花顺营业部目录和历史页面 | `stock_lhb_yyb_detail_em` | 部分可用 | 营业部 ID、分页深度和历史定义可能不同；Redis 页面缓存无 TTL 有陈旧风险 | 继续使用当前同花顺采集和稳定业务键；批量任务限制日期与营业部范围 |
| 财务报表和财务指标 | 当前策略的未来扩展 | 项目当前未纳入必需回补链 | `stock_financial_analysis_indicator_em`；`stock_balance_sheet_by_report_em`；利润表、现金流量表接口 | 可直接使用 | 字段量大、报告期和公告日语义不同；上游字段可能变化 | 新增规范表和字段映射后再接入，不作为当前历史回补的隐式步骤 |
| 融资融券 | 当前项目扩展数据 | 项目当前未纳入必需回补链 | `stock_margin_sse`；`stock_margin_detail_sse` 及深交所、北交所接口 | 可直接使用 | 按交易所和日期请求，批量回补必须限速和统一字段 | 明确交易所、单位和日期口径后独立落库 |
| 沪深港通资金流 | 当前项目扩展数据 | 项目当前未纳入必需回补链 | `stock_hsgt_hist_em` | 部分可用 | 上游披露字段和日期范围发生过变化，不能假定全时期同口径 | 作为独立数据集验证后使用，不并入普通资金流 |
| 沪深港通持股 | 当前项目扩展数据 | 项目当前未纳入必需回补链 | `stock_hsgt_hold_stock_em`；`stock_hsgt_stock_statistics_em`；`stock_hsgt_individual_em` | 部分可用 | 个股历史披露日期有限，近期统计和长期历史能力不同 | 先确定需要的统计粒度，再设计日期级缓存和补数范围 |
| IPO、新股 | 当前项目扩展数据 | 项目当前未纳入必需回补链 | `stock_xgsglb_em`；`stock_ipo_ths`；`stock_new_ipo_cninfo` | 可直接使用 | API 随 AkShare 版本变化，申购、上市、发行日期字段要分开 | 记录版本和字段映射；当前锁定版本缺失的 API 不得直接写入生产任务 |
| 分红、配股 | 当前项目扩展数据 | 项目当前未纳入必需回补链 | `stock_history_dividend`；`stock_history_dividend_detail` | 可直接使用 | 每 10 股单位、除权日期、占位日期需要归一化 | 独立落库并保留原始字段和标准化字段 |
| 筹码分布 | 当前项目扩展数据 | 项目当前未纳入必需回补链 | `stock_cyq_em` | 部分可用 | 通常只有最近约 90 个交易日，不适合长期策略回测 | 只用于近期分析，不作为长期历史补数源 |
| KDJ | `kdj_indicators` | 本地 `calculate_kdj()`，入口 `update_kdj_indicators()` | 无需下载同名结果 | 不可使用 | 第三方 KDJ 参数、复权口径和初始化方式可能不同 | 先完整回补 `daily_quotes`，再按 `period=9` 本地重算并 upsert |
| 市场宽度 | `index_market_breadth` | 本地 `run_index_emotion_job()` 及市场行情事实 | 无需下载同名结果 | 不可使用 | 需要项目自己的股票池、涨跌和涨停定义 | 从 `daily_quotes` 和项目规则本地计算 |
| 指数情绪周期 | `index_emotion_daily` | 本地情绪任务 | 无需下载同名结果 | 不可使用 | 是项目规则派生值，不是外部标准行情字段 | 先补齐指数、日线和市场宽度，再调用情绪任务 |
| 热门板块情绪 | `hot_board_emotion_daily` | 本地情绪任务，依赖 `jiuyan_actions` 和日线 | 无需下载同名结果 | 不可使用 | 依赖 Jiuyan 的前一交易日样本和项目规则 | 先补 Jiuyan、日线，再按日期重算 |

## 请求频率与稳定性

- **AkShare**：批量任务必须串行调用，普通请求建议至少间隔 1 秒；连接失败使用有限次数指数退避。AkShare 不屏蔽上游限制，东方财富、同花顺、交易所等上游的断连和限流仍会直接影响任务。
- **Tushare**：遵守 token 权限、积分和调用频率。当前 collector 遇到包含“频率”的异常时等待 65 秒后重试，并在日期间保持至少 1.3 秒间隔。
- **BaoStock**：当前 5 分钟任务按单只证券、单个日期范围执行一次登录、查询和注销，没有内置请求重试。批量操作应串行处理证券并保存失败清单。
- **Jiuyan**：当前实现使用全局请求时隙，默认随机间隔 60 至 105 秒，并最多尝试 2 次。出现滑块时需要人工验证，不能通过提高并发规避。
- **同花顺**：当前龙虎榜采集器默认对连接和超时错误尝试 3 次，使用 0.5 秒线性等待，但没有统一的批量请求间隔。长区间回补应缩小批次并监控封禁响应。
- **东方财富浏览器采集**：只用于盘中实时资金流和策略页面监听。浏览器带 Cookie 的会话可用，不代表 Python `requests` 历史接口可用；两条链路必须分别监控。

## 当前代码依据

- [市场数据 collector](../src/stock_lab/modules/market_data/collectors.py)
- [市值回补任务](../src/stock_lab/jobs/market_cap_backfill.py)
- [DDE 回补任务](../src/stock_lab/jobs/dde_backfill.py)
- [KPL DDE source](../src/stock_lab/infrastructure/market_data/kpl.py)
- [5 分钟行情任务](../src/stock_lab/jobs/intraday_bars_5m.py)
- [KDJ 重算任务](../src/stock_lab/jobs/kdj_indicators.py)
- [资金流历史任务](../src/stock_lab/jobs/fund_flow_backfill.py)
- [Jiuyan 采集器](../src/stock_lab/modules/market_data/jiuyan.py)
- [龙虎榜采集器](../src/stock_lab/infrastructure/market_data/dragon_tiger.py)
- [情绪任务](../src/stock_lab/modules/emotion/jobs.py)

## 版本与官方参考

项目当前锁定 `akshare==1.17.54`。官方在线文档当前显示为 `1.18.83`，两者不能直接视为行为完全相同；新增 API、字段和上游修复必须先在隔离环境验证，再更新项目锁定版本。

- [AKShare 股票数据文档](https://akshare.akfamily.xyz/data/stock/stock.html)
- [AKShare 指数数据文档](https://akshare.akfamily.xyz/data/index/index.html)
- [AKShare 工具数据文档](https://akshare.akfamily.xyz/data/tool/tool.html)
- [AKShare 1.17.54 源码](https://github.com/akfamily/akshare/tree/release-v1.17.54)
- [AKShare 1.18.83 源码](https://github.com/akfamily/akshare/tree/release-v1.18.83)

## 当前结论

AkShare 适合逐步接入指数、标准日线、当前板块目录、财务、交易所统计、IPO 和分红等数据；不适合未经语义和历史深度验证就统一替换当前项目的 Tushare、BaoStock、Jiuyan、同花顺或 DDE 数据。尤其是板块资金流历史，AkShare 的函数存在，但其上游稳定性和历史完整性必须在每次回补时单独验证。
