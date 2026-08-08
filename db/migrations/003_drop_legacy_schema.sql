-- Destructive finalization. Run only after backup, module cutover, and validation.
DROP PROCEDURE IF EXISTS guard_legacy_drop;

DELIMITER $$
CREATE PROCEDURE guard_legacy_drop()
BEGIN
  DECLARE v_state_tables int DEFAULT 0;
  DECLARE v_required_versions int DEFAULT 0;
  DECLARE v_successful_validation int DEFAULT 0;

  SELECT COUNT(*) INTO v_state_tables
  FROM `information_schema`.`TABLES`
  WHERE `TABLE_SCHEMA` = DATABASE()
    AND `TABLE_NAME` IN ('schema_migrations', 'migration_validations');
  IF v_state_tables <> 2 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Legacy drop requires migration state tables from 001';
  END IF;

  SELECT COUNT(*) INTO v_required_versions
  FROM `schema_migrations`
  WHERE `version` IN ('001_create_english_schema', '002_migrate_legacy_data');
  IF v_required_versions <> 2 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Legacy drop requires successful migrations 001 and 002';
  END IF;

  SELECT COUNT(*) INTO v_successful_validation
  FROM `migration_validations`
  WHERE `validation_version` = '002_parity_v1' AND `status` = 'succeeded';
  IF v_successful_validation <> 1 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Legacy drop requires validation 002_parity_v1 with succeeded status';
  END IF;
END$$
DELIMITER ;

CALL guard_legacy_drop();
DROP PROCEDURE guard_legacy_drop;

SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS `akshare_sh000001`;
DROP TABLE IF EXISTS `t_指数情绪周期_市场宽度`;
DROP TABLE IF EXISTS `t_指数情绪周期_每日分析`;
DROP TABLE IF EXISTS `t_热门板块情绪_每日分析`;
DROP TABLE IF EXISTS `stock_basic`;
DROP TABLE IF EXISTS `stock_daily`;
DROP TABLE IF EXISTS `stock_kdj`;
DROP TABLE IF EXISTS `t_stock_5_min_k`;
DROP TABLE IF EXISTS `t_韭研公社异动解析`;
DROP TABLE IF EXISTS `t_龙虎榜`;
DROP TABLE IF EXISTS `t_龙虎榜_营业部_上榜历史数据`;
DROP TABLE IF EXISTS `t_龙虎榜_营业部_上榜次数最多`;
DROP TABLE IF EXISTS `t_龙虎榜_营业部_全部`;
DROP TABLE IF EXISTS `t_同花顺板块列表`;
DROP TABLE IF EXISTS `t_同花顺板块成分股`;
DROP TABLE IF EXISTS `t_同花顺股票板块概念对应关系`;
INSERT INTO `schema_migrations` (`version`) VALUES ('003_drop_legacy_schema')
ON DUPLICATE KEY UPDATE `applied_at`=`applied_at`;
SET FOREIGN_KEY_CHECKS = 1;
