SET NAMES utf8mb4;

DROP PROCEDURE IF EXISTS guard_migration_002;
DROP PROCEDURE IF EXISTS preflight_legacy_data;
DROP PROCEDURE IF EXISTS assert_mapping_parity;

DELIMITER $$
CREATE PROCEDURE guard_migration_002()
BEGIN
  DECLARE v_count int DEFAULT 0;
  SELECT COUNT(*) INTO v_count
  FROM `schema_migrations`
  WHERE `version` = '001_create_english_schema';
  IF v_count <> 1 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Migration 002 requires successful migration 001';
  END IF;
END$$

CREATE PROCEDURE preflight_legacy_data()
BEGIN
  DECLARE v_source_table varchar(64) DEFAULT NULL;
  DECLARE v_source_column varchar(64) DEFAULT NULL;
  DECLARE v_source_key varchar(255) DEFAULT NULL;
  DECLARE v_message varchar(128);

  SELECT invalid.source_table, invalid.source_column, invalid.source_key
  INTO v_source_table, v_source_column, v_source_key
  FROM (
    SELECT 't_指数情绪周期_每日分析' AS source_table, '市场宽度JSON' AS source_column, CAST(`日期` AS CHAR) AS source_key
    FROM `t_指数情绪周期_每日分析`
    WHERE `市场宽度JSON` IS NOT NULL AND JSON_VALID(CAST(`市场宽度JSON` AS CHAR)) = 0
    UNION ALL
    SELECT 't_指数情绪周期_每日分析', '信号JSON', CAST(`日期` AS CHAR)
    FROM `t_指数情绪周期_每日分析`
    WHERE `信号JSON` IS NOT NULL AND JSON_VALID(CAST(`信号JSON` AS CHAR)) = 0
    UNION ALL
    SELECT 't_指数情绪周期_每日分析', '最近走势JSON', CAST(`日期` AS CHAR)
    FROM `t_指数情绪周期_每日分析`
    WHERE `最近走势JSON` IS NOT NULL AND JSON_VALID(CAST(`最近走势JSON` AS CHAR)) = 0
    UNION ALL
    SELECT 't_指数情绪周期_每日分析', '波动图JSON', CAST(`日期` AS CHAR)
    FROM `t_指数情绪周期_每日分析`
    WHERE `波动图JSON` IS NOT NULL AND JSON_VALID(CAST(`波动图JSON` AS CHAR)) = 0
    UNION ALL
    SELECT 't_指数情绪周期_每日分析', '完整结果JSON', CAST(`日期` AS CHAR)
    FROM `t_指数情绪周期_每日分析`
    WHERE `完整结果JSON` IS NOT NULL AND JSON_VALID(CAST(`完整结果JSON` AS CHAR)) = 0
    UNION ALL
    SELECT 't_热门板块情绪_每日分析', '判定依据JSON', CONCAT(CAST(`日期` AS CHAR), '/', `板块`)
    FROM `t_热门板块情绪_每日分析`
    WHERE `判定依据JSON` IS NOT NULL AND JSON_VALID(CAST(`判定依据JSON` AS CHAR)) = 0
  ) AS invalid
  LIMIT 1;

  IF v_source_table IS NOT NULL THEN
    SET v_message = LEFT(CONCAT(
      'Invalid legacy JSON: ', v_source_table, '.', v_source_column,
      ' key=', COALESCE(v_source_key, '<NULL>')
    ), 128);
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = v_message;
  END IF;

  SET v_source_table = NULL;
  SET v_source_column = NULL;
  SET v_source_key = NULL;

  SELECT invalid.source_table, invalid.source_column, invalid.source_key
  INTO v_source_table, v_source_column, v_source_key
  FROM (
    SELECT 't_龙虎榜_营业部_上榜次数最多' AS source_table, '上榜次数' AS source_column, CAST(`营业部id` AS CHAR) AS source_key
    FROM `t_龙虎榜_营业部_上榜次数最多`
    WHERE NULLIF(TRIM(CAST(`上榜次数` AS CHAR)), '') IS NOT NULL
      AND NOT REGEXP_LIKE(TRIM(CAST(`上榜次数` AS CHAR)), '^([0-9]+|[0-9]{1,3}(,[0-9]{3})+)(次|家|只)?$')
    UNION ALL
    SELECT 't_龙虎榜_营业部_上榜次数最多', '年内上榜次数', CAST(`营业部id` AS CHAR)
    FROM `t_龙虎榜_营业部_上榜次数最多`
    WHERE NULLIF(TRIM(CAST(`年内上榜次数` AS CHAR)), '') IS NOT NULL
      AND NOT REGEXP_LIKE(TRIM(CAST(`年内上榜次数` AS CHAR)), '^([0-9]+|[0-9]{1,3}(,[0-9]{3})+)(次|家|只)?$')
    UNION ALL
    SELECT 't_龙虎榜_营业部_上榜次数最多', '年内买入股票只数', CAST(`营业部id` AS CHAR)
    FROM `t_龙虎榜_营业部_上榜次数最多`
    WHERE NULLIF(TRIM(CAST(`年内买入股票只数` AS CHAR)), '') IS NOT NULL
      AND NOT REGEXP_LIKE(TRIM(CAST(`年内买入股票只数` AS CHAR)), '^([0-9]+|[0-9]{1,3}(,[0-9]{3})+)(次|家|只)?$')
    UNION ALL
    SELECT 't_龙虎榜_营业部_上榜次数最多', '合计动用资金', CAST(`营业部id` AS CHAR)
    FROM `t_龙虎榜_营业部_上榜次数最多`
    WHERE NULLIF(TRIM(CAST(`合计动用资金` AS CHAR)), '') IS NOT NULL
      AND NOT REGEXP_LIKE(TRIM(CAST(`合计动用资金` AS CHAR)), '^[+-]?([0-9]+|[0-9]{1,3}(,[0-9]{3})+)([.][0-9]+)?(元|万|万元|亿|亿元)?$')
    UNION ALL
    SELECT 't_龙虎榜_营业部_上榜次数最多', '年内3日跟买成功率', CAST(`营业部id` AS CHAR)
    FROM `t_龙虎榜_营业部_上榜次数最多`
    WHERE NULLIF(TRIM(CAST(`年内3日跟买成功率` AS CHAR)), '') IS NOT NULL
      AND NOT REGEXP_LIKE(TRIM(CAST(`年内3日跟买成功率` AS CHAR)), '^[+-]?([0-9]+|[0-9]{1,3}(,[0-9]{3})+)([.][0-9]+)?%?$')
  ) AS invalid
  LIMIT 1;

  IF v_source_table IS NOT NULL THEN
    SET v_message = LEFT(CONCAT(
      'Invalid broker statistic: ', v_source_table, '.', v_source_column,
      ' key=', COALESCE(v_source_key, '<NULL>')
    ), 128);
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = v_message;
  END IF;
END$$

