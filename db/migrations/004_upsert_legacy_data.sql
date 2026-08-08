SET NAMES utf8mb4;

INSERT INTO `migration_validations` (`validation_version`, `status`, `details`)
VALUES ('004_legacy_containment_v1', 'stale', 'Prior 004 authorization invalidated before rerun')
ON DUPLICATE KEY UPDATE `status`=VALUES(`status`), `validated_at`=CURRENT_TIMESTAMP, `details`=VALUES(`details`);
COMMIT;

CREATE TABLE IF NOT EXISTS `migration_validation_tables` (
  `run_id` char(36) NOT NULL,
  `validation_version` varchar(64) NOT NULL,
  `source_table` varchar(128) NOT NULL,
  `target_table` varchar(128) NOT NULL,
  `source_rows` bigint NOT NULL,
  `source_distinct_keys` bigint NOT NULL,
  `missing_target_keys` bigint NOT NULL,
  `mapped_field_mismatches` bigint NOT NULL,
  `target_rows_before` bigint NOT NULL,
  `target_rows_after` bigint NOT NULL,
  `lost_preexisting_target_keys` bigint NOT NULL,
  `validated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`run_id`, `source_table`),
  KEY `idx_migration_validation_version` (`validation_version`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `migration_cutover_runs` (
  `run_id` char(36) NOT NULL,
  `validation_version` varchar(64) NOT NULL,
  `status` varchar(16) NOT NULL,
  `started_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `completed_at` datetime DEFAULT NULL,
  `details` varchar(512) DEFAULT NULL,
  PRIMARY KEY (`run_id`),
  KEY `idx_migration_cutover_validation` (`validation_version`, `status`, `completed_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `_004_target_keys_before` (
  `mapping_name` varchar(128) NOT NULL,
  `key_value` varchar(512) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL,
  PRIMARY KEY (`mapping_name`, `key_value`)
) ENGINE=InnoDB;

UPDATE `migration_cutover_runs`
SET `status`='stale', `completed_at`=CURRENT_TIMESTAMP
WHERE `validation_version`='004_legacy_containment_v1' AND `status`='succeeded';
COMMIT;

DROP PROCEDURE IF EXISTS assert_mapping_containment;
DROP PROCEDURE IF EXISTS preflight_legacy_data_004;
DROP PROCEDURE IF EXISTS run_migration_004;

DELIMITER $$
CREATE PROCEDURE preflight_legacy_data_004()
BEGIN
  DECLARE v_source_table varchar(128) DEFAULT NULL;
  DECLARE v_source_column varchar(128) DEFAULT NULL;
  DECLARE v_source_key varchar(255) DEFAULT NULL;
  DECLARE v_message varchar(128);

  SELECT invalid.source_table, invalid.source_column, invalid.source_key
  INTO v_source_table, v_source_column, v_source_key
  FROM (
    SELECT 't_指数情绪周期_每日分析' AS source_table, '市场宽度JSON' AS source_column, CAST(`日期` AS CHAR) AS source_key FROM `t_指数情绪周期_每日分析` WHERE `市场宽度JSON` IS NOT NULL AND JSON_VALID(CAST(`市场宽度JSON` AS CHAR))=0
    UNION ALL SELECT 't_指数情绪周期_每日分析', '信号JSON', CAST(`日期` AS CHAR) FROM `t_指数情绪周期_每日分析` WHERE `信号JSON` IS NOT NULL AND JSON_VALID(CAST(`信号JSON` AS CHAR))=0
    UNION ALL SELECT 't_指数情绪周期_每日分析', '最近走势JSON', CAST(`日期` AS CHAR) FROM `t_指数情绪周期_每日分析` WHERE `最近走势JSON` IS NOT NULL AND JSON_VALID(CAST(`最近走势JSON` AS CHAR))=0
    UNION ALL SELECT 't_指数情绪周期_每日分析', '波动图JSON', CAST(`日期` AS CHAR) FROM `t_指数情绪周期_每日分析` WHERE `波动图JSON` IS NOT NULL AND JSON_VALID(CAST(`波动图JSON` AS CHAR))=0
    UNION ALL SELECT 't_指数情绪周期_每日分析', '完整结果JSON', CAST(`日期` AS CHAR) FROM `t_指数情绪周期_每日分析` WHERE `完整结果JSON` IS NOT NULL AND JSON_VALID(CAST(`完整结果JSON` AS CHAR))=0
    UNION ALL SELECT 't_热门板块情绪_每日分析', '判定依据JSON', CONCAT(CAST(`日期` AS CHAR), '/', `板块`) FROM `t_热门板块情绪_每日分析` WHERE `判定依据JSON` IS NOT NULL AND JSON_VALID(CAST(`判定依据JSON` AS CHAR))=0
  ) invalid
  LIMIT 1;
  IF v_source_table IS NOT NULL THEN
    SET v_message=LEFT(CONCAT('Invalid legacy JSON: ',v_source_table,'.',v_source_column,' key=',COALESCE(v_source_key,'<NULL>')),128);
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT=v_message;
  END IF;

  SET v_source_table=NULL;
  SET v_source_column=NULL;
  SET v_source_key=NULL;
  SELECT invalid.source_table, invalid.source_column, invalid.source_key
  INTO v_source_table, v_source_column, v_source_key
  FROM (
    SELECT 't_龙虎榜_营业部_上榜次数最多' AS source_table, '上榜次数' AS source_column, CAST(`营业部id` AS CHAR) AS source_key FROM `t_龙虎榜_营业部_上榜次数最多` WHERE NULLIF(TRIM(CAST(`上榜次数` AS CHAR)),'') IS NOT NULL AND NOT REGEXP_LIKE(TRIM(CAST(`上榜次数` AS CHAR)),'^([0-9]+|[0-9]{1,3}(,[0-9]{3})+)(次|家|只)?$')
    UNION ALL SELECT 't_龙虎榜_营业部_上榜次数最多', '年内上榜次数', CAST(`营业部id` AS CHAR) FROM `t_龙虎榜_营业部_上榜次数最多` WHERE NULLIF(TRIM(CAST(`年内上榜次数` AS CHAR)),'') IS NOT NULL AND NOT REGEXP_LIKE(TRIM(CAST(`年内上榜次数` AS CHAR)),'^([0-9]+|[0-9]{1,3}(,[0-9]{3})+)(次|家|只)?$')
    UNION ALL SELECT 't_龙虎榜_营业部_上榜次数最多', '年内买入股票只数', CAST(`营业部id` AS CHAR) FROM `t_龙虎榜_营业部_上榜次数最多` WHERE NULLIF(TRIM(CAST(`年内买入股票只数` AS CHAR)),'') IS NOT NULL AND NOT REGEXP_LIKE(TRIM(CAST(`年内买入股票只数` AS CHAR)),'^([0-9]+|[0-9]{1,3}(,[0-9]{3})+)(次|家|只)?$')
    UNION ALL SELECT 't_龙虎榜_营业部_上榜次数最多', '合计动用资金', CAST(`营业部id` AS CHAR) FROM `t_龙虎榜_营业部_上榜次数最多` WHERE NULLIF(TRIM(CAST(`合计动用资金` AS CHAR)),'') IS NOT NULL AND NOT REGEXP_LIKE(TRIM(CAST(`合计动用资金` AS CHAR)),'^[+-]?([0-9]+|[0-9]{1,3}(,[0-9]{3})+)([.][0-9]+)?(元|万|万元|亿|亿元)?$')
    UNION ALL SELECT 't_龙虎榜_营业部_上榜次数最多', '年内3日跟买成功率', CAST(`营业部id` AS CHAR) FROM `t_龙虎榜_营业部_上榜次数最多` WHERE NULLIF(TRIM(CAST(`年内3日跟买成功率` AS CHAR)),'') IS NOT NULL AND NOT REGEXP_LIKE(TRIM(CAST(`年内3日跟买成功率` AS CHAR)),'^[+-]?([0-9]+|[0-9]{1,3}(,[0-9]{3})+)([.][0-9]+)?%?$')
  ) invalid
  LIMIT 1;
  IF v_source_table IS NOT NULL THEN
    SET v_message=LEFT(CONCAT('Invalid broker statistic: ',v_source_table,'.',v_source_column,' key=',COALESCE(v_source_key,'<NULL>')),128);
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT=v_message;
  END IF;
END$$

CREATE PROCEDURE assert_mapping_containment(
  IN p_source_table varchar(128),
  IN p_target_table varchar(128),
  IN p_source_rows bigint,
  IN p_source_distinct_keys bigint,
  IN p_missing_target_keys bigint,
  IN p_mapped_field_mismatches bigint,
  IN p_target_rows_before bigint,
  IN p_target_rows_after bigint,
  IN p_lost_preexisting_target_keys bigint
)
BEGIN
  DECLARE v_message varchar(128);

  INSERT INTO `migration_validation_tables` (
    `run_id`, `validation_version`, `source_table`, `target_table`, `source_rows`,
    `source_distinct_keys`, `missing_target_keys`, `mapped_field_mismatches`,
    `target_rows_before`, `target_rows_after`, `lost_preexisting_target_keys`
  ) VALUES (
    @migration_004_run_id, '004_legacy_containment_v1', p_source_table, p_target_table, p_source_rows,
    p_source_distinct_keys, p_missing_target_keys, p_mapped_field_mismatches,
    p_target_rows_before, p_target_rows_after, p_lost_preexisting_target_keys
  ) ON DUPLICATE KEY UPDATE
    `target_table`=VALUES(`target_table`), `source_rows`=VALUES(`source_rows`),
    `source_distinct_keys`=VALUES(`source_distinct_keys`), `missing_target_keys`=VALUES(`missing_target_keys`),
    `mapped_field_mismatches`=VALUES(`mapped_field_mismatches`), `target_rows_before`=VALUES(`target_rows_before`),
    `target_rows_after`=VALUES(`target_rows_after`), `lost_preexisting_target_keys`=VALUES(`lost_preexisting_target_keys`),
    `validated_at`=CURRENT_TIMESTAMP;

  IF p_source_rows <> p_source_distinct_keys THEN
    SET v_message = CONCAT('Duplicate source keys: ', p_source_table);
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = v_message;
  END IF;
  IF p_missing_target_keys <> 0 THEN
    SET v_message = CONCAT('Missing target keys: ', p_target_table);
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = v_message;
  END IF;
  IF p_mapped_field_mismatches <> 0 THEN
    SET v_message = CONCAT('Mapped field mismatch: ', p_target_table);
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = v_message;
  END IF;
  IF p_target_rows_after < p_target_rows_before THEN
    SET v_message = CONCAT('Target row count decreased: ', p_target_table);
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = v_message;
  END IF;
  IF p_lost_preexisting_target_keys <> 0 THEN
    SET v_message = CONCAT('Pre-existing target keys lost: ', p_target_table);
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = v_message;
  END IF;
END$$

CREATE PROCEDURE run_migration_004()
BEGIN
  DECLARE v_error_message text DEFAULT 'Migration 004 failed';
  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    GET DIAGNOSTICS CONDITION 1 v_error_message = MESSAGE_TEXT;
    ROLLBACK;
    INSERT INTO `migration_validations` (`validation_version`, `status`, `details`)
    VALUES ('004_legacy_containment_v1', 'failed', LEFT(CONCAT(COALESCE(@migration_004_mapping, 'preflight'), ': ', v_error_message), 512))
    ON DUPLICATE KEY UPDATE `status`=VALUES(`status`), `validated_at`=CURRENT_TIMESTAMP, `details`=VALUES(`details`);
    UPDATE `migration_cutover_runs`
    SET `status`='failed', `completed_at`=CURRENT_TIMESTAMP, `details`=LEFT(v_error_message, 512)
    WHERE `run_id`=@migration_004_run_id;
    COMMIT;
    RESIGNAL;
  END;

  SET @migration_004_run_id = UUID();
  INSERT INTO `migration_cutover_runs` (`run_id`, `validation_version`, `status`, `details`)
  VALUES (@migration_004_run_id, '004_legacy_containment_v1', 'running', 'Migration 004 is running');
  INSERT INTO `migration_validations` (`validation_version`, `status`, `details`)
  VALUES ('004_legacy_containment_v1', 'running', 'Migration 004 legacy upsert and containment validation is running')
  ON DUPLICATE KEY UPDATE `status`=VALUES(`status`), `validated_at`=CURRENT_TIMESTAMP, `details`=VALUES(`details`);
  COMMIT;

  START TRANSACTION;

  CALL preflight_legacy_data_004();

  DELETE FROM `_004_target_keys_before`;

  INSERT INTO `_004_target_keys_before` SELECT 'index_daily', CAST(`trade_date` AS CHAR) FROM `index_daily`;
  INSERT INTO `_004_target_keys_before` SELECT 'index_market_breadth', CAST(`trade_date` AS CHAR) FROM `index_market_breadth`;
  INSERT INTO `_004_target_keys_before` SELECT 'index_emotion_daily', CAST(`trade_date` AS CHAR) FROM `index_emotion_daily`;
  INSERT INTO `_004_target_keys_before` SELECT 'hot_board_emotion_daily', CONCAT(`trade_date`, '|', `board_name`) FROM `hot_board_emotion_daily`;
  INSERT INTO `_004_target_keys_before` SELECT 'securities', `ts_code` FROM `securities`;
  INSERT INTO `_004_target_keys_before` SELECT 'daily_quotes', `data_id` FROM `daily_quotes`;
  INSERT INTO `_004_target_keys_before` SELECT 'kdj_indicators', `data_id` FROM `kdj_indicators`;
  INSERT INTO `_004_target_keys_before` SELECT 'intraday_bars_5m', `data_id` FROM `intraday_bars_5m`;
  INSERT INTO `_004_target_keys_before` SELECT 'jiuyan_actions', `data_id` FROM `jiuyan_actions`;
  INSERT INTO `_004_target_keys_before` SELECT 'dragon_tiger', `data_id` FROM `dragon_tiger`;
  INSERT INTO `_004_target_keys_before` SELECT 'broker_listing_history', `data_id` FROM `broker_listing_history`;
  INSERT INTO `_004_target_keys_before` SELECT 'broker_top_stats', `broker_id` FROM `broker_top_stats`;
  INSERT INTO `_004_target_keys_before` SELECT 'brokers', `broker_id` FROM `brokers`;
  INSERT INTO `_004_target_keys_before` SELECT 'ths_boards', `board_code` FROM `ths_boards`;
  INSERT INTO `_004_target_keys_before` SELECT 'ths_board_constituents', CONCAT(`board_code`, '|', `stock_code`) FROM `ths_board_constituents`;
  INSERT INTO `_004_target_keys_before` SELECT 'ths_stock_relations', `stock_code` FROM `ths_stock_relations`;

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
  SELECT CAST(`营业部id` AS CHAR), `营业部名称`, CASE WHEN NULLIF(TRIM(CAST(`上榜次数` AS CHAR)), '') IS NULL THEN NULL ELSE CAST(REPLACE(REGEXP_REPLACE(TRIM(CAST(`上榜次数` AS CHAR)), '(次|家|只)$', ''), ',', '') AS UNSIGNED) END, CASE WHEN NULLIF(TRIM(CAST(`合计动用资金` AS CHAR)), '') IS NULL THEN NULL ELSE CAST(REPLACE(REGEXP_REPLACE(TRIM(CAST(`合计动用资金` AS CHAR)), '(元|万|万元|亿|亿元)$', ''), ',', '') AS DECIMAL(30,4)) * CASE WHEN REGEXP_LIKE(TRIM(CAST(`合计动用资金` AS CHAR)), '亿(元)?$') THEN 100000000 WHEN REGEXP_LIKE(TRIM(CAST(`合计动用资金` AS CHAR)), '万(元)?$') THEN 10000 ELSE 1 END END, CASE WHEN NULLIF(TRIM(CAST(`年内上榜次数` AS CHAR)), '') IS NULL THEN NULL ELSE CAST(REPLACE(REGEXP_REPLACE(TRIM(CAST(`年内上榜次数` AS CHAR)), '(次|家|只)$', ''), ',', '') AS UNSIGNED) END, CASE WHEN NULLIF(TRIM(CAST(`年内买入股票只数` AS CHAR)), '') IS NULL THEN NULL ELSE CAST(REPLACE(REGEXP_REPLACE(TRIM(CAST(`年内买入股票只数` AS CHAR)), '(次|家|只)$', ''), ',', '') AS UNSIGNED) END, CASE WHEN NULLIF(TRIM(CAST(`年内3日跟买成功率` AS CHAR)), '') IS NULL THEN NULL ELSE CAST(REPLACE(REPLACE(TRIM(CAST(`年内3日跟买成功率` AS CHAR)), ',', ''), '%', '') AS DECIMAL(10,4)) END
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

  SET @migration_004_mapping='akshare_sh000001';
  CALL assert_mapping_containment(
    'akshare_sh000001', 'index_daily',
    (SELECT COUNT(*) FROM `akshare_sh000001`),
    (SELECT COUNT(DISTINCT `日期`) FROM `akshare_sh000001`),
    (SELECT COUNT(*) FROM `akshare_sh000001` s LEFT JOIN `index_daily` t ON t.`trade_date`=s.`日期` WHERE t.`trade_date` IS NULL),
    (SELECT COUNT(*) FROM `akshare_sh000001` s JOIN `index_daily` t ON t.`trade_date`=s.`日期` WHERE NOT (t.`trade_date` <=> s.`日期` AND t.`open_price` <=> s.`开盘` AND t.`close_price` <=> s.`收盘` AND t.`high_price` <=> s.`最高` AND t.`low_price` <=> s.`最低` AND t.`volume` <=> s.`成交量` AND t.`turnover` <=> s.`成交额` AND t.`amplitude_pct` <=> s.`振幅` AND t.`change_pct` <=> s.`涨跌幅` AND t.`change_amount` <=> s.`涨跌额` AND t.`turnover_rate` <=> s.`换手率`)),
    (SELECT COUNT(*) FROM `_004_target_keys_before` WHERE `mapping_name`='index_daily'),
    (SELECT COUNT(*) FROM `index_daily`),
    (SELECT COUNT(*) FROM `_004_target_keys_before` b LEFT JOIN `index_daily` t ON t.`trade_date`=CAST(b.`key_value` AS UNSIGNED) WHERE b.`mapping_name`='index_daily' AND t.`trade_date` IS NULL)
  );

  SET @migration_004_mapping='t_指数情绪周期_市场宽度';
  CALL assert_mapping_containment(
    't_指数情绪周期_市场宽度', 'index_market_breadth',
    (SELECT COUNT(*) FROM `t_指数情绪周期_市场宽度`),
    (SELECT COUNT(DISTINCT `日期`) FROM `t_指数情绪周期_市场宽度`),
    (SELECT COUNT(*) FROM `t_指数情绪周期_市场宽度` s LEFT JOIN `index_market_breadth` t ON t.`trade_date`=s.`日期` WHERE t.`trade_date` IS NULL),
    (SELECT COUNT(*) FROM `t_指数情绪周期_市场宽度` s JOIN `index_market_breadth` t ON t.`trade_date`=s.`日期` WHERE NOT (t.`trade_date` <=> s.`日期` AND t.`stock_count` <=> s.`股票总数` AND t.`advancing_count` <=> s.`上涨家数` AND t.`declining_count` <=> s.`下跌家数` AND t.`advance_over_5_count` <=> s.`涨超5家数` AND t.`decline_over_5_count` <=> s.`跌超5家数` AND t.`limit_up_count` <=> s.`涨停家数` AND t.`limit_down_count` <=> s.`跌停家数` AND t.`market_turnover` <=> s.`成交额` AND t.`average_change_pct` <=> s.`平均涨跌幅` AND t.`created_at` <=> s.`创建时间` AND t.`updated_at` <=> s.`更新时间`)),
    (SELECT COUNT(*) FROM `_004_target_keys_before` WHERE `mapping_name`='index_market_breadth'),
    (SELECT COUNT(*) FROM `index_market_breadth`),
    (SELECT COUNT(*) FROM `_004_target_keys_before` b LEFT JOIN `index_market_breadth` t ON t.`trade_date`=CAST(b.`key_value` AS UNSIGNED) WHERE b.`mapping_name`='index_market_breadth' AND t.`trade_date` IS NULL)
  );

  SET @migration_004_mapping='t_指数情绪周期_每日分析';
  CALL assert_mapping_containment(
    't_指数情绪周期_每日分析', 'index_emotion_daily',
    (SELECT COUNT(*) FROM `t_指数情绪周期_每日分析`),
    (SELECT COUNT(DISTINCT `日期`) FROM `t_指数情绪周期_每日分析`),
    (SELECT COUNT(*) FROM `t_指数情绪周期_每日分析` s LEFT JOIN `index_emotion_daily` t ON t.`trade_date`=s.`日期` WHERE t.`trade_date` IS NULL),
    (SELECT COUNT(*) FROM `t_指数情绪周期_每日分析` s JOIN `index_emotion_daily` t ON t.`trade_date`=s.`日期` WHERE NOT (t.`trade_date` <=> s.`日期` AND t.`index_name` <=> s.`指数名称` AND t.`cycle_state` <=> s.`周期状态` AND t.`cycle_score` <=> s.`周期分数` AND t.`summary` <=> s.`摘要` AND t.`open_price` <=> s.`开盘` AND t.`close_price` <=> s.`收盘` AND t.`high_price` <=> s.`最高` AND t.`low_price` <=> s.`最低` AND t.`change_pct` <=> s.`涨跌幅` AND t.`index_turnover` <=> s.`指数成交额` AND t.`index_turnover_ratio` <=> s.`指数成交额比例` AND t.`market_turnover_ratio` <=> s.`市场成交额比例` AND t.`ma5` <=> s.`MA5` AND t.`ma10` <=> s.`MA10` AND t.`ma20` <=> s.`MA20` AND t.`ma60` <=> s.`MA60` AND t.`ma5_slope` <=> s.`MA5斜率` AND t.`ma10_slope` <=> s.`MA10斜率` AND t.`ma20_slope` <=> s.`MA20斜率` AND t.`trend_score` <=> s.`趋势得分` AND t.`breadth_score` <=> s.`市场宽度得分` AND t.`limit_structure_score` <=> s.`涨跌停结构得分` AND t.`volume_score` <=> s.`量能得分` AND t.`risk_appetite_score` <=> s.`风险偏好得分` AND t.`market_breadth_json` <=> CASE WHEN s.`市场宽度JSON` IS NULL THEN NULL ELSE CAST(s.`市场宽度JSON` AS JSON) END AND t.`signals_json` <=> CASE WHEN s.`信号JSON` IS NULL THEN NULL ELSE CAST(s.`信号JSON` AS JSON) END AND t.`recent_trend_json` <=> CASE WHEN s.`最近走势JSON` IS NULL THEN NULL ELSE CAST(s.`最近走势JSON` AS JSON) END AND t.`volatility_chart_json` <=> CASE WHEN s.`波动图JSON` IS NULL THEN NULL ELSE CAST(s.`波动图JSON` AS JSON) END AND t.`full_result_json` <=> CASE WHEN s.`完整结果JSON` IS NULL THEN NULL ELSE CAST(s.`完整结果JSON` AS JSON) END AND t.`created_at` <=> s.`创建时间` AND t.`updated_at` <=> s.`更新时间`)),
    (SELECT COUNT(*) FROM `_004_target_keys_before` WHERE `mapping_name`='index_emotion_daily'),
    (SELECT COUNT(*) FROM `index_emotion_daily`),
    (SELECT COUNT(*) FROM `_004_target_keys_before` b LEFT JOIN `index_emotion_daily` t ON t.`trade_date`=CAST(b.`key_value` AS UNSIGNED) WHERE b.`mapping_name`='index_emotion_daily' AND t.`trade_date` IS NULL)
  );

  SET @migration_004_mapping='t_热门板块情绪_每日分析';
  CALL assert_mapping_containment(
    't_热门板块情绪_每日分析', 'hot_board_emotion_daily',
    (SELECT COUNT(*) FROM `t_热门板块情绪_每日分析`),
    (SELECT COUNT(DISTINCT CONCAT(`日期`, '|', `板块`)) FROM `t_热门板块情绪_每日分析`),
    (SELECT COUNT(*) FROM `t_热门板块情绪_每日分析` s LEFT JOIN `hot_board_emotion_daily` t ON t.`trade_date`=s.`日期` AND CONVERT(t.`board_name` USING utf8mb4) COLLATE utf8mb4_bin=CONVERT(s.`板块` USING utf8mb4) COLLATE utf8mb4_bin WHERE t.`trade_date` IS NULL),
    (SELECT COUNT(*) FROM `t_热门板块情绪_每日分析` s JOIN `hot_board_emotion_daily` t ON t.`trade_date`=s.`日期` AND CONVERT(t.`board_name` USING utf8mb4) COLLATE utf8mb4_bin=CONVERT(s.`板块` USING utf8mb4) COLLATE utf8mb4_bin WHERE NOT (t.`sample_trade_date` <=> s.`样本来源日期` AND t.`previous_list_complete` <=> s.`前日榜单数据完整` AND t.`current_list_complete` <=> s.`当日榜单数据完整` AND t.`previous_board_count` <=> s.`前日板块数量` AND t.`previous_stock_pool_count` <=> s.`前日股票池数量` AND t.`previous_detail_coverage` <=> s.`前日明细覆盖率` AND t.`current_board_count` <=> s.`当日板块数量` AND t.`current_stock_detail_count` <=> s.`当日股票明细数量` AND t.`valid_sample_count` <=> s.`有效样本数` AND t.`quote_coverage` <=> s.`行情覆盖率` AND t.`average_change_pct` <=> s.`平均涨跌幅` AND t.`median_change_pct` <=> s.`中位数涨跌幅` AND t.`average_amplitude_pct` <=> s.`平均振幅` AND t.`change_stddev` <=> s.`涨幅标准差` AND t.`promotion_count` <=> s.`晋级家数` AND t.`promotion_rate` <=> s.`晋级率` AND t.`new_promotion_count` <=> s.`新晋级家数` AND t.`new_promotion_rate` <=> s.`新晋级率` AND t.`positive_count` <=> s.`红盘家数` AND t.`positive_rate` <=> s.`红盘率` AND t.`large_gain_count` <=> s.`大涨家数` AND t.`large_gain_rate` <=> s.`大涨率` AND t.`large_loss_count` <=> s.`大跌家数` AND t.`large_loss_rate` <=> s.`大跌率` AND t.`failed_limit_count` <=> s.`炸板家数` AND t.`failed_limit_rate` <=> s.`炸板率` AND t.`retained_count` <=> s.`同板块留存家数` AND t.`retained_rate` <=> s.`同板块留存率` AND t.`heat_stage` <=> s.`热度阶段` AND t.`continuation_state` <=> s.`承接情绪` AND t.`overall_status` <=> s.`综合状态` AND t.`emotion_score` <=> s.`情绪分` AND t.`decision_summary` <=> s.`判定摘要` AND t.`decision_reasons_json` <=> CASE WHEN s.`判定依据JSON` IS NULL THEN NULL ELSE CAST(s.`判定依据JSON` AS JSON) END AND t.`created_at` <=> s.`创建时间` AND t.`updated_at` <=> s.`更新时间`)),
    (SELECT COUNT(*) FROM `_004_target_keys_before` WHERE `mapping_name`='hot_board_emotion_daily'),
    (SELECT COUNT(*) FROM `hot_board_emotion_daily`),
    (SELECT COUNT(*) FROM `_004_target_keys_before` b LEFT JOIN `hot_board_emotion_daily` t ON CONVERT(CONCAT(t.`trade_date`, '|', t.`board_name`) USING utf8mb4) COLLATE utf8mb4_bin=b.`key_value` WHERE b.`mapping_name`='hot_board_emotion_daily' AND t.`trade_date` IS NULL)
  );

  SET @migration_004_mapping='stock_basic';
  CALL assert_mapping_containment(
    'stock_basic', 'securities',
    (SELECT COUNT(*) FROM `stock_basic`),
    (SELECT COUNT(DISTINCT CAST(`ts_code` AS CHAR)) FROM `stock_basic`),
    (SELECT COUNT(*) FROM `stock_basic` s LEFT JOIN `securities` t ON CONVERT(t.`ts_code` USING utf8mb4) COLLATE utf8mb4_bin=CONVERT(CAST(s.`ts_code` AS CHAR) USING utf8mb4) COLLATE utf8mb4_bin WHERE t.`ts_code` IS NULL),
    (SELECT COUNT(*) FROM `stock_basic` s JOIN `securities` t ON CONVERT(t.`ts_code` USING utf8mb4) COLLATE utf8mb4_bin=CONVERT(CAST(s.`ts_code` AS CHAR) USING utf8mb4) COLLATE utf8mb4_bin WHERE NOT (t.`symbol` <=> LPAD(CAST(s.`symbol` AS CHAR), 6, '0') AND t.`name` <=> s.`name` AND t.`area` <=> s.`area` AND t.`industry` <=> s.`industry` AND t.`market` <=> s.`market` AND t.`list_date` <=> CAST(s.`list_date` AS UNSIGNED) AND t.`list_status` <=> s.`list_status`)),
    (SELECT COUNT(*) FROM `_004_target_keys_before` WHERE `mapping_name`='securities'),
    (SELECT COUNT(*) FROM `securities`),
    (SELECT COUNT(*) FROM `_004_target_keys_before` b LEFT JOIN `securities` t ON CONVERT(t.`ts_code` USING utf8mb4) COLLATE utf8mb4_bin=b.`key_value` WHERE b.`mapping_name`='securities' AND t.`ts_code` IS NULL)
  );

  SET @migration_004_mapping='stock_daily';
  CALL assert_mapping_containment(
    'stock_daily', 'daily_quotes',
    (SELECT COUNT(*) FROM `stock_daily`),
    (SELECT COUNT(DISTINCT CONCAT(CASE WHEN LEFT(LPAD(`ts_code`,6,'0'),1) IN ('4','8') THEN CONCAT(LPAD(`ts_code`,6,'0'),'.BJ') WHEN CAST(`ts_code` AS UNSIGNED)>=600000 THEN CONCAT(LPAD(`ts_code`,6,'0'),'.SH') ELSE CONCAT(LPAD(`ts_code`,6,'0'),'.SZ') END,'_',`trade_date`)) FROM `stock_daily`),
    (SELECT COUNT(*) FROM `stock_daily` s LEFT JOIN `daily_quotes` t ON CONVERT(t.`data_id` USING utf8mb4) COLLATE utf8mb4_bin=CONVERT(CONCAT(CASE WHEN LEFT(LPAD(s.`ts_code`,6,'0'),1) IN ('4','8') THEN CONCAT(LPAD(s.`ts_code`,6,'0'),'.BJ') WHEN CAST(s.`ts_code` AS UNSIGNED)>=600000 THEN CONCAT(LPAD(s.`ts_code`,6,'0'),'.SH') ELSE CONCAT(LPAD(s.`ts_code`,6,'0'),'.SZ') END,'_',s.`trade_date`) USING utf8mb4) COLLATE utf8mb4_bin WHERE t.`data_id` IS NULL),
    (SELECT COUNT(*) FROM `stock_daily` s JOIN `daily_quotes` t ON CONVERT(t.`data_id` USING utf8mb4) COLLATE utf8mb4_bin=CONVERT(CONCAT(CASE WHEN LEFT(LPAD(s.`ts_code`,6,'0'),1) IN ('4','8') THEN CONCAT(LPAD(s.`ts_code`,6,'0'),'.BJ') WHEN CAST(s.`ts_code` AS UNSIGNED)>=600000 THEN CONCAT(LPAD(s.`ts_code`,6,'0'),'.SH') ELSE CONCAT(LPAD(s.`ts_code`,6,'0'),'.SZ') END,'_',s.`trade_date`) USING utf8mb4) COLLATE utf8mb4_bin WHERE NOT (t.`ts_code` <=> CASE WHEN LEFT(LPAD(s.`ts_code`,6,'0'),1) IN ('4','8') THEN CONCAT(LPAD(s.`ts_code`,6,'0'),'.BJ') WHEN CAST(s.`ts_code` AS UNSIGNED)>=600000 THEN CONCAT(LPAD(s.`ts_code`,6,'0'),'.SH') ELSE CONCAT(LPAD(s.`ts_code`,6,'0'),'.SZ') END AND t.`trade_date` <=> s.`trade_date` AND t.`open_price` <=> s.`open` AND t.`high_price` <=> s.`high` AND t.`low_price` <=> s.`low` AND t.`close_price` <=> s.`close` AND t.`previous_close` <=> s.`pre_close` AND t.`change_amount` <=> s.`change` AND t.`change_pct` <=> s.`pct_chg` AND t.`volume` <=> s.`vol` AND t.`turnover` <=> s.`amount` AND t.`total_market_value` <=> s.`total_mv` AND t.`circulating_market_value` <=> s.`circ_mv` AND t.`free_float_shares` <=> s.`free_share` AND t.`free_float_market_value` <=> s.`free_mv` AND t.`stock_name` <=> s.`stock_name` AND t.`dde_net_amount` <=> s.`dde`)),
    (SELECT COUNT(*) FROM `_004_target_keys_before` WHERE `mapping_name`='daily_quotes'),
    (SELECT COUNT(*) FROM `daily_quotes`),
    (SELECT COUNT(*) FROM `_004_target_keys_before` b LEFT JOIN `daily_quotes` t ON CONVERT(t.`data_id` USING utf8mb4) COLLATE utf8mb4_bin=b.`key_value` WHERE b.`mapping_name`='daily_quotes' AND t.`data_id` IS NULL)
  );

  SET @migration_004_mapping='stock_kdj';
  CALL assert_mapping_containment(
    'stock_kdj', 'kdj_indicators',
    (SELECT COUNT(*) FROM `stock_kdj`),
    (SELECT COUNT(DISTINCT CONCAT(CASE WHEN LEFT(LPAD(`ts_code`,6,'0'),1) IN ('4','8') THEN CONCAT(LPAD(`ts_code`,6,'0'),'.BJ') WHEN CAST(`ts_code` AS UNSIGNED)>=600000 THEN CONCAT(LPAD(`ts_code`,6,'0'),'.SH') ELSE CONCAT(LPAD(`ts_code`,6,'0'),'.SZ') END,'_',`trade_date`)) FROM `stock_kdj`),
    (SELECT COUNT(*) FROM `stock_kdj` s LEFT JOIN `kdj_indicators` t ON CONVERT(t.`data_id` USING utf8mb4) COLLATE utf8mb4_bin=CONVERT(CONCAT(CASE WHEN LEFT(LPAD(s.`ts_code`,6,'0'),1) IN ('4','8') THEN CONCAT(LPAD(s.`ts_code`,6,'0'),'.BJ') WHEN CAST(s.`ts_code` AS UNSIGNED)>=600000 THEN CONCAT(LPAD(s.`ts_code`,6,'0'),'.SH') ELSE CONCAT(LPAD(s.`ts_code`,6,'0'),'.SZ') END,'_',s.`trade_date`) USING utf8mb4) COLLATE utf8mb4_bin WHERE t.`data_id` IS NULL),
    (SELECT COUNT(*) FROM `stock_kdj` s JOIN `kdj_indicators` t ON CONVERT(t.`data_id` USING utf8mb4) COLLATE utf8mb4_bin=CONVERT(CONCAT(CASE WHEN LEFT(LPAD(s.`ts_code`,6,'0'),1) IN ('4','8') THEN CONCAT(LPAD(s.`ts_code`,6,'0'),'.BJ') WHEN CAST(s.`ts_code` AS UNSIGNED)>=600000 THEN CONCAT(LPAD(s.`ts_code`,6,'0'),'.SH') ELSE CONCAT(LPAD(s.`ts_code`,6,'0'),'.SZ') END,'_',s.`trade_date`) USING utf8mb4) COLLATE utf8mb4_bin WHERE NOT (t.`ts_code` <=> CASE WHEN LEFT(LPAD(s.`ts_code`,6,'0'),1) IN ('4','8') THEN CONCAT(LPAD(s.`ts_code`,6,'0'),'.BJ') WHEN CAST(s.`ts_code` AS UNSIGNED)>=600000 THEN CONCAT(LPAD(s.`ts_code`,6,'0'),'.SH') ELSE CONCAT(LPAD(s.`ts_code`,6,'0'),'.SZ') END AND t.`trade_date` <=> s.`trade_date` AND t.`k_value` <=> s.`k` AND t.`d_value` <=> s.`d` AND t.`j_value` <=> s.`j`)),
    (SELECT COUNT(*) FROM `_004_target_keys_before` WHERE `mapping_name`='kdj_indicators'),
    (SELECT COUNT(*) FROM `kdj_indicators`),
    (SELECT COUNT(*) FROM `_004_target_keys_before` b LEFT JOIN `kdj_indicators` t ON CONVERT(t.`data_id` USING utf8mb4) COLLATE utf8mb4_bin=b.`key_value` WHERE b.`mapping_name`='kdj_indicators' AND t.`data_id` IS NULL)
  );

  SET @migration_004_mapping='t_stock_5_min_k';
  CALL assert_mapping_containment(
    't_stock_5_min_k', 'intraday_bars_5m',
    (SELECT COUNT(*) FROM `t_stock_5_min_k`),
    (SELECT COUNT(DISTINCT CONCAT(LPAD(CAST(`code` AS CHAR),6,'0'),'_',`time`,'_',`adjustflag`)) FROM `t_stock_5_min_k`),
    (SELECT COUNT(*) FROM `t_stock_5_min_k` s LEFT JOIN `intraday_bars_5m` t ON CONVERT(t.`data_id` USING utf8mb4) COLLATE utf8mb4_bin=CONVERT(CONCAT(LPAD(CAST(s.`code` AS CHAR),6,'0'),'_',s.`time`,'_',s.`adjustflag`) USING utf8mb4) COLLATE utf8mb4_bin WHERE t.`data_id` IS NULL),
    (SELECT COUNT(*) FROM `t_stock_5_min_k` s JOIN `intraday_bars_5m` t ON CONVERT(t.`data_id` USING utf8mb4) COLLATE utf8mb4_bin=CONVERT(CONCAT(LPAD(CAST(s.`code` AS CHAR),6,'0'),'_',s.`time`,'_',s.`adjustflag`) USING utf8mb4) COLLATE utf8mb4_bin WHERE NOT (t.`trade_date` <=> s.`date` AND t.`trade_time` <=> s.`time` AND t.`stock_code` <=> LPAD(CAST(s.`code` AS CHAR),6,'0') AND t.`open_price` <=> s.`open` AND t.`high_price` <=> s.`high` AND t.`low_price` <=> s.`low` AND t.`close_price` <=> s.`close` AND t.`volume` <=> s.`volume` AND t.`turnover` <=> s.`amount` AND t.`adjustment_flag` <=> s.`adjustflag`)),
    (SELECT COUNT(*) FROM `_004_target_keys_before` WHERE `mapping_name`='intraday_bars_5m'),
    (SELECT COUNT(*) FROM `intraday_bars_5m`),
    (SELECT COUNT(*) FROM `_004_target_keys_before` b LEFT JOIN `intraday_bars_5m` t ON CONVERT(t.`data_id` USING utf8mb4) COLLATE utf8mb4_bin=b.`key_value` WHERE b.`mapping_name`='intraday_bars_5m' AND t.`data_id` IS NULL)
  );

  SET @migration_004_mapping='t_韭研公社异动解析';
  CALL assert_mapping_containment(
    't_韭研公社异动解析', 'jiuyan_actions',
    (SELECT COUNT(*) FROM `t_韭研公社异动解析`),
    (SELECT COUNT(DISTINCT `data_id`) FROM `t_韭研公社异动解析`),
    (SELECT COUNT(*) FROM `t_韭研公社异动解析` s LEFT JOIN `jiuyan_actions` t ON CONVERT(t.`data_id` USING utf8mb4) COLLATE utf8mb4_bin=CONVERT(s.`data_id` USING utf8mb4) COLLATE utf8mb4_bin WHERE t.`data_id` IS NULL),
    (SELECT COUNT(*) FROM `t_韭研公社异动解析` s JOIN `jiuyan_actions` t ON CONVERT(t.`data_id` USING utf8mb4) COLLATE utf8mb4_bin=CONVERT(s.`data_id` USING utf8mb4) COLLATE utf8mb4_bin WHERE NOT (t.`trade_date` <=> s.`date` AND CAST(t.`board_name` AS BINARY) <=> CAST(s.`板块` AS BINARY) AND t.`board_stock_count` <=> s.`板块个股数量` AND CAST(t.`stock_code` AS BINARY) <=> CAST(LPAD(CAST(s.`股票代码` AS CHAR),6,'0') AS BINARY) AND CAST(t.`stock_name` AS BINARY) <=> CAST(s.`股票名称` AS BINARY) AND CAST(t.`source_code` AS BINARY) <=> CAST(s.`code` AS BINARY) AND t.`limit_up_at` <=> s.`涨停时间` AND CAST(t.`board_streak` AS BINARY) <=> CAST(s.`几天几板` AS BINARY) AND t.`change_pct` <=> s.`涨幅` AND CAST(t.`limit_up_reason` AS BINARY) <=> CAST(s.`涨停解析` AS BINARY))),
    (SELECT COUNT(*) FROM `_004_target_keys_before` WHERE `mapping_name`='jiuyan_actions'),
    (SELECT COUNT(*) FROM `jiuyan_actions`),
    (SELECT COUNT(*) FROM `_004_target_keys_before` b LEFT JOIN `jiuyan_actions` t ON CONVERT(t.`data_id` USING utf8mb4) COLLATE utf8mb4_bin=b.`key_value` WHERE b.`mapping_name`='jiuyan_actions' AND t.`data_id` IS NULL)
  );

  SET @migration_004_mapping='t_龙虎榜';
  CALL assert_mapping_containment(
    't_龙虎榜', 'dragon_tiger',
    (SELECT COUNT(*) FROM `t_龙虎榜`),
    (SELECT COUNT(DISTINCT `data_id`) FROM `t_龙虎榜`),
    (SELECT COUNT(*) FROM `t_龙虎榜` s LEFT JOIN `dragon_tiger` t ON CONVERT(t.`data_id` USING utf8mb4) COLLATE utf8mb4_bin=CONVERT(s.`data_id` USING utf8mb4) COLLATE utf8mb4_bin WHERE t.`data_id` IS NULL),
    (SELECT COUNT(*) FROM `t_龙虎榜` s JOIN `dragon_tiger` t ON CONVERT(t.`data_id` USING utf8mb4) COLLATE utf8mb4_bin=CONVERT(s.`data_id` USING utf8mb4) COLLATE utf8mb4_bin WHERE NOT (t.`trade_date` <=> s.`date` AND t.`source_id` <=> s.`rid` AND t.`detail_type` <=> s.`明细` AND t.`date_type` <=> s.`日期类型` AND t.`stock_code` <=> s.`股票代码` AND t.`stock_name` <=> s.`股票名称` AND t.`current_price` <=> s.`现价` AND t.`change_pct` <=> s.`涨跌幅` AND t.`turnover` <=> s.`成交金额` AND t.`net_buy_amount` <=> s.`净买入额` AND t.`total_buy_amount` <=> s.`合计买入` AND t.`total_sell_amount` <=> s.`合计卖出` AND t.`buy_1_broker_id` <=> s.`买1营业部id` AND t.`buy_1_broker_name` <=> s.`买1营业部` AND t.`buy_1_buy_amount` <=> s.`买1买入额` AND t.`buy_1_sell_amount` <=> s.`买1卖出额` AND t.`buy_1_net_amount` <=> s.`买1净额` AND t.`buy_2_broker_id` <=> s.`买2营业部id` AND t.`buy_2_broker_name` <=> s.`买2营业部` AND t.`buy_2_buy_amount` <=> s.`买2买入额` AND t.`buy_2_sell_amount` <=> s.`买2卖出额` AND t.`buy_2_net_amount` <=> s.`买2净额` AND t.`buy_3_broker_id` <=> s.`买3营业部id` AND t.`buy_3_broker_name` <=> s.`买3营业部` AND t.`buy_3_buy_amount` <=> s.`买3买入额` AND t.`buy_3_sell_amount` <=> s.`买3卖出额` AND t.`buy_3_net_amount` <=> s.`买3净额` AND t.`buy_4_broker_id` <=> s.`买4营业部id` AND t.`buy_4_broker_name` <=> s.`买4营业部` AND t.`buy_4_buy_amount` <=> s.`买4买入额` AND t.`buy_4_sell_amount` <=> s.`买4卖出额` AND t.`buy_4_net_amount` <=> s.`买4净额` AND t.`buy_5_broker_id` <=> s.`买5营业部id` AND t.`buy_5_broker_name` <=> s.`买5营业部` AND t.`buy_5_buy_amount` <=> s.`买5买入额` AND t.`buy_5_sell_amount` <=> s.`买5卖出额` AND t.`buy_5_net_amount` <=> s.`买5净额` AND t.`sell_1_broker_id` <=> s.`卖1营业部id` AND t.`sell_1_broker_name` <=> s.`卖1营业部` AND t.`sell_1_buy_amount` <=> s.`卖1买入额` AND t.`sell_1_sell_amount` <=> s.`卖1卖出额` AND t.`sell_1_net_amount` <=> s.`卖1净额` AND t.`sell_2_broker_id` <=> s.`卖2营业部id` AND t.`sell_2_broker_name` <=> s.`卖2营业部` AND t.`sell_2_buy_amount` <=> s.`卖2买入额` AND t.`sell_2_sell_amount` <=> s.`卖2卖出额` AND t.`sell_2_net_amount` <=> s.`卖2净额` AND t.`sell_3_broker_id` <=> s.`卖3营业部id` AND t.`sell_3_broker_name` <=> s.`卖3营业部` AND t.`sell_3_buy_amount` <=> s.`卖3买入额` AND t.`sell_3_sell_amount` <=> s.`卖3卖出额` AND t.`sell_3_net_amount` <=> s.`卖3净额` AND t.`sell_4_broker_id` <=> s.`卖4营业部id` AND t.`sell_4_broker_name` <=> s.`卖4营业部` AND t.`sell_4_buy_amount` <=> s.`卖4买入额` AND t.`sell_4_sell_amount` <=> s.`卖4卖出额` AND t.`sell_4_net_amount` <=> s.`卖4净额` AND t.`sell_5_broker_id` <=> s.`卖5营业部id` AND t.`sell_5_broker_name` <=> s.`卖5营业部` AND t.`sell_5_buy_amount` <=> s.`卖5买入额` AND t.`sell_5_sell_amount` <=> s.`卖5卖出额` AND t.`sell_5_net_amount` <=> s.`卖5净额`)),
    (SELECT COUNT(*) FROM `_004_target_keys_before` WHERE `mapping_name`='dragon_tiger'),
    (SELECT COUNT(*) FROM `dragon_tiger`),
    (SELECT COUNT(*) FROM `_004_target_keys_before` b LEFT JOIN `dragon_tiger` t ON CONVERT(t.`data_id` USING utf8mb4) COLLATE utf8mb4_bin=b.`key_value` WHERE b.`mapping_name`='dragon_tiger' AND t.`data_id` IS NULL)
  );

  SET @migration_004_mapping='t_龙虎榜_营业部_上榜历史数据';
  CALL assert_mapping_containment(
    't_龙虎榜_营业部_上榜历史数据', 'broker_listing_history',
    (SELECT COUNT(*) FROM `t_龙虎榜_营业部_上榜历史数据`),
    (SELECT COUNT(DISTINCT `data_id`) FROM `t_龙虎榜_营业部_上榜历史数据`),
    (SELECT COUNT(*) FROM `t_龙虎榜_营业部_上榜历史数据` s LEFT JOIN `broker_listing_history` t ON CONVERT(t.`data_id` USING utf8mb4) COLLATE utf8mb4_bin=CONVERT(s.`data_id` USING utf8mb4) COLLATE utf8mb4_bin WHERE t.`data_id` IS NULL),
    (SELECT COUNT(*) FROM `t_龙虎榜_营业部_上榜历史数据` s JOIN `broker_listing_history` t ON CONVERT(t.`data_id` USING utf8mb4) COLLATE utf8mb4_bin=CONVERT(s.`data_id` USING utf8mb4) COLLATE utf8mb4_bin WHERE NOT (t.`broker_id` <=> s.`营业部id` AND t.`broker_name` <=> s.`营业部名称` AND t.`trade_date` <=> s.`日期` AND t.`stock_name` <=> s.`股票简称` AND t.`stock_code` <=> s.`股票代码` AND t.`listing_reason` <=> s.`上榜原因` AND t.`change_pct` <=> s.`涨跌幅` AND t.`buy_amount` <=> s.`买入额` AND t.`sell_amount` <=> s.`卖出额` AND t.`net_amount` <=> s.`买卖净额` AND t.`board_name` <=> s.`所属板块`)),
    (SELECT COUNT(*) FROM `_004_target_keys_before` WHERE `mapping_name`='broker_listing_history'),
    (SELECT COUNT(*) FROM `broker_listing_history`),
    (SELECT COUNT(*) FROM `_004_target_keys_before` b LEFT JOIN `broker_listing_history` t ON CONVERT(t.`data_id` USING utf8mb4) COLLATE utf8mb4_bin=b.`key_value` WHERE b.`mapping_name`='broker_listing_history' AND t.`data_id` IS NULL)
  );

  SET @migration_004_mapping='t_龙虎榜_营业部_上榜次数最多';
  CALL assert_mapping_containment(
    't_龙虎榜_营业部_上榜次数最多', 'broker_top_stats',
    (SELECT COUNT(*) FROM `t_龙虎榜_营业部_上榜次数最多`),
    (SELECT COUNT(DISTINCT CAST(`营业部id` AS CHAR)) FROM `t_龙虎榜_营业部_上榜次数最多`),
    (SELECT COUNT(*) FROM `t_龙虎榜_营业部_上榜次数最多` s LEFT JOIN `broker_top_stats` t ON CONVERT(t.`broker_id` USING utf8mb4) COLLATE utf8mb4_bin=CONVERT(CAST(s.`营业部id` AS CHAR) USING utf8mb4) COLLATE utf8mb4_bin WHERE t.`broker_id` IS NULL),
    (SELECT COUNT(*) FROM `t_龙虎榜_营业部_上榜次数最多` s JOIN `broker_top_stats` t ON CONVERT(t.`broker_id` USING utf8mb4) COLLATE utf8mb4_bin=CONVERT(CAST(s.`营业部id` AS CHAR) USING utf8mb4) COLLATE utf8mb4_bin WHERE NOT (t.`broker_name` <=> s.`营业部名称` AND t.`listing_count` <=> CASE WHEN NULLIF(TRIM(CAST(s.`上榜次数` AS CHAR)),'') IS NULL THEN NULL ELSE CAST(REPLACE(REGEXP_REPLACE(TRIM(CAST(s.`上榜次数` AS CHAR)),'(次|家|只)$',''),',','') AS UNSIGNED) END AND t.`total_capital_used` <=> CASE WHEN NULLIF(TRIM(CAST(s.`合计动用资金` AS CHAR)),'') IS NULL THEN NULL ELSE CAST(REPLACE(REGEXP_REPLACE(TRIM(CAST(s.`合计动用资金` AS CHAR)),'(元|万|万元|亿|亿元)$',''),',','') AS DECIMAL(30,4)) * CASE WHEN REGEXP_LIKE(TRIM(CAST(s.`合计动用资金` AS CHAR)),'亿(元)?$') THEN 100000000 WHEN REGEXP_LIKE(TRIM(CAST(s.`合计动用资金` AS CHAR)),'万(元)?$') THEN 10000 ELSE 1 END END AND t.`year_listing_count` <=> CASE WHEN NULLIF(TRIM(CAST(s.`年内上榜次数` AS CHAR)),'') IS NULL THEN NULL ELSE CAST(REPLACE(REGEXP_REPLACE(TRIM(CAST(s.`年内上榜次数` AS CHAR)),'(次|家|只)$',''),',','') AS UNSIGNED) END AND t.`year_stock_count` <=> CASE WHEN NULLIF(TRIM(CAST(s.`年内买入股票只数` AS CHAR)),'') IS NULL THEN NULL ELSE CAST(REPLACE(REGEXP_REPLACE(TRIM(CAST(s.`年内买入股票只数` AS CHAR)),'(次|家|只)$',''),',','') AS UNSIGNED) END AND t.`three_day_follow_success_rate` <=> CASE WHEN NULLIF(TRIM(CAST(s.`年内3日跟买成功率` AS CHAR)),'') IS NULL THEN NULL ELSE CAST(REPLACE(REPLACE(TRIM(CAST(s.`年内3日跟买成功率` AS CHAR)),',',''),'%','') AS DECIMAL(10,4)) END)),
    (SELECT COUNT(*) FROM `_004_target_keys_before` WHERE `mapping_name`='broker_top_stats'),
    (SELECT COUNT(*) FROM `broker_top_stats`),
    (SELECT COUNT(*) FROM `_004_target_keys_before` b LEFT JOIN `broker_top_stats` t ON CONVERT(t.`broker_id` USING utf8mb4) COLLATE utf8mb4_bin=b.`key_value` WHERE b.`mapping_name`='broker_top_stats' AND t.`broker_id` IS NULL)
  );

  SET @migration_004_mapping='t_龙虎榜_营业部_全部';
  CALL assert_mapping_containment(
    't_龙虎榜_营业部_全部', 'brokers',
    (SELECT COUNT(*) FROM `t_龙虎榜_营业部_全部`),
    (SELECT COUNT(DISTINCT CAST(`营业部id` AS CHAR)) FROM `t_龙虎榜_营业部_全部`),
    (SELECT COUNT(*) FROM `t_龙虎榜_营业部_全部` s LEFT JOIN `brokers` t ON CONVERT(t.`broker_id` USING utf8mb4) COLLATE utf8mb4_bin=CONVERT(CAST(s.`营业部id` AS CHAR) USING utf8mb4) COLLATE utf8mb4_bin WHERE t.`broker_id` IS NULL),
    (SELECT COUNT(*) FROM `t_龙虎榜_营业部_全部` s JOIN `brokers` t ON CONVERT(t.`broker_id` USING utf8mb4) COLLATE utf8mb4_bin=CONVERT(CAST(s.`营业部id` AS CHAR) USING utf8mb4) COLLATE utf8mb4_bin WHERE NOT (t.`broker_name` <=> s.`营业部名称`)),
    (SELECT COUNT(*) FROM `_004_target_keys_before` WHERE `mapping_name`='brokers'),
    (SELECT COUNT(*) FROM `brokers`),
    (SELECT COUNT(*) FROM `_004_target_keys_before` b LEFT JOIN `brokers` t ON CONVERT(t.`broker_id` USING utf8mb4) COLLATE utf8mb4_bin=b.`key_value` WHERE b.`mapping_name`='brokers' AND t.`broker_id` IS NULL)
  );

  SET @migration_004_mapping='t_同花顺板块列表';
  CALL assert_mapping_containment(
    't_同花顺板块列表', 'ths_boards',
    (SELECT COUNT(*) FROM `t_同花顺板块列表`),
    (SELECT COUNT(DISTINCT `板块代码`) FROM `t_同花顺板块列表`),
    (SELECT COUNT(*) FROM `t_同花顺板块列表` s LEFT JOIN `ths_boards` t ON CONVERT(t.`board_code` USING utf8mb4) COLLATE utf8mb4_bin=CONVERT(s.`板块代码` USING utf8mb4) COLLATE utf8mb4_bin WHERE t.`board_code` IS NULL),
    (SELECT COUNT(*) FROM `t_同花顺板块列表` s JOIN `ths_boards` t ON CONVERT(t.`board_code` USING utf8mb4) COLLATE utf8mb4_bin=CONVERT(s.`板块代码` USING utf8mb4) COLLATE utf8mb4_bin WHERE NOT (CAST(t.`board_type` AS BINARY) <=> CAST(s.`板块类型` AS BINARY) AND CAST(t.`board_name` AS BINARY) <=> CAST(s.`板块名称` AS BINARY) AND CAST(t.`page_code` AS BINARY) <=> CAST(s.`页面代码` AS BINARY) AND CAST(t.`detail_path` AS BINARY) <=> CAST(s.`详情路径` AS BINARY) AND t.`collected_date` <=> s.`采集日期` AND t.`updated_at` <=> s.`更新时间`)),
    (SELECT COUNT(*) FROM `_004_target_keys_before` WHERE `mapping_name`='ths_boards'),
    (SELECT COUNT(*) FROM `ths_boards`),
    (SELECT COUNT(*) FROM `_004_target_keys_before` b LEFT JOIN `ths_boards` t ON CONVERT(t.`board_code` USING utf8mb4) COLLATE utf8mb4_bin=b.`key_value` WHERE b.`mapping_name`='ths_boards' AND t.`board_code` IS NULL)
  );

  SET @migration_004_mapping='t_同花顺板块成分股';
  CALL assert_mapping_containment(
    't_同花顺板块成分股', 'ths_board_constituents',
    (SELECT COUNT(*) FROM `t_同花顺板块成分股`),
    (SELECT COUNT(DISTINCT CONCAT(`板块代码`,'|',`股票代码`)) FROM `t_同花顺板块成分股`),
    (SELECT COUNT(*) FROM `t_同花顺板块成分股` s LEFT JOIN `ths_board_constituents` t ON CONVERT(CONCAT(t.`board_code`,'|',t.`stock_code`) USING utf8mb4) COLLATE utf8mb4_bin=CONVERT(CONCAT(s.`板块代码`,'|',s.`股票代码`) USING utf8mb4) COLLATE utf8mb4_bin WHERE t.`board_code` IS NULL),
    (SELECT COUNT(*) FROM `t_同花顺板块成分股` s JOIN `ths_board_constituents` t ON CONVERT(CONCAT(t.`board_code`,'|',t.`stock_code`) USING utf8mb4) COLLATE utf8mb4_bin=CONVERT(CONCAT(s.`板块代码`,'|',s.`股票代码`) USING utf8mb4) COLLATE utf8mb4_bin WHERE NOT (CAST(t.`board_type` AS BINARY) <=> CAST(s.`板块类型` AS BINARY) AND CAST(t.`board_name` AS BINARY) <=> CAST(s.`板块名称` AS BINARY) AND CAST(t.`page_code` AS BINARY) <=> CAST(s.`页面代码` AS BINARY) AND CAST(t.`stock_name` AS BINARY) <=> CAST(s.`股票名称` AS BINARY) AND t.`collected_date` <=> s.`采集日期` AND t.`updated_at` <=> s.`更新时间`)),
    (SELECT COUNT(*) FROM `_004_target_keys_before` WHERE `mapping_name`='ths_board_constituents'),
    (SELECT COUNT(*) FROM `ths_board_constituents`),
    (SELECT COUNT(*) FROM `_004_target_keys_before` b LEFT JOIN `ths_board_constituents` t ON CONVERT(CONCAT(t.`board_code`,'|',t.`stock_code`) USING utf8mb4) COLLATE utf8mb4_bin=b.`key_value` WHERE b.`mapping_name`='ths_board_constituents' AND t.`board_code` IS NULL)
  );

  SET @migration_004_mapping='t_同花顺股票板块概念对应关系';
  CALL assert_mapping_containment(
    't_同花顺股票板块概念对应关系', 'ths_stock_relations',
    (SELECT COUNT(*) FROM `t_同花顺股票板块概念对应关系`),
    (SELECT COUNT(DISTINCT `股票代码`) FROM `t_同花顺股票板块概念对应关系`),
    (SELECT COUNT(*) FROM `t_同花顺股票板块概念对应关系` s LEFT JOIN `ths_stock_relations` t ON CONVERT(t.`stock_code` USING utf8mb4) COLLATE utf8mb4_bin=CONVERT(s.`股票代码` USING utf8mb4) COLLATE utf8mb4_bin WHERE t.`stock_code` IS NULL),
    (SELECT COUNT(*) FROM `t_同花顺股票板块概念对应关系` s JOIN `ths_stock_relations` t ON CONVERT(t.`stock_code` USING utf8mb4) COLLATE utf8mb4_bin=CONVERT(s.`股票代码` USING utf8mb4) COLLATE utf8mb4_bin WHERE NOT (CAST(t.`stock_name` AS BINARY) <=> CAST(s.`股票名称` AS BINARY) AND CAST(t.`industry_names` AS BINARY) <=> CAST(s.`同花顺行业` AS BINARY) AND CAST(t.`industry_codes` AS BINARY) <=> CAST(s.`同花顺行业代码` AS BINARY) AND CAST(t.`concept_names` AS BINARY) <=> CAST(s.`同花顺概念` AS BINARY) AND CAST(t.`concept_codes` AS BINARY) <=> CAST(s.`同花顺概念代码` AS BINARY) AND t.`collected_date` <=> s.`采集日期` AND t.`updated_at` <=> s.`更新时间`)),
    (SELECT COUNT(*) FROM `_004_target_keys_before` WHERE `mapping_name`='ths_stock_relations'),
    (SELECT COUNT(*) FROM `ths_stock_relations`),
    (SELECT COUNT(*) FROM `_004_target_keys_before` b LEFT JOIN `ths_stock_relations` t ON CONVERT(t.`stock_code` USING utf8mb4) COLLATE utf8mb4_bin=b.`key_value` WHERE b.`mapping_name`='ths_stock_relations' AND t.`stock_code` IS NULL)
  );

  INSERT INTO `migration_validations` (`validation_version`, `status`, `details`)
  VALUES ('004_legacy_containment_v1', 'succeeded', 'All 16 legacy mappings upserted; containment gates passed')
  ON DUPLICATE KEY UPDATE `status`=VALUES(`status`), `validated_at`=CURRENT_TIMESTAMP, `details`=VALUES(`details`);
  INSERT INTO `schema_migrations` (`version`) VALUES ('004_upsert_legacy_data')
  ON DUPLICATE KEY UPDATE `applied_at`=`applied_at`;
  UPDATE `migration_cutover_runs`
  SET `status`='succeeded', `completed_at`=CURRENT_TIMESTAMP, `details`='All 16 containment gates passed'
  WHERE `run_id`=@migration_004_run_id;
  COMMIT;
END$$
DELIMITER ;

CALL run_migration_004();
