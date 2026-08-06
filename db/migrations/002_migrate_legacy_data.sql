SET NAMES utf8mb4;

INSERT INTO `index_daily` (`trade_date`, `open_price`, `close_price`, `high_price`, `low_price`, `volume`, `turnover`, `amplitude_pct`, `change_pct`, `change_amount`, `turnover_rate`)
SELECT `日期`, `开盘`, `收盘`, `最高`, `最低`, `成交量`, `成交额`, `振幅`, `涨跌幅`, `涨跌额`, `换手率`
FROM `akshare_sh000001`
ON DUPLICATE KEY UPDATE `close_price`=VALUES(`close_price`), `volume`=VALUES(`volume`), `turnover`=VALUES(`turnover`);

INSERT INTO `index_market_breadth` (`trade_date`, `stock_count`, `advancing_count`, `declining_count`, `advance_over_5_count`, `decline_over_5_count`, `limit_up_count`, `limit_down_count`, `market_turnover`, `average_change_pct`, `created_at`, `updated_at`)
SELECT `日期`, `股票总数`, `上涨家数`, `下跌家数`, `涨超5家数`, `跌超5家数`, `涨停家数`, `跌停家数`, `成交额`, `平均涨跌幅`, `创建时间`, `更新时间`
FROM `t_指数情绪周期_市场宽度`
ON DUPLICATE KEY UPDATE `stock_count`=VALUES(`stock_count`), `updated_at`=VALUES(`updated_at`);

INSERT INTO `index_emotion_daily` (`trade_date`, `index_name`, `cycle_state`, `cycle_score`, `summary`, `open_price`, `close_price`, `high_price`, `low_price`, `change_pct`, `index_turnover`, `index_turnover_ratio`, `market_turnover_ratio`, `ma5`, `ma10`, `ma20`, `ma60`, `ma5_slope`, `ma10_slope`, `ma20_slope`, `trend_score`, `breadth_score`, `limit_structure_score`, `volume_score`, `risk_appetite_score`, `market_breadth_json`, `signals_json`, `recent_trend_json`, `volatility_chart_json`, `full_result_json`, `created_at`, `updated_at`)
SELECT `日期`, `指数名称`, `周期状态`, `周期分数`, `摘要`, `开盘`, `收盘`, `最高`, `最低`, `涨跌幅`, `指数成交额`, `指数成交额比例`, `市场成交额比例`, `MA5`, `MA10`, `MA20`, `MA60`, `MA5斜率`, `MA10斜率`, `MA20斜率`, `趋势得分`, `市场宽度得分`, `涨跌停结构得分`, `量能得分`, `风险偏好得分`, `市场宽度JSON`, `信号JSON`, `最近走势JSON`, `波动图JSON`, `完整结果JSON`, `创建时间`, `更新时间`
FROM `t_指数情绪周期_每日分析`
ON DUPLICATE KEY UPDATE `cycle_state`=VALUES(`cycle_state`), `cycle_score`=VALUES(`cycle_score`), `updated_at`=VALUES(`updated_at`);

INSERT INTO `hot_board_emotion_daily` (`trade_date`, `board_name`, `sample_trade_date`, `previous_list_complete`, `current_list_complete`, `previous_board_count`, `previous_stock_pool_count`, `previous_detail_coverage`, `current_board_count`, `current_stock_detail_count`, `valid_sample_count`, `quote_coverage`, `average_change_pct`, `median_change_pct`, `average_amplitude_pct`, `change_stddev`, `promotion_count`, `promotion_rate`, `new_promotion_count`, `new_promotion_rate`, `positive_count`, `positive_rate`, `large_gain_count`, `large_gain_rate`, `large_loss_count`, `large_loss_rate`, `failed_limit_count`, `failed_limit_rate`, `retained_count`, `retained_rate`, `heat_stage`, `continuation_state`, `overall_status`, `emotion_score`, `decision_summary`, `decision_reasons_json`, `created_at`, `updated_at`)
SELECT `日期`, `板块`, `样本来源日期`, `前日榜单数据完整`, `当日榜单数据完整`, `前日板块数量`, `前日股票池数量`, `前日明细覆盖率`, `当日板块数量`, `当日股票明细数量`, `有效样本数`, `行情覆盖率`, `平均涨跌幅`, `中位数涨跌幅`, `平均振幅`, `涨幅标准差`, `晋级家数`, `晋级率`, `新晋级家数`, `新晋级率`, `红盘家数`, `红盘率`, `大涨家数`, `大涨率`, `大跌家数`, `大跌率`, `炸板家数`, `炸板率`, `同板块留存家数`, `同板块留存率`, `热度阶段`, `承接情绪`, `综合状态`, `情绪分`, `判定摘要`, `判定依据JSON`, `创建时间`, `更新时间`
FROM `t_热门板块情绪_每日分析`
ON DUPLICATE KEY UPDATE `overall_status`=VALUES(`overall_status`), `emotion_score`=VALUES(`emotion_score`), `updated_at`=VALUES(`updated_at`);