CREATE PROCEDURE assert_mapping_parity(
  IN p_mapping varchar(64),
  IN p_source_rows bigint,
  IN p_target_rows bigint,
  IN p_source_keys bigint,
  IN p_target_keys bigint,
  IN p_source_min_date bigint,
  IN p_target_min_date bigint,
  IN p_source_max_date bigint,
  IN p_target_max_date bigint,
  IN p_source_aggregate longtext,
  IN p_target_aggregate longtext,
  IN p_target_invalid_json bigint
)
BEGIN
  DECLARE v_message varchar(128);

  IF p_source_rows <> p_target_rows THEN
    SET v_message = CONCAT('Row parity failed for ', p_mapping, ': ', p_source_rows, ' != ', p_target_rows);
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = v_message;
  END IF;
  IF p_source_keys <> p_target_keys OR p_source_rows <> p_source_keys THEN
    SET v_message = CONCAT('Distinct-key parity failed for ', p_mapping);
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = v_message;
  END IF;
  IF NOT (p_source_min_date <=> p_target_min_date) OR NOT (p_source_max_date <=> p_target_max_date) THEN
    SET v_message = CONCAT('Date-range parity failed for ', p_mapping);
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = v_message;
  END IF;
  IF NOT (p_source_aggregate <=> p_target_aggregate) THEN
    SET v_message = CONCAT('Aggregate parity failed for ', p_mapping);
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = v_message;
  END IF;
  IF p_target_invalid_json IS NOT NULL AND p_target_invalid_json <> 0 THEN
    SET v_message = CONCAT('Target JSON validation failed for ', p_mapping);
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = v_message;
  END IF;

  SELECT
    p_mapping AS `mapping`,
    p_source_rows AS `source_rows`,
    p_target_rows AS `target_rows`,
    p_source_keys AS `source_distinct_keys`,
    p_target_keys AS `target_distinct_keys`,
    p_source_min_date AS `source_min_date`,
    p_target_min_date AS `target_min_date`,
    p_source_max_date AS `source_max_date`,
    p_target_max_date AS `target_max_date`,
    p_source_aggregate AS `source_aggregate`,
    p_target_aggregate AS `target_aggregate`,
    p_target_invalid_json AS `target_invalid_json`;
END$$
DELIMITER ;

CALL guard_migration_002();
DELETE FROM `migration_validations` WHERE `validation_version` = '002_parity_v1';
DELETE FROM `schema_migrations` WHERE `version` = '002_migrate_legacy_data';
CALL preflight_legacy_data();

INSERT INTO `index_daily` (`trade_date`, `open_price`, `close_price`, `high_price`, `low_price`, `volume`, `turnover`, `amplitude_pct`, `change_pct`, `change_amount`, `turnover_rate`)
SELECT `日期`, `开盘`, `收盘`, `最高`, `最低`, `成交量`, `成交额`, `振幅`, `涨跌幅`, `涨跌额`, `换手率`
FROM `akshare_sh000001`
ON DUPLICATE KEY UPDATE `open_price`=VALUES(`open_price`), `close_price`=VALUES(`close_price`), `high_price`=VALUES(`high_price`), `low_price`=VALUES(`low_price`), `volume`=VALUES(`volume`), `turnover`=VALUES(`turnover`), `amplitude_pct`=VALUES(`amplitude_pct`), `change_pct`=VALUES(`change_pct`), `change_amount`=VALUES(`change_amount`), `turnover_rate`=VALUES(`turnover_rate`);

INSERT INTO `index_market_breadth` (`trade_date`, `stock_count`, `advancing_count`, `declining_count`, `advance_over_5_count`, `decline_over_5_count`, `limit_up_count`, `limit_down_count`, `market_turnover`, `average_change_pct`, `created_at`, `updated_at`)
SELECT `日期`, `股票总数`, `上涨家数`, `下跌家数`, `涨超5家数`, `跌超5家数`, `涨停家数`, `跌停家数`, `成交额`, `平均涨跌幅`, `创建时间`, `更新时间`
FROM `t_指数情绪周期_市场宽度`
ON DUPLICATE KEY UPDATE `stock_count`=VALUES(`stock_count`), `advancing_count`=VALUES(`advancing_count`), `declining_count`=VALUES(`declining_count`), `advance_over_5_count`=VALUES(`advance_over_5_count`), `decline_over_5_count`=VALUES(`decline_over_5_count`), `limit_up_count`=VALUES(`limit_up_count`), `limit_down_count`=VALUES(`limit_down_count`), `market_turnover`=VALUES(`market_turnover`), `average_change_pct`=VALUES(`average_change_pct`), `created_at`=VALUES(`created_at`), `updated_at`=VALUES(`updated_at`);

INSERT INTO `index_emotion_daily` (`trade_date`, `index_name`, `cycle_state`, `cycle_score`, `summary`, `open_price`, `close_price`, `high_price`, `low_price`, `change_pct`, `index_turnover`, `index_turnover_ratio`, `market_turnover_ratio`, `ma5`, `ma10`, `ma20`, `ma60`, `ma5_slope`, `ma10_slope`, `ma20_slope`, `trend_score`, `breadth_score`, `limit_structure_score`, `volume_score`, `risk_appetite_score`, `market_breadth_json`, `signals_json`, `recent_trend_json`, `volatility_chart_json`, `full_result_json`, `created_at`, `updated_at`)
SELECT `日期`, `指数名称`, `周期状态`, `周期分数`, `摘要`, `开盘`, `收盘`, `最高`, `最低`, `涨跌幅`, `指数成交额`, `指数成交额比例`, `市场成交额比例`, `MA5`, `MA10`, `MA20`, `MA60`, `MA5斜率`, `MA10斜率`, `MA20斜率`, `趋势得分`, `市场宽度得分`, `涨跌停结构得分`, `量能得分`, `风险偏好得分`, CASE WHEN `市场宽度JSON` IS NULL THEN NULL ELSE CAST(`市场宽度JSON` AS JSON) END, CASE WHEN `信号JSON` IS NULL THEN NULL ELSE CAST(`信号JSON` AS JSON) END, CASE WHEN `最近走势JSON` IS NULL THEN NULL ELSE CAST(`最近走势JSON` AS JSON) END, CASE WHEN `波动图JSON` IS NULL THEN NULL ELSE CAST(`波动图JSON` AS JSON) END, CASE WHEN `完整结果JSON` IS NULL THEN NULL ELSE CAST(`完整结果JSON` AS JSON) END, `创建时间`, `更新时间`
FROM `t_指数情绪周期_每日分析`
ON DUPLICATE KEY UPDATE `index_name`=VALUES(`index_name`), `cycle_state`=VALUES(`cycle_state`), `cycle_score`=VALUES(`cycle_score`), `summary`=VALUES(`summary`), `open_price`=VALUES(`open_price`), `close_price`=VALUES(`close_price`), `high_price`=VALUES(`high_price`), `low_price`=VALUES(`low_price`), `change_pct`=VALUES(`change_pct`), `index_turnover`=VALUES(`index_turnover`), `index_turnover_ratio`=VALUES(`index_turnover_ratio`), `market_turnover_ratio`=VALUES(`market_turnover_ratio`), `ma5`=VALUES(`ma5`), `ma10`=VALUES(`ma10`), `ma20`=VALUES(`ma20`), `ma60`=VALUES(`ma60`), `ma5_slope`=VALUES(`ma5_slope`), `ma10_slope`=VALUES(`ma10_slope`), `ma20_slope`=VALUES(`ma20_slope`), `trend_score`=VALUES(`trend_score`), `breadth_score`=VALUES(`breadth_score`), `limit_structure_score`=VALUES(`limit_structure_score`), `volume_score`=VALUES(`volume_score`), `risk_appetite_score`=VALUES(`risk_appetite_score`), `market_breadth_json`=VALUES(`market_breadth_json`), `signals_json`=VALUES(`signals_json`), `recent_trend_json`=VALUES(`recent_trend_json`), `volatility_chart_json`=VALUES(`volatility_chart_json`), `full_result_json`=VALUES(`full_result_json`), `created_at`=VALUES(`created_at`), `updated_at`=VALUES(`updated_at`);

