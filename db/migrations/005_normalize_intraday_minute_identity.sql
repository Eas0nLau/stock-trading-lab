SET NAMES utf8mb4;

DELIMITER $$
DROP PROCEDURE IF EXISTS `run_migration_005`$$
CREATE PROCEDURE `run_migration_005`()
BEGIN
  DECLARE source_count BIGINT DEFAULT 0;
  DECLARE normalized_count BIGINT DEFAULT 0;
  DECLARE target_count BIGINT DEFAULT 0;

  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    DROP TEMPORARY TABLE IF EXISTS `intraday_bars_5m_minute_normalized`;
    INSERT INTO `migration_validations` (
      `validation_version`, `status`, `details`
    ) VALUES (
      '005_intraday_minute_identity_v1',
      'failed',
      'Minute-identity normalization rolled back'
    )
    ON DUPLICATE KEY UPDATE
      `status` = VALUES(`status`),
      `validated_at` = CURRENT_TIMESTAMP,
      `details` = VALUES(`details`);
    RESIGNAL;
  END;

  SET TRANSACTION ISOLATION LEVEL SERIALIZABLE;
  START TRANSACTION;

  DROP TEMPORARY TABLE IF EXISTS `intraday_bars_5m_minute_normalized`;

  CREATE TEMPORARY TABLE `intraday_bars_5m_minute_normalized`
  LIKE `intraday_bars_5m`;

  INSERT INTO `intraday_bars_5m_minute_normalized` (
    `data_id`, `trade_date`, `trade_time`, `stock_code`, `open_price`,
    `high_price`, `low_price`, `close_price`, `volume`, `turnover`,
    `adjustment_flag`
  )
  SELECT
    CONCAT(
      `stock_code`, '_', LEFT(CAST(`trade_time` AS CHAR), 12), '_',
      `adjustment_flag`
    ),
    `trade_date`,
    CAST(LEFT(CAST(`trade_time` AS CHAR), 12) AS UNSIGNED),
    `stock_code`, `open_price`, `high_price`, `low_price`, `close_price`,
    `volume`, `turnover`, `adjustment_flag`
  FROM `intraday_bars_5m`
  ORDER BY CHAR_LENGTH(CAST(`trade_time` AS CHAR)), `trade_time`
  ON DUPLICATE KEY UPDATE
    `trade_date` = VALUES(`trade_date`),
    `trade_time` = VALUES(`trade_time`),
    `stock_code` = VALUES(`stock_code`),
    `open_price` = VALUES(`open_price`),
    `high_price` = VALUES(`high_price`),
    `low_price` = VALUES(`low_price`),
    `close_price` = VALUES(`close_price`),
    `volume` = VALUES(`volume`),
    `turnover` = VALUES(`turnover`),
    `adjustment_flag` = VALUES(`adjustment_flag`);

  SELECT COUNT(*) INTO source_count FROM `intraday_bars_5m`;
  SELECT COUNT(*) INTO normalized_count
  FROM `intraday_bars_5m_minute_normalized`;

  IF normalized_count > source_count
     OR (source_count > 0 AND normalized_count = 0) THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Invalid intraday minute normalization counts';
  END IF;

  DELETE FROM `intraday_bars_5m`;

  INSERT INTO `intraday_bars_5m` (
    `data_id`, `trade_date`, `trade_time`, `stock_code`, `open_price`,
    `high_price`, `low_price`, `close_price`, `volume`, `turnover`,
    `adjustment_flag`
  )
  SELECT
    `data_id`, `trade_date`, `trade_time`, `stock_code`, `open_price`,
    `high_price`, `low_price`, `close_price`, `volume`, `turnover`,
    `adjustment_flag`
  FROM `intraday_bars_5m_minute_normalized`;

  SELECT COUNT(*) INTO target_count FROM `intraday_bars_5m`;
  IF target_count <> normalized_count THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Intraday minute normalization target mismatch';
  END IF;

  INSERT INTO `migration_validations` (
    `validation_version`, `status`, `details`
  ) VALUES (
    '005_intraday_minute_identity_v1',
    'succeeded',
    CONCAT(
      'source=', source_count,
      ', normalized=', normalized_count,
      ', target=', target_count
    )
  )
  ON DUPLICATE KEY UPDATE
    `status` = VALUES(`status`),
    `validated_at` = CURRENT_TIMESTAMP,
    `details` = VALUES(`details`);

  INSERT INTO `schema_migrations` (`version`)
  VALUES ('005_normalize_intraday_minute_identity')
  ON DUPLICATE KEY UPDATE `applied_at` = `applied_at`;

  COMMIT;
  DROP TEMPORARY TABLE `intraday_bars_5m_minute_normalized`;
END$$
DELIMITER ;

CALL `run_migration_005`();