INSERT INTO `securities` (`ts_code`, `symbol`, `name`, `area`, `industry`, `market`, `list_date`, `list_status`)
SELECT CAST(`ts_code` AS CHAR), LPAD(CAST(`symbol` AS CHAR), 6, '0'), `name`, `area`, `industry`, `market`, CAST(`list_date` AS UNSIGNED), `list_status`
FROM `stock_basic`
WHERE `ts_code` IS NOT NULL AND `symbol` IS NOT NULL AND `name` IS NOT NULL
ON DUPLICATE KEY UPDATE `name`=VALUES(`name`), `industry`=VALUES(`industry`), `market`=VALUES(`market`), `list_status`=VALUES(`list_status`);

INSERT INTO `daily_quotes` (`data_id`, `ts_code`, `trade_date`, `open_price`, `high_price`, `low_price`, `close_price`, `previous_close`, `change_amount`, `change_pct`, `volume`, `turnover`, `total_market_value`, `circulating_market_value`, `free_float_shares`, `free_float_market_value`, `stock_name`, `dde_net_amount`)
SELECT `data_id`, CAST(`ts_code` AS CHAR), `trade_date`, `open`, `high`, `low`, `close`, `pre_close`, `change`, `pct_chg`, `vol`, `amount`, `total_mv`, `circ_mv`, `free_share`, `free_mv`, `stock_name`, `dde`
FROM `stock_daily`
ON DUPLICATE KEY UPDATE `close_price`=VALUES(`close_price`), `volume`=VALUES(`volume`), `turnover`=VALUES(`turnover`), `dde_net_amount`=VALUES(`dde_net_amount`);

INSERT INTO `kdj_indicators` (`data_id`, `ts_code`, `trade_date`, `k_value`, `d_value`, `j_value`)
SELECT `data_id`, CAST(`ts_code` AS CHAR), `trade_date`, `k`, `d`, `j`
FROM `stock_kdj`
ON DUPLICATE KEY UPDATE `k_value`=VALUES(`k_value`), `d_value`=VALUES(`d_value`), `j_value`=VALUES(`j_value`);

INSERT INTO `intraday_bars_5m` (`data_id`, `trade_date`, `trade_time`, `stock_code`, `open_price`, `high_price`, `low_price`, `close_price`, `volume`, `turnover`, `adjustment_flag`)
SELECT `data_id`, `date`, `time`, LPAD(CAST(`code` AS CHAR), 6, '0'), `open`, `high`, `low`, `close`, `volume`, `amount`, `adjustflag`
FROM `t_stock_5_min_k`
ON DUPLICATE KEY UPDATE `close_price`=VALUES(`close_price`), `volume`=VALUES(`volume`), `turnover`=VALUES(`turnover`);

INSERT INTO `jiuyan_actions` (`data_id`, `trade_date`, `board_name`, `board_stock_count`, `stock_code`, `stock_name`, `source_code`, `limit_up_at`, `board_streak`, `change_pct`, `limit_up_reason`)
SELECT `data_id`, `date`, `板块`, `板块个股数量`, LPAD(CAST(`股票代码` AS CHAR), 6, '0'), `股票名称`, `code`, `涨停时间`, `几天几板`, `涨幅`, `涨停解析`
FROM `t_韭研公社异动解析`
ON DUPLICATE KEY UPDATE `board_name`=VALUES(`board_name`), `change_pct`=VALUES(`change_pct`), `limit_up_reason`=VALUES(`limit_up_reason`);

