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

DROP TEMPORARY TABLE `intraday_bars_5m_minute_normalized`;

COMMIT;