INSERT INTO `hot_board_emotion_daily` (`trade_date`, `board_name`, `sample_trade_date`, `previous_list_complete`, `current_list_complete`, `previous_board_count`, `previous_stock_pool_count`, `previous_detail_coverage`, `current_board_count`, `current_stock_detail_count`, `valid_sample_count`, `quote_coverage`, `average_change_pct`, `median_change_pct`, `average_amplitude_pct`, `change_stddev`, `promotion_count`, `promotion_rate`, `new_promotion_count`, `new_promotion_rate`, `positive_count`, `positive_rate`, `large_gain_count`, `large_gain_rate`, `large_loss_count`, `large_loss_rate`, `failed_limit_count`, `failed_limit_rate`, `retained_count`, `retained_rate`, `heat_stage`, `continuation_state`, `overall_status`, `emotion_score`, `decision_summary`, `decision_reasons_json`, `created_at`, `updated_at`)
SELECT `日期`, `板块`, `样本来源日期`, `前日榜单数据完整`, `当日榜单数据完整`, `前日板块数量`, `前日股票池数量`, `前日明细覆盖率`, `当日板块数量`, `当日股票明细数量`, `有效样本数`, `行情覆盖率`, `平均涨跌幅`, `中位数涨跌幅`, `平均振幅`, `涨幅标准差`, `晋级家数`, `晋级率`, `新晋级家数`, `新晋级率`, `红盘家数`, `红盘率`, `大涨家数`, `大涨率`, `大跌家数`, `大跌率`, `炸板家数`, `炸板率`, `同板块留存家数`, `同板块留存率`, `热度阶段`, `承接情绪`, `综合状态`, `情绪分`, `判定摘要`, CASE WHEN `判定依据JSON` IS NULL THEN NULL ELSE CAST(`判定依据JSON` AS JSON) END, `创建时间`, `更新时间`
FROM `t_热门板块情绪_每日分析`
ON DUPLICATE KEY UPDATE `sample_trade_date`=VALUES(`sample_trade_date`), `previous_list_complete`=VALUES(`previous_list_complete`), `current_list_complete`=VALUES(`current_list_complete`), `previous_board_count`=VALUES(`previous_board_count`), `previous_stock_pool_count`=VALUES(`previous_stock_pool_count`), `previous_detail_coverage`=VALUES(`previous_detail_coverage`), `current_board_count`=VALUES(`current_board_count`), `current_stock_detail_count`=VALUES(`current_stock_detail_count`), `valid_sample_count`=VALUES(`valid_sample_count`), `quote_coverage`=VALUES(`quote_coverage`), `average_change_pct`=VALUES(`average_change_pct`), `median_change_pct`=VALUES(`median_change_pct`), `average_amplitude_pct`=VALUES(`average_amplitude_pct`), `change_stddev`=VALUES(`change_stddev`), `promotion_count`=VALUES(`promotion_count`), `promotion_rate`=VALUES(`promotion_rate`), `new_promotion_count`=VALUES(`new_promotion_count`), `new_promotion_rate`=VALUES(`new_promotion_rate`), `positive_count`=VALUES(`positive_count`), `positive_rate`=VALUES(`positive_rate`), `large_gain_count`=VALUES(`large_gain_count`), `large_gain_rate`=VALUES(`large_gain_rate`), `large_loss_count`=VALUES(`large_loss_count`), `large_loss_rate`=VALUES(`large_loss_rate`), `failed_limit_count`=VALUES(`failed_limit_count`), `failed_limit_rate`=VALUES(`failed_limit_rate`), `retained_count`=VALUES(`retained_count`), `retained_rate`=VALUES(`retained_rate`), `heat_stage`=VALUES(`heat_stage`), `continuation_state`=VALUES(`continuation_state`), `overall_status`=VALUES(`overall_status`), `emotion_score`=VALUES(`emotion_score`), `decision_summary`=VALUES(`decision_summary`), `decision_reasons_json`=VALUES(`decision_reasons_json`), `created_at`=VALUES(`created_at`), `updated_at`=VALUES(`updated_at`);

INSERT INTO `securities` (`ts_code`, `symbol`, `name`, `area`, `industry`, `market`, `list_date`, `list_status`)
SELECT CAST(`ts_code` AS CHAR), LPAD(CAST(`symbol` AS CHAR), 6, '0'), `name`, `area`, `industry`, `market`, CAST(`list_date` AS UNSIGNED), `list_status`
FROM `stock_basic`
ON DUPLICATE KEY UPDATE `symbol`=VALUES(`symbol`), `name`=VALUES(`name`), `area`=VALUES(`area`), `industry`=VALUES(`industry`), `market`=VALUES(`market`), `list_date`=VALUES(`list_date`), `list_status`=VALUES(`list_status`);

INSERT INTO `daily_quotes` (`data_id`, `ts_code`, `trade_date`, `open_price`, `high_price`, `low_price`, `close_price`, `previous_close`, `change_amount`, `change_pct`, `volume`, `turnover`, `total_market_value`, `circulating_market_value`, `free_float_shares`, `free_float_market_value`, `stock_name`, `dde_net_amount`)
SELECT CONCAT(CASE WHEN LEFT(LPAD(`ts_code`, 6, '0'), 1) IN ('4', '8') THEN CONCAT(LPAD(`ts_code`, 6, '0'), '.BJ') WHEN CAST(`ts_code` AS UNSIGNED) >= 600000 THEN CONCAT(LPAD(`ts_code`, 6, '0'), '.SH') ELSE CONCAT(LPAD(`ts_code`, 6, '0'), '.SZ') END, '_', `trade_date`), CASE WHEN LEFT(LPAD(`ts_code`, 6, '0'), 1) IN ('4', '8') THEN CONCAT(LPAD(`ts_code`, 6, '0'), '.BJ') WHEN CAST(`ts_code` AS UNSIGNED) >= 600000 THEN CONCAT(LPAD(`ts_code`, 6, '0'), '.SH') ELSE CONCAT(LPAD(`ts_code`, 6, '0'), '.SZ') END, `trade_date`, `open`, `high`, `low`, `close`, `pre_close`, `change`, `pct_chg`, `vol`, `amount`, `total_mv`, `circ_mv`, `free_share`, `free_mv`, `stock_name`, `dde`
FROM `stock_daily`
ON DUPLICATE KEY UPDATE `ts_code`=VALUES(`ts_code`), `trade_date`=VALUES(`trade_date`), `open_price`=VALUES(`open_price`), `high_price`=VALUES(`high_price`), `low_price`=VALUES(`low_price`), `close_price`=VALUES(`close_price`), `previous_close`=VALUES(`previous_close`), `change_amount`=VALUES(`change_amount`), `change_pct`=VALUES(`change_pct`), `volume`=VALUES(`volume`), `turnover`=VALUES(`turnover`), `total_market_value`=VALUES(`total_market_value`), `circulating_market_value`=VALUES(`circulating_market_value`), `free_float_shares`=VALUES(`free_float_shares`), `free_float_market_value`=VALUES(`free_float_market_value`), `stock_name`=VALUES(`stock_name`), `dde_net_amount`=VALUES(`dde_net_amount`);