INSERT INTO `dragon_tiger` (`data_id`, `trade_date`, `source_id`, `detail_type`, `date_type`, `stock_code`, `stock_name`, `current_price`, `change_pct`, `turnover`, `net_buy_amount`, `total_buy_amount`, `total_sell_amount`, `buy_1_broker_id`, `buy_1_broker_name`, `buy_1_buy_amount`, `buy_1_sell_amount`, `buy_1_net_amount`, `buy_2_broker_id`, `buy_2_broker_name`, `buy_2_buy_amount`, `buy_2_sell_amount`, `buy_2_net_amount`, `buy_3_broker_id`, `buy_3_broker_name`, `buy_3_buy_amount`, `buy_3_sell_amount`, `buy_3_net_amount`, `buy_4_broker_id`, `buy_4_broker_name`, `buy_4_buy_amount`, `buy_4_sell_amount`, `buy_4_net_amount`, `buy_5_broker_id`, `buy_5_broker_name`, `buy_5_buy_amount`, `buy_5_sell_amount`, `buy_5_net_amount`, `sell_1_broker_id`, `sell_1_broker_name`, `sell_1_buy_amount`, `sell_1_sell_amount`, `sell_1_net_amount`, `sell_2_broker_id`, `sell_2_broker_name`, `sell_2_buy_amount`, `sell_2_sell_amount`, `sell_2_net_amount`, `sell_3_broker_id`, `sell_3_broker_name`, `sell_3_buy_amount`, `sell_3_sell_amount`, `sell_3_net_amount`, `sell_4_broker_id`, `sell_4_broker_name`, `sell_4_buy_amount`, `sell_4_sell_amount`, `sell_4_net_amount`, `sell_5_broker_id`, `sell_5_broker_name`, `sell_5_buy_amount`, `sell_5_sell_amount`, `sell_5_net_amount`)
SELECT `data_id`, `date`, `rid`, `明细`, `日期类型`, `股票代码`, `股票名称`, `现价`, `涨跌幅`, `成交金额`, `净买入额`, `合计买入`, `合计卖出`, `买1营业部id`, `买1营业部`, `买1买入额`, `买1卖出额`, `买1净额`, `买2营业部id`, `买2营业部`, `买2买入额`, `买2卖出额`, `买2净额`, `买3营业部id`, `买3营业部`, `买3买入额`, `买3卖出额`, `买3净额`, `买4营业部id`, `买4营业部`, `买4买入额`, `买4卖出额`, `买4净额`, `买5营业部id`, `买5营业部`, `买5买入额`, `买5卖出额`, `买5净额`, `卖1营业部id`, `卖1营业部`, `卖1买入额`, `卖1卖出额`, `卖1净额`, `卖2营业部id`, `卖2营业部`, `卖2买入额`, `卖2卖出额`, `卖2净额`, `卖3营业部id`, `卖3营业部`, `卖3买入额`, `卖3卖出额`, `卖3净额`, `卖4营业部id`, `卖4营业部`, `卖4买入额`, `卖4卖出额`, `卖4净额`, `卖5营业部id`, `卖5营业部`, `卖5买入额`, `卖5卖出额`, `卖5净额`
FROM `t_龙虎榜`
ON DUPLICATE KEY UPDATE `current_price`=VALUES(`current_price`), `change_pct`=VALUES(`change_pct`), `net_buy_amount`=VALUES(`net_buy_amount`);

INSERT INTO `broker_listing_history` (`data_id`, `broker_id`, `broker_name`, `trade_date`, `stock_name`, `stock_code`, `listing_reason`, `change_pct`, `buy_amount`, `sell_amount`, `net_amount`, `board_name`)
SELECT `data_id`, `营业部id`, `营业部名称`, `日期`, `股票简称`, `股票代码`, `上榜原因`, `涨跌幅`, `买入额`, `卖出额`, `买卖净额`, `所属板块`
FROM `t_龙虎榜_营业部_上榜历史数据`
ON DUPLICATE KEY UPDATE `broker_name`=VALUES(`broker_name`), `net_amount`=VALUES(`net_amount`);

