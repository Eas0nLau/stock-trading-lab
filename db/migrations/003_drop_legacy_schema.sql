-- Destructive finalization. Run only after backup, module cutover, and validation.
DROP PROCEDURE IF EXISTS guard_legacy_drop;

DELIMITER $$
CREATE PROCEDURE guard_legacy_drop()
BEGIN
  DECLARE v_state_tables int DEFAULT 0;
  DECLARE v_required_versions int DEFAULT 0;
  DECLARE v_successful_validation int DEFAULT 0;
  DECLARE v_successful_table_validations int DEFAULT 0;
  DECLARE v_table_validation_rows int DEFAULT 0;
  DECLARE v_latest_run_id char(36) DEFAULT NULL;

  SELECT COUNT(*) INTO v_state_tables
  FROM `information_schema`.`TABLES`
  WHERE `TABLE_SCHEMA` = DATABASE()
    AND `TABLE_NAME` IN ('schema_migrations', 'migration_validations', 'migration_validation_tables');
  IF v_state_tables <> 3 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Legacy drop requires migration state tables from 001';
  END IF;

  SELECT COUNT(*) INTO v_required_versions
  FROM `schema_migrations`
  WHERE `version` IN ('001_create_english_schema', '002_migrate_legacy_data', '004_upsert_legacy_data');
  IF v_required_versions <> 3 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Legacy drop requires successful migrations 001, 002, and 004';
  END IF;

  SELECT COUNT(*) INTO v_successful_validation
  FROM `migration_validations`
  WHERE `validation_version` = '004_legacy_containment_v1'
    AND `status` = 'succeeded'
    AND `validated_at` >= NOW() - INTERVAL 30 MINUTE;
  IF v_successful_validation <> 1 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Legacy drop requires validation 004_legacy_containment_v1 with succeeded status';
  END IF;

  SELECT `run_id` INTO v_latest_run_id
  FROM `migration_cutover_runs`
  WHERE `validation_version`='004_legacy_containment_v1'
    AND `status`='succeeded'
    AND `completed_at` >= NOW() - INTERVAL 30 MINUTE
  ORDER BY `completed_at` DESC
  LIMIT 1;
  IF v_latest_run_id IS NULL THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Legacy drop requires a fresh successful 004 run';
  END IF;

  SELECT COUNT(*) INTO v_table_validation_rows
  FROM `migration_validation_tables`
  WHERE `run_id`=v_latest_run_id;
  IF v_table_validation_rows <> 16 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Legacy drop requires exactly 16 table validation rows';
  END IF;

  SELECT COUNT(*) INTO v_successful_table_validations
  FROM (
    SELECT 'akshare_sh000001' AS source_table, 'index_daily' AS target_table, (SELECT COUNT(*) FROM `akshare_sh000001`) AS current_source_rows
    UNION ALL SELECT 't_指数情绪周期_市场宽度', 'index_market_breadth', (SELECT COUNT(*) FROM `t_指数情绪周期_市场宽度`)
    UNION ALL SELECT 't_指数情绪周期_每日分析', 'index_emotion_daily', (SELECT COUNT(*) FROM `t_指数情绪周期_每日分析`)
    UNION ALL SELECT 't_热门板块情绪_每日分析', 'hot_board_emotion_daily', (SELECT COUNT(*) FROM `t_热门板块情绪_每日分析`)
    UNION ALL SELECT 'stock_basic', 'securities', (SELECT COUNT(*) FROM `stock_basic`)
    UNION ALL SELECT 'stock_daily', 'daily_quotes', (SELECT COUNT(*) FROM `stock_daily`)
    UNION ALL SELECT 'stock_kdj', 'kdj_indicators', (SELECT COUNT(*) FROM `stock_kdj`)
    UNION ALL SELECT 't_stock_5_min_k', 'intraday_bars_5m', (SELECT COUNT(*) FROM `t_stock_5_min_k`)
    UNION ALL SELECT 't_韭研公社异动解析', 'jiuyan_actions', (SELECT COUNT(*) FROM `t_韭研公社异动解析`)
    UNION ALL SELECT 't_龙虎榜', 'dragon_tiger', (SELECT COUNT(*) FROM `t_龙虎榜`)
    UNION ALL SELECT 't_龙虎榜_营业部_上榜历史数据', 'broker_listing_history', (SELECT COUNT(*) FROM `t_龙虎榜_营业部_上榜历史数据`)
    UNION ALL SELECT 't_龙虎榜_营业部_上榜次数最多', 'broker_top_stats', (SELECT COUNT(*) FROM `t_龙虎榜_营业部_上榜次数最多`)
    UNION ALL SELECT 't_龙虎榜_营业部_全部', 'brokers', (SELECT COUNT(*) FROM `t_龙虎榜_营业部_全部`)
    UNION ALL SELECT 't_同花顺板块列表', 'ths_boards', (SELECT COUNT(*) FROM `t_同花顺板块列表`)
    UNION ALL SELECT 't_同花顺板块成分股', 'ths_board_constituents', (SELECT COUNT(*) FROM `t_同花顺板块成分股`)
    UNION ALL SELECT 't_同花顺股票板块概念对应关系', 'ths_stock_relations', (SELECT COUNT(*) FROM `t_同花顺股票板块概念对应关系`)
  ) expected
  JOIN `migration_validation_tables` detail
    ON detail.`run_id`=v_latest_run_id
   AND detail.`source_table`=expected.source_table
   AND detail.`target_table`=expected.target_table
  WHERE detail.`validation_version` = '004_legacy_containment_v1'
    AND detail.`source_rows` = expected.current_source_rows
    AND detail.`source_rows` = detail.`source_distinct_keys`
    AND detail.`missing_target_keys` = 0
    AND detail.`mapped_field_mismatches` = 0
    AND detail.`target_rows_after` >= detail.`target_rows_before`
    AND detail.`lost_preexisting_target_keys` = 0;
  IF v_successful_table_validations <> 16 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Legacy drop requires 16 successful table containment validations';
  END IF;
END$$
DELIMITER ;

CALL run_migration_004();
CALL guard_legacy_drop();
DROP PROCEDURE guard_legacy_drop;

DROP TABLE IF EXISTS
  `akshare_sh000001`,
  `t_指数情绪周期_市场宽度`,
  `t_指数情绪周期_每日分析`,
  `t_热门板块情绪_每日分析`,
  `stock_basic`,
  `stock_daily`,
  `stock_kdj`,
  `t_stock_5_min_k`,
  `t_韭研公社异动解析`,
  `t_龙虎榜`,
  `t_龙虎榜_营业部_上榜历史数据`,
  `t_龙虎榜_营业部_上榜次数最多`,
  `t_龙虎榜_营业部_全部`,
  `t_同花顺板块列表`,
  `t_同花顺板块成分股`,
  `t_同花顺股票板块概念对应关系`;
INSERT INTO `schema_migrations` (`version`) VALUES ('003_drop_legacy_schema')
ON DUPLICATE KEY UPDATE `applied_at`=`applied_at`;
DROP PROCEDURE run_migration_004;
DROP PROCEDURE preflight_legacy_data_004;
DROP PROCEDURE assert_mapping_containment;
DROP TABLE `_004_target_keys_before`;