INSERT INTO `kdj_indicators` (`data_id`, `ts_code`, `trade_date`, `k_value`, `d_value`, `j_value`)
SELECT CONCAT(CASE WHEN LEFT(LPAD(`ts_code`, 6, '0'), 1) IN ('4', '8') THEN CONCAT(LPAD(`ts_code`, 6, '0'), '.BJ') WHEN CAST(`ts_code` AS UNSIGNED) >= 600000 THEN CONCAT(LPAD(`ts_code`, 6, '0'), '.SH') ELSE CONCAT(LPAD(`ts_code`, 6, '0'), '.SZ') END, '_', `trade_date`), CASE WHEN LEFT(LPAD(`ts_code`, 6, '0'), 1) IN ('4', '8') THEN CONCAT(LPAD(`ts_code`, 6, '0'), '.BJ') WHEN CAST(`ts_code` AS UNSIGNED) >= 600000 THEN CONCAT(LPAD(`ts_code`, 6, '0'), '.SH') ELSE CONCAT(LPAD(`ts_code`, 6, '0'), '.SZ') END, `trade_date`, `k`, `d`, `j`
FROM `stock_kdj`
ON DUPLICATE KEY UPDATE `ts_code`=VALUES(`ts_code`), `trade_date`=VALUES(`trade_date`), `k_value`=VALUES(`k_value`), `d_value`=VALUES(`d_value`), `j_value`=VALUES(`j_value`);

INSERT INTO `intraday_bars_5m` (`data_id`, `trade_date`, `trade_time`, `stock_code`, `open_price`, `high_price`, `low_price`, `close_price`, `volume`, `turnover`, `adjustment_flag`)
SELECT CONCAT(LPAD(CAST(`code` AS CHAR), 6, '0'), '_', `time`, '_', `adjustflag`), `date`, `time`, LPAD(CAST(`code` AS CHAR), 6, '0'), `open`, `high`, `low`, `close`, `volume`, `amount`, `adjustflag`
FROM `t_stock_5_min_k`
ON DUPLICATE KEY UPDATE `trade_date`=VALUES(`trade_date`), `trade_time`=VALUES(`trade_time`), `stock_code`=VALUES(`stock_code`), `open_price`=VALUES(`open_price`), `high_price`=VALUES(`high_price`), `low_price`=VALUES(`low_price`), `close_price`=VALUES(`close_price`), `volume`=VALUES(`volume`), `turnover`=VALUES(`turnover`), `adjustment_flag`=VALUES(`adjustment_flag`);

INSERT INTO `jiuyan_actions` (`data_id`, `trade_date`, `board_name`, `board_stock_count`, `stock_code`, `stock_name`, `source_code`, `limit_up_at`, `board_streak`, `change_pct`, `limit_up_reason`)
SELECT `data_id`, `date`, `板块`, `板块个股数量`, LPAD(CAST(`股票代码` AS CHAR), 6, '0'), `股票名称`, `code`, `涨停时间`, `几天几板`, `涨幅`, `涨停解析`
FROM `t_韭研公社异动解析`
ON DUPLICATE KEY UPDATE `trade_date`=VALUES(`trade_date`), `board_name`=VALUES(`board_name`), `board_stock_count`=VALUES(`board_stock_count`), `stock_code`=VALUES(`stock_code`), `stock_name`=VALUES(`stock_name`), `source_code`=VALUES(`source_code`), `limit_up_at`=VALUES(`limit_up_at`), `board_streak`=VALUES(`board_streak`), `change_pct`=VALUES(`change_pct`), `limit_up_reason`=VALUES(`limit_up_reason`);

INSERT INTO `dragon_tiger` (`data_id`, `trade_date`, `source_id`, `detail_type`, `date_type`, `stock_code`, `stock_name`, `current_price`, `change_pct`, `turnover`, `net_buy_amount`, `total_buy_amount`, `total_sell_amount`, `buy_1_broker_id`, `buy_1_broker_name`, `buy_1_buy_amount`, `buy_1_sell_amount`, `buy_1_net_amount`, `buy_2_broker_id`, `buy_2_broker_name`, `buy_2_buy_amount`, `buy_2_sell_amount`, `buy_2_net_amount`, `buy_3_broker_id`, `buy_3_broker_name`, `buy_3_buy_amount`, `buy_3_sell_amount`, `buy_3_net_amount`, `buy_4_broker_id`, `buy_4_broker_name`, `buy_4_buy_amount`, `buy_4_sell_amount`, `buy_4_net_amount`, `buy_5_broker_id`, `buy_5_broker_name`, `buy_5_buy_amount`, `buy_5_sell_amount`, `buy_5_net_amount`, `sell_1_broker_id`, `sell_1_broker_name`, `sell_1_buy_amount`, `sell_1_sell_amount`, `sell_1_net_amount`, `sell_2_broker_id`, `sell_2_broker_name`, `sell_2_buy_amount`, `sell_2_sell_amount`, `sell_2_net_amount`, `sell_3_broker_id`, `sell_3_broker_name`, `sell_3_buy_amount`, `sell_3_sell_amount`, `sell_3_net_amount`, `sell_4_broker_id`, `sell_4_broker_name`, `sell_4_buy_amount`, `sell_4_sell_amount`, `sell_4_net_amount`, `sell_5_broker_id`, `sell_5_broker_name`, `sell_5_buy_amount`, `sell_5_sell_amount`, `sell_5_net_amount`)
SELECT `data_id`, `date`, `rid`, `明细`, `日期类型`, `股票代码`, `股票名称`, `现价`, `涨跌幅`, `成交金额`, `净买入额`, `合计买入`, `合计卖出`, `买1营业部id`, `买1营业部`, `买1买入额`, `买1卖出额`, `买1净额`, `买2营业部id`, `买2营业部`, `买2买入额`, `买2卖出额`, `买2净额`, `买3营业部id`, `买3营业部`, `买3买入额`, `买3卖出额`, `买3净额`, `买4营业部id`, `买4营业部`, `买4买入额`, `买4卖出额`, `买4净额`, `买5营业部id`, `买5营业部`, `买5买入额`, `买5卖出额`, `买5净额`, `卖1营业部id`, `卖1营业部`, `卖1买入额`, `卖1卖出额`, `卖1净额`, `卖2营业部id`, `卖2营业部`, `卖2买入额`, `卖2卖出额`, `卖2净额`, `卖3营业部id`, `卖3营业部`, `卖3买入额`, `卖3卖出额`, `卖3净额`, `卖4营业部id`, `卖4营业部`, `卖4买入额`, `卖4卖出额`, `卖4净额`, `卖5营业部id`, `卖5营业部`, `卖5买入额`, `卖5卖出额`, `卖5净额`
FROM `t_龙虎榜`
ON DUPLICATE KEY UPDATE `trade_date`=VALUES(`trade_date`), `source_id`=VALUES(`source_id`), `detail_type`=VALUES(`detail_type`), `date_type`=VALUES(`date_type`), `stock_code`=VALUES(`stock_code`), `stock_name`=VALUES(`stock_name`), `current_price`=VALUES(`current_price`), `change_pct`=VALUES(`change_pct`), `turnover`=VALUES(`turnover`), `net_buy_amount`=VALUES(`net_buy_amount`), `total_buy_amount`=VALUES(`total_buy_amount`), `total_sell_amount`=VALUES(`total_sell_amount`), `buy_1_broker_id`=VALUES(`buy_1_broker_id`), `buy_1_broker_name`=VALUES(`buy_1_broker_name`), `buy_1_buy_amount`=VALUES(`buy_1_buy_amount`), `buy_1_sell_amount`=VALUES(`buy_1_sell_amount`), `buy_1_net_amount`=VALUES(`buy_1_net_amount`), `buy_2_broker_id`=VALUES(`buy_2_broker_id`), `buy_2_broker_name`=VALUES(`buy_2_broker_name`), `buy_2_buy_amount`=VALUES(`buy_2_buy_amount`), `buy_2_sell_amount`=VALUES(`buy_2_sell_amount`), `buy_2_net_amount`=VALUES(`buy_2_net_amount`), `buy_3_broker_id`=VALUES(`buy_3_broker_id`), `buy_3_broker_name`=VALUES(`buy_3_broker_name`), `buy_3_buy_amount`=VALUES(`buy_3_buy_amount`), `buy_3_sell_amount`=VALUES(`buy_3_sell_amount`), `buy_3_net_amount`=VALUES(`buy_3_net_amount`), `buy_4_broker_id`=VALUES(`buy_4_broker_id`), `buy_4_broker_name`=VALUES(`buy_4_broker_name`), `buy_4_buy_amount`=VALUES(`buy_4_buy_amount`), `buy_4_sell_amount`=VALUES(`buy_4_sell_amount`), `buy_4_net_amount`=VALUES(`buy_4_net_amount`), `buy_5_broker_id`=VALUES(`buy_5_broker_id`), `buy_5_broker_name`=VALUES(`buy_5_broker_name`), `buy_5_buy_amount`=VALUES(`buy_5_buy_amount`), `buy_5_sell_amount`=VALUES(`buy_5_sell_amount`), `buy_5_net_amount`=VALUES(`buy_5_net_amount`), `sell_1_broker_id`=VALUES(`sell_1_broker_id`), `sell_1_broker_name`=VALUES(`sell_1_broker_name`), `sell_1_buy_amount`=VALUES(`sell_1_buy_amount`), `sell_1_sell_amount`=VALUES(`sell_1_sell_amount`), `sell_1_net_amount`=VALUES(`sell_1_net_amount`), `sell_2_broker_id`=VALUES(`sell_2_broker_id`), `sell_2_broker_name`=VALUES(`sell_2_broker_name`), `sell_2_buy_amount`=VALUES(`sell_2_buy_amount`), `sell_2_sell_amount`=VALUES(`sell_2_sell_amount`), `sell_2_net_amount`=VALUES(`sell_2_net_amount`), `sell_3_broker_id`=VALUES(`sell_3_broker_id`), `sell_3_broker_name`=VALUES(`sell_3_broker_name`), `sell_3_buy_amount`=VALUES(`sell_3_buy_amount`), `sell_3_sell_amount`=VALUES(`sell_3_sell_amount`), `sell_3_net_amount`=VALUES(`sell_3_net_amount`), `sell_4_broker_id`=VALUES(`sell_4_broker_id`), `sell_4_broker_name`=VALUES(`sell_4_broker_name`), `sell_4_buy_amount`=VALUES(`sell_4_buy_amount`), `sell_4_sell_amount`=VALUES(`sell_4_sell_amount`), `sell_4_net_amount`=VALUES(`sell_4_net_amount`), `sell_5_broker_id`=VALUES(`sell_5_broker_id`), `sell_5_broker_name`=VALUES(`sell_5_broker_name`), `sell_5_buy_amount`=VALUES(`sell_5_buy_amount`), `sell_5_sell_amount`=VALUES(`sell_5_sell_amount`), `sell_5_net_amount`=VALUES(`sell_5_net_amount`);