INSERT INTO `broker_top_stats` (`broker_id`, `broker_name`, `listing_count`, `total_capital_used`, `year_listing_count`, `year_stock_count`, `three_day_follow_success_rate`)
SELECT CAST(`营业部id` AS CHAR), `营业部名称`, CAST(`上榜次数` AS UNSIGNED), CAST(`合计动用资金` AS DECIMAL(20,2)), CAST(`年内上榜次数` AS UNSIGNED), CAST(`年内买入股票只数` AS UNSIGNED), CAST(REPLACE(`年内3日跟买成功率`, '%', '') AS DECIMAL(10,4))
FROM `t_龙虎榜_营业部_上榜次数最多`
WHERE `营业部id` IS NOT NULL
ON DUPLICATE KEY UPDATE `broker_name`=VALUES(`broker_name`), `listing_count`=VALUES(`listing_count`), `three_day_follow_success_rate`=VALUES(`three_day_follow_success_rate`);

INSERT INTO `brokers` (`broker_id`, `broker_name`)
SELECT `营业部id`, `营业部名称`
FROM `t_龙虎榜_营业部_全部`
ON DUPLICATE KEY UPDATE `broker_name`=VALUES(`broker_name`);

INSERT INTO `ths_boards` (`board_code`, `board_type`, `board_name`, `page_code`, `detail_path`, `collected_date`, `updated_at`)
SELECT `板块代码`, `板块类型`, `板块名称`, `页面代码`, `详情路径`, `采集日期`, `更新时间`
FROM `t_同花顺板块列表`
ON DUPLICATE KEY UPDATE `board_name`=VALUES(`board_name`), `collected_date`=VALUES(`collected_date`), `updated_at`=VALUES(`updated_at`);

INSERT INTO `ths_board_constituents` (`board_code`, `stock_code`, `board_type`, `board_name`, `page_code`, `stock_name`, `collected_date`, `updated_at`)
SELECT `板块代码`, `股票代码`, `板块类型`, `板块名称`, `页面代码`, `股票名称`, `采集日期`, `更新时间`
FROM `t_同花顺板块成分股`
ON DUPLICATE KEY UPDATE `stock_name`=VALUES(`stock_name`), `collected_date`=VALUES(`collected_date`), `updated_at`=VALUES(`updated_at`);

INSERT INTO `ths_stock_relations` (`stock_code`, `stock_name`, `industry_names`, `industry_codes`, `concept_names`, `concept_codes`, `collected_date`, `updated_at`)
SELECT `股票代码`, `股票名称`, `同花顺行业`, `同花顺行业代码`, `同花顺概念`, `同花顺概念代码`, `采集日期`, `更新时间`
FROM `t_同花顺股票板块概念对应关系`
ON DUPLICATE KEY UPDATE `stock_name`=VALUES(`stock_name`), `industry_names`=VALUES(`industry_names`), `concept_names`=VALUES(`concept_names`), `updated_at`=VALUES(`updated_at`);

INSERT INTO `schema_migrations` (`version`) VALUES ('002_migrate_legacy_data')
ON DUPLICATE KEY UPDATE `applied_at`=`applied_at`;

-- Run these checks before application cutover.
SELECT 'index_daily' AS `table_name`, (SELECT COUNT(*) FROM `akshare_sh000001`) AS `legacy_rows`, (SELECT COUNT(*) FROM `index_daily`) AS `new_rows`;
SELECT 'securities' AS `table_name`, (SELECT COUNT(*) FROM `stock_basic`) AS `legacy_rows`, (SELECT COUNT(*) FROM `securities`) AS `new_rows`;
SELECT 'daily_quotes' AS `table_name`, (SELECT COUNT(*) FROM `stock_daily`) AS `legacy_rows`, (SELECT COUNT(*) FROM `daily_quotes`) AS `new_rows`;
SELECT 'dragon_tiger' AS `table_name`, (SELECT COUNT(*) FROM `t_龙虎榜`) AS `legacy_rows`, (SELECT COUNT(*) FROM `dragon_tiger`) AS `new_rows`;