INSERT INTO `broker_listing_history` (`data_id`, `broker_id`, `broker_name`, `trade_date`, `stock_name`, `stock_code`, `listing_reason`, `change_pct`, `buy_amount`, `sell_amount`, `net_amount`, `board_name`)
SELECT `data_id`, `营业部id`, `营业部名称`, `日期`, `股票简称`, `股票代码`, `上榜原因`, `涨跌幅`, `买入额`, `卖出额`, `买卖净额`, `所属板块`
FROM `t_龙虎榜_营业部_上榜历史数据`
ON DUPLICATE KEY UPDATE `broker_id`=VALUES(`broker_id`), `broker_name`=VALUES(`broker_name`), `trade_date`=VALUES(`trade_date`), `stock_name`=VALUES(`stock_name`), `stock_code`=VALUES(`stock_code`), `listing_reason`=VALUES(`listing_reason`), `change_pct`=VALUES(`change_pct`), `buy_amount`=VALUES(`buy_amount`), `sell_amount`=VALUES(`sell_amount`), `net_amount`=VALUES(`net_amount`), `board_name`=VALUES(`board_name`);

INSERT INTO `broker_top_stats` (`broker_id`, `broker_name`, `listing_count`, `total_capital_used`, `year_listing_count`, `year_stock_count`, `three_day_follow_success_rate`)
SELECT
  CAST(`营业部id` AS CHAR),
  `营业部名称`,
  CASE WHEN NULLIF(TRIM(CAST(`上榜次数` AS CHAR)), '') IS NULL THEN NULL ELSE CAST(REPLACE(REGEXP_REPLACE(TRIM(CAST(`上榜次数` AS CHAR)), '(次|家|只)$', ''), ',', '') AS UNSIGNED) END,
  CASE WHEN NULLIF(TRIM(CAST(`合计动用资金` AS CHAR)), '') IS NULL THEN NULL ELSE CAST(REPLACE(REGEXP_REPLACE(TRIM(CAST(`合计动用资金` AS CHAR)), '(元|万|万元|亿|亿元)$', ''), ',', '') AS DECIMAL(30,4)) * CASE WHEN REGEXP_LIKE(TRIM(CAST(`合计动用资金` AS CHAR)), '亿(元)?$') THEN 100000000 WHEN REGEXP_LIKE(TRIM(CAST(`合计动用资金` AS CHAR)), '万(元)?$') THEN 10000 ELSE 1 END END,
  CASE WHEN NULLIF(TRIM(CAST(`年内上榜次数` AS CHAR)), '') IS NULL THEN NULL ELSE CAST(REPLACE(REGEXP_REPLACE(TRIM(CAST(`年内上榜次数` AS CHAR)), '(次|家|只)$', ''), ',', '') AS UNSIGNED) END,
  CASE WHEN NULLIF(TRIM(CAST(`年内买入股票只数` AS CHAR)), '') IS NULL THEN NULL ELSE CAST(REPLACE(REGEXP_REPLACE(TRIM(CAST(`年内买入股票只数` AS CHAR)), '(次|家|只)$', ''), ',', '') AS UNSIGNED) END,
  CASE WHEN NULLIF(TRIM(CAST(`年内3日跟买成功率` AS CHAR)), '') IS NULL THEN NULL ELSE CAST(REPLACE(REPLACE(TRIM(CAST(`年内3日跟买成功率` AS CHAR)), ',', ''), '%', '') AS DECIMAL(10,4)) END
FROM `t_龙虎榜_营业部_上榜次数最多`
ON DUPLICATE KEY UPDATE `broker_name`=VALUES(`broker_name`), `listing_count`=VALUES(`listing_count`), `total_capital_used`=VALUES(`total_capital_used`), `year_listing_count`=VALUES(`year_listing_count`), `year_stock_count`=VALUES(`year_stock_count`), `three_day_follow_success_rate`=VALUES(`three_day_follow_success_rate`);

INSERT INTO `brokers` (`broker_id`, `broker_name`)
SELECT CAST(`营业部id` AS CHAR), `营业部名称`
FROM `t_龙虎榜_营业部_全部`
ON DUPLICATE KEY UPDATE `broker_name`=VALUES(`broker_name`);

INSERT INTO `ths_boards` (`board_code`, `board_type`, `board_name`, `page_code`, `detail_path`, `collected_date`, `updated_at`)
SELECT `板块代码`, `板块类型`, `板块名称`, `页面代码`, `详情路径`, `采集日期`, `更新时间`
FROM `t_同花顺板块列表`
ON DUPLICATE KEY UPDATE `board_type`=VALUES(`board_type`), `board_name`=VALUES(`board_name`), `page_code`=VALUES(`page_code`), `detail_path`=VALUES(`detail_path`), `collected_date`=VALUES(`collected_date`), `updated_at`=VALUES(`updated_at`);

INSERT INTO `ths_board_constituents` (`board_code`, `stock_code`, `board_type`, `board_name`, `page_code`, `stock_name`, `collected_date`, `updated_at`)
SELECT `板块代码`, `股票代码`, `板块类型`, `板块名称`, `页面代码`, `股票名称`, `采集日期`, `更新时间`
FROM `t_同花顺板块成分股`
ON DUPLICATE KEY UPDATE `board_type`=VALUES(`board_type`), `board_name`=VALUES(`board_name`), `page_code`=VALUES(`page_code`), `stock_name`=VALUES(`stock_name`), `collected_date`=VALUES(`collected_date`), `updated_at`=VALUES(`updated_at`);

INSERT INTO `ths_stock_relations` (`stock_code`, `stock_name`, `industry_names`, `industry_codes`, `concept_names`, `concept_codes`, `collected_date`, `updated_at`)
SELECT `股票代码`, `股票名称`, `同花顺行业`, `同花顺行业代码`, `同花顺概念`, `同花顺概念代码`, `采集日期`, `更新时间`
FROM `t_同花顺股票板块概念对应关系`
ON DUPLICATE KEY UPDATE `stock_name`=VALUES(`stock_name`), `industry_names`=VALUES(`industry_names`), `industry_codes`=VALUES(`industry_codes`), `concept_names`=VALUES(`concept_names`), `concept_codes`=VALUES(`concept_codes`), `collected_date`=VALUES(`collected_date`), `updated_at`=VALUES(`updated_at`);

CALL assert_mapping_parity(
  'index_daily',
  (SELECT COUNT(*) FROM `akshare_sh000001`), (SELECT COUNT(*) FROM `index_daily`),
  (SELECT COUNT(DISTINCT `日期`) FROM `akshare_sh000001`), (SELECT COUNT(DISTINCT `trade_date`) FROM `index_daily`),
  (SELECT MIN(`日期`) FROM `akshare_sh000001`), (SELECT MIN(`trade_date`) FROM `index_daily`),
  (SELECT MAX(`日期`) FROM `akshare_sh000001`), (SELECT MAX(`trade_date`) FROM `index_daily`),
  (SELECT JSON_OBJECT('volume', SUM(CAST(`成交量` AS DECIMAL(65,6))), 'turnover', SUM(CAST(`成交额` AS DECIMAL(65,6))), 'change_amount', SUM(CAST(`涨跌额` AS DECIMAL(65,6)))) FROM `akshare_sh000001`),
  (SELECT JSON_OBJECT('volume', SUM(CAST(`volume` AS DECIMAL(65,6))), 'turnover', SUM(CAST(`turnover` AS DECIMAL(65,6))), 'change_amount', SUM(CAST(`change_amount` AS DECIMAL(65,6)))) FROM `index_daily`),
  NULL
);
CALL assert_mapping_parity(
  'index_market_breadth',
  (SELECT COUNT(*) FROM `t_指数情绪周期_市场宽度`), (SELECT COUNT(*) FROM `index_market_breadth`),
  (SELECT COUNT(DISTINCT `日期`) FROM `t_指数情绪周期_市场宽度`), (SELECT COUNT(DISTINCT `trade_date`) FROM `index_market_breadth`),
  (SELECT MIN(`日期`) FROM `t_指数情绪周期_市场宽度`), (SELECT MIN(`trade_date`) FROM `index_market_breadth`),
  (SELECT MAX(`日期`) FROM `t_指数情绪周期_市场宽度`), (SELECT MAX(`trade_date`) FROM `index_market_breadth`),
  (SELECT JSON_OBJECT('stock_count', SUM(CAST(`股票总数` AS DECIMAL(65,6))), 'market_turnover', SUM(CAST(`成交额` AS DECIMAL(65,6)))) FROM `t_指数情绪周期_市场宽度`),
  (SELECT JSON_OBJECT('stock_count', SUM(CAST(`stock_count` AS DECIMAL(65,6))), 'market_turnover', SUM(CAST(`market_turnover` AS DECIMAL(65,6)))) FROM `index_market_breadth`),
  NULL
);
CALL assert_mapping_parity(
  'index_emotion_daily',
  (SELECT COUNT(*) FROM `t_指数情绪周期_每日分析`), (SELECT COUNT(*) FROM `index_emotion_daily`),
  (SELECT COUNT(DISTINCT `日期`) FROM `t_指数情绪周期_每日分析`), (SELECT COUNT(DISTINCT `trade_date`) FROM `index_emotion_daily`),
  (SELECT MIN(`日期`) FROM `t_指数情绪周期_每日分析`), (SELECT MIN(`trade_date`) FROM `index_emotion_daily`),
  (SELECT MAX(`日期`) FROM `t_指数情绪周期_每日分析`), (SELECT MAX(`trade_date`) FROM `index_emotion_daily`),
  (SELECT JSON_OBJECT('cycle_score', SUM(CAST(`周期分数` AS DECIMAL(65,6))), 'index_turnover', SUM(CAST(`指数成交额` AS DECIMAL(65,6)))) FROM `t_指数情绪周期_每日分析`),
  (SELECT JSON_OBJECT('cycle_score', SUM(CAST(`cycle_score` AS DECIMAL(65,6))), 'index_turnover', SUM(CAST(`index_turnover` AS DECIMAL(65,6)))) FROM `index_emotion_daily`),
  (SELECT SUM(CASE WHEN (`market_breadth_json` IS NOT NULL AND JSON_VALID(`market_breadth_json`) = 0) OR (`signals_json` IS NOT NULL AND JSON_VALID(`signals_json`) = 0) OR (`recent_trend_json` IS NOT NULL AND JSON_VALID(`recent_trend_json`) = 0) OR (`volatility_chart_json` IS NOT NULL AND JSON_VALID(`volatility_chart_json`) = 0) OR (`full_result_json` IS NOT NULL AND JSON_VALID(`full_result_json`) = 0) THEN 1 ELSE 0 END) FROM `index_emotion_daily`)
);
CALL assert_mapping_parity(
  'hot_board_emotion_daily',
  (SELECT COUNT(*) FROM `t_热门板块情绪_每日分析`), (SELECT COUNT(*) FROM `hot_board_emotion_daily`),
  (SELECT COUNT(DISTINCT CONCAT_WS(CHAR(31), `日期`, `板块`)) FROM `t_热门板块情绪_每日分析`), (SELECT COUNT(DISTINCT CONCAT_WS(CHAR(31), `trade_date`, `board_name`)) FROM `hot_board_emotion_daily`),
  (SELECT MIN(`日期`) FROM `t_热门板块情绪_每日分析`), (SELECT MIN(`trade_date`) FROM `hot_board_emotion_daily`),
  (SELECT MAX(`日期`) FROM `t_热门板块情绪_每日分析`), (SELECT MAX(`trade_date`) FROM `hot_board_emotion_daily`),
  (SELECT JSON_OBJECT('valid_sample_count', SUM(CAST(`有效样本数` AS DECIMAL(65,6))), 'emotion_score', SUM(CAST(`情绪分` AS DECIMAL(65,6)))) FROM `t_热门板块情绪_每日分析`),
  (SELECT JSON_OBJECT('valid_sample_count', SUM(CAST(`valid_sample_count` AS DECIMAL(65,6))), 'emotion_score', SUM(CAST(`emotion_score` AS DECIMAL(65,6)))) FROM `hot_board_emotion_daily`),
  (SELECT SUM(CASE WHEN `decision_reasons_json` IS NOT NULL AND JSON_VALID(`decision_reasons_json`) = 0 THEN 1 ELSE 0 END) FROM `hot_board_emotion_daily`)
);
CALL assert_mapping_parity(
  'securities',
  (SELECT COUNT(*) FROM `stock_basic`), (SELECT COUNT(*) FROM `securities`),
  (SELECT COUNT(DISTINCT CAST(`ts_code` AS CHAR)) FROM `stock_basic`), (SELECT COUNT(DISTINCT `ts_code`) FROM `securities`),
  NULL, NULL, NULL, NULL,
  NULL, NULL, NULL
);
CALL assert_mapping_parity(
  'daily_quotes',
  (SELECT COUNT(*) FROM `stock_daily`), (SELECT COUNT(*) FROM `daily_quotes`),
  (SELECT COUNT(DISTINCT CONCAT(CASE WHEN LEFT(LPAD(`ts_code`, 6, '0'), 1) IN ('4', '8') THEN CONCAT(LPAD(`ts_code`, 6, '0'), '.BJ') WHEN CAST(`ts_code` AS UNSIGNED) >= 600000 THEN CONCAT(LPAD(`ts_code`, 6, '0'), '.SH') ELSE CONCAT(LPAD(`ts_code`, 6, '0'), '.SZ') END, '_', `trade_date`)) FROM `stock_daily`), (SELECT COUNT(DISTINCT `data_id`) FROM `daily_quotes`),
  (SELECT MIN(`trade_date`) FROM `stock_daily`), (SELECT MIN(`trade_date`) FROM `daily_quotes`),
  (SELECT MAX(`trade_date`) FROM `stock_daily`), (SELECT MAX(`trade_date`) FROM `daily_quotes`),
  (SELECT JSON_OBJECT('volume', SUM(CAST(`vol` AS DECIMAL(65,6))), 'turnover', SUM(CAST(`amount` AS DECIMAL(65,6))), 'dde_net_amount', SUM(CAST(`dde` AS DECIMAL(65,6)))) FROM `stock_daily`),
  (SELECT JSON_OBJECT('volume', SUM(CAST(`volume` AS DECIMAL(65,6))), 'turnover', SUM(CAST(`turnover` AS DECIMAL(65,6))), 'dde_net_amount', SUM(CAST(`dde_net_amount` AS DECIMAL(65,6)))) FROM `daily_quotes`),
  NULL
);
CALL assert_mapping_parity(
  'kdj_indicators',
  (SELECT COUNT(*) FROM `stock_kdj`), (SELECT COUNT(*) FROM `kdj_indicators`),
  (SELECT COUNT(DISTINCT CONCAT(CASE WHEN LEFT(LPAD(`ts_code`, 6, '0'), 1) IN ('4', '8') THEN CONCAT(LPAD(`ts_code`, 6, '0'), '.BJ') WHEN CAST(`ts_code` AS UNSIGNED) >= 600000 THEN CONCAT(LPAD(`ts_code`, 6, '0'), '.SH') ELSE CONCAT(LPAD(`ts_code`, 6, '0'), '.SZ') END, '_', `trade_date`)) FROM `stock_kdj`), (SELECT COUNT(DISTINCT `data_id`) FROM `kdj_indicators`),
  (SELECT MIN(`trade_date`) FROM `stock_kdj`), (SELECT MIN(`trade_date`) FROM `kdj_indicators`),
  (SELECT MAX(`trade_date`) FROM `stock_kdj`), (SELECT MAX(`trade_date`) FROM `kdj_indicators`),
  (SELECT JSON_OBJECT('k_value', SUM(CAST(`k` AS DECIMAL(65,6))), 'd_value', SUM(CAST(`d` AS DECIMAL(65,6))), 'j_value', SUM(CAST(`j` AS DECIMAL(65,6)))) FROM `stock_kdj`),
  (SELECT JSON_OBJECT('k_value', SUM(CAST(`k_value` AS DECIMAL(65,6))), 'd_value', SUM(CAST(`d_value` AS DECIMAL(65,6))), 'j_value', SUM(CAST(`j_value` AS DECIMAL(65,6)))) FROM `kdj_indicators`),
  NULL
);
CALL assert_mapping_parity(
  'intraday_bars_5m',
  (SELECT COUNT(*) FROM `t_stock_5_min_k`), (SELECT COUNT(*) FROM `intraday_bars_5m`),
  (SELECT COUNT(DISTINCT CONCAT(LPAD(CAST(`code` AS CHAR), 6, '0'), '_', `time`, '_', `adjustflag`)) FROM `t_stock_5_min_k`), (SELECT COUNT(DISTINCT `data_id`) FROM `intraday_bars_5m`),
  (SELECT MIN(`date`) FROM `t_stock_5_min_k`), (SELECT MIN(`trade_date`) FROM `intraday_bars_5m`),
  (SELECT MAX(`date`) FROM `t_stock_5_min_k`), (SELECT MAX(`trade_date`) FROM `intraday_bars_5m`),
  (SELECT JSON_OBJECT('volume', SUM(CAST(`volume` AS DECIMAL(65,6))), 'turnover', SUM(CAST(`amount` AS DECIMAL(65,6)))) FROM `t_stock_5_min_k`),
  (SELECT JSON_OBJECT('volume', SUM(CAST(`volume` AS DECIMAL(65,6))), 'turnover', SUM(CAST(`turnover` AS DECIMAL(65,6)))) FROM `intraday_bars_5m`),
  NULL
);
CALL assert_mapping_parity(
  'jiuyan_actions',
  (SELECT COUNT(*) FROM `t_韭研公社异动解析`), (SELECT COUNT(*) FROM `jiuyan_actions`),
  (SELECT COUNT(DISTINCT `data_id`) FROM `t_韭研公社异动解析`), (SELECT COUNT(DISTINCT `data_id`) FROM `jiuyan_actions`),
  (SELECT MIN(`date`) FROM `t_韭研公社异动解析`), (SELECT MIN(`trade_date`) FROM `jiuyan_actions`),
  (SELECT MAX(`date`) FROM `t_韭研公社异动解析`), (SELECT MAX(`trade_date`) FROM `jiuyan_actions`),
  (SELECT JSON_OBJECT('change_pct', SUM(CAST(`涨幅` AS DECIMAL(65,6)))) FROM `t_韭研公社异动解析`),
  (SELECT JSON_OBJECT('change_pct', SUM(CAST(`change_pct` AS DECIMAL(65,6)))) FROM `jiuyan_actions`),
  NULL
);
CALL assert_mapping_parity(
  'dragon_tiger',
  (SELECT COUNT(*) FROM `t_龙虎榜`), (SELECT COUNT(*) FROM `dragon_tiger`),
  (SELECT COUNT(DISTINCT `data_id`) FROM `t_龙虎榜`), (SELECT COUNT(DISTINCT `data_id`) FROM `dragon_tiger`),
  (SELECT MIN(`date`) FROM `t_龙虎榜`), (SELECT MIN(`trade_date`) FROM `dragon_tiger`),
  (SELECT MAX(`date`) FROM `t_龙虎榜`), (SELECT MAX(`trade_date`) FROM `dragon_tiger`),
  (SELECT JSON_OBJECT('turnover', SUM(CAST(`成交金额` AS DECIMAL(65,6))), 'net_buy_amount', SUM(CAST(`净买入额` AS DECIMAL(65,6))), 'total_buy_amount', SUM(CAST(`合计买入` AS DECIMAL(65,6))), 'total_sell_amount', SUM(CAST(`合计卖出` AS DECIMAL(65,6)))) FROM `t_龙虎榜`),
  (SELECT JSON_OBJECT('turnover', SUM(CAST(`turnover` AS DECIMAL(65,6))), 'net_buy_amount', SUM(CAST(`net_buy_amount` AS DECIMAL(65,6))), 'total_buy_amount', SUM(CAST(`total_buy_amount` AS DECIMAL(65,6))), 'total_sell_amount', SUM(CAST(`total_sell_amount` AS DECIMAL(65,6)))) FROM `dragon_tiger`),
  NULL
);
CALL assert_mapping_parity(
  'broker_listing_history',
  (SELECT COUNT(*) FROM `t_龙虎榜_营业部_上榜历史数据`), (SELECT COUNT(*) FROM `broker_listing_history`),
  (SELECT COUNT(DISTINCT `data_id`) FROM `t_龙虎榜_营业部_上榜历史数据`), (SELECT COUNT(DISTINCT `data_id`) FROM `broker_listing_history`),
  (SELECT MIN(`日期`) FROM `t_龙虎榜_营业部_上榜历史数据`), (SELECT MIN(`trade_date`) FROM `broker_listing_history`),
  (SELECT MAX(`日期`) FROM `t_龙虎榜_营业部_上榜历史数据`), (SELECT MAX(`trade_date`) FROM `broker_listing_history`),
  (SELECT JSON_OBJECT('buy_amount', SUM(CAST(`买入额` AS DECIMAL(65,6))), 'sell_amount', SUM(CAST(`卖出额` AS DECIMAL(65,6))), 'net_amount', SUM(CAST(`买卖净额` AS DECIMAL(65,6)))) FROM `t_龙虎榜_营业部_上榜历史数据`),
  (SELECT JSON_OBJECT('buy_amount', SUM(CAST(`buy_amount` AS DECIMAL(65,6))), 'sell_amount', SUM(CAST(`sell_amount` AS DECIMAL(65,6))), 'net_amount', SUM(CAST(`net_amount` AS DECIMAL(65,6)))) FROM `broker_listing_history`),
  NULL
);
CALL assert_mapping_parity(
  'broker_top_stats',
  (SELECT COUNT(*) FROM `t_龙虎榜_营业部_上榜次数最多`), (SELECT COUNT(*) FROM `broker_top_stats`),
  (SELECT COUNT(DISTINCT CAST(`营业部id` AS CHAR)) FROM `t_龙虎榜_营业部_上榜次数最多`), (SELECT COUNT(DISTINCT `broker_id`) FROM `broker_top_stats`),
  NULL, NULL, NULL, NULL,
  (SELECT JSON_OBJECT('listing_count', SUM(CAST(CASE WHEN NULLIF(TRIM(CAST(`上榜次数` AS CHAR)), '') IS NULL THEN NULL ELSE CAST(REPLACE(REGEXP_REPLACE(TRIM(CAST(`上榜次数` AS CHAR)), '(次|家|只)$', ''), ',', '') AS UNSIGNED) END AS DECIMAL(65,6))), 'total_capital_used', SUM(CAST(CASE WHEN NULLIF(TRIM(CAST(`合计动用资金` AS CHAR)), '') IS NULL THEN NULL ELSE CAST(REPLACE(REGEXP_REPLACE(TRIM(CAST(`合计动用资金` AS CHAR)), '(元|万|万元|亿|亿元)$', ''), ',', '') AS DECIMAL(30,4)) * CASE WHEN REGEXP_LIKE(TRIM(CAST(`合计动用资金` AS CHAR)), '亿(元)?$') THEN 100000000 WHEN REGEXP_LIKE(TRIM(CAST(`合计动用资金` AS CHAR)), '万(元)?$') THEN 10000 ELSE 1 END END AS DECIMAL(65,6)))) FROM `t_龙虎榜_营业部_上榜次数最多`),
  (SELECT JSON_OBJECT('listing_count', SUM(CAST(`listing_count` AS DECIMAL(65,6))), 'total_capital_used', SUM(CAST(`total_capital_used` AS DECIMAL(65,6)))) FROM `broker_top_stats`),
  NULL
);
CALL assert_mapping_parity(
  'brokers',
  (SELECT COUNT(*) FROM `t_龙虎榜_营业部_全部`), (SELECT COUNT(*) FROM `brokers`),
  (SELECT COUNT(DISTINCT CAST(`营业部id` AS CHAR)) FROM `t_龙虎榜_营业部_全部`), (SELECT COUNT(DISTINCT `broker_id`) FROM `brokers`),
  NULL, NULL, NULL, NULL,
  NULL, NULL, NULL
);
CALL assert_mapping_parity(
  'ths_boards',
  (SELECT COUNT(*) FROM `t_同花顺板块列表`), (SELECT COUNT(*) FROM `ths_boards`),
  (SELECT COUNT(DISTINCT `板块代码`) FROM `t_同花顺板块列表`), (SELECT COUNT(DISTINCT `board_code`) FROM `ths_boards`),
  (SELECT MIN(`采集日期`) FROM `t_同花顺板块列表`), (SELECT MIN(`collected_date`) FROM `ths_boards`),
  (SELECT MAX(`采集日期`) FROM `t_同花顺板块列表`), (SELECT MAX(`collected_date`) FROM `ths_boards`),
  NULL, NULL, NULL
);
CALL assert_mapping_parity(
  'ths_board_constituents',
  (SELECT COUNT(*) FROM `t_同花顺板块成分股`), (SELECT COUNT(*) FROM `ths_board_constituents`),
  (SELECT COUNT(DISTINCT CONCAT_WS(CHAR(31), `板块代码`, `股票代码`)) FROM `t_同花顺板块成分股`), (SELECT COUNT(DISTINCT CONCAT_WS(CHAR(31), `board_code`, `stock_code`)) FROM `ths_board_constituents`),
  (SELECT MIN(`采集日期`) FROM `t_同花顺板块成分股`), (SELECT MIN(`collected_date`) FROM `ths_board_constituents`),
  (SELECT MAX(`采集日期`) FROM `t_同花顺板块成分股`), (SELECT MAX(`collected_date`) FROM `ths_board_constituents`),
  NULL, NULL, NULL
);
CALL assert_mapping_parity(
  'ths_stock_relations',
  (SELECT COUNT(*) FROM `t_同花顺股票板块概念对应关系`), (SELECT COUNT(*) FROM `ths_stock_relations`),
  (SELECT COUNT(DISTINCT `股票代码`) FROM `t_同花顺股票板块概念对应关系`), (SELECT COUNT(DISTINCT `stock_code`) FROM `ths_stock_relations`),
  (SELECT MIN(`采集日期`) FROM `t_同花顺股票板块概念对应关系`), (SELECT MIN(`collected_date`) FROM `ths_stock_relations`),
  (SELECT MAX(`采集日期`) FROM `t_同花顺股票板块概念对应关系`), (SELECT MAX(`collected_date`) FROM `ths_stock_relations`),
  NULL, NULL, NULL
);

INSERT INTO `migration_validations` (`validation_version`, `status`, `details`)
VALUES ('002_parity_v1', 'succeeded', 'All 16 source-target parity gates passed')
ON DUPLICATE KEY UPDATE `status`=VALUES(`status`), `validated_at`=CURRENT_TIMESTAMP, `details`=VALUES(`details`);

INSERT INTO `schema_migrations` (`version`) VALUES ('002_migrate_legacy_data')
ON DUPLICATE KEY UPDATE `applied_at`=`applied_at`;

DROP PROCEDURE assert_mapping_parity;
DROP PROCEDURE preflight_legacy_data;
DROP PROCEDURE guard_migration_002;
