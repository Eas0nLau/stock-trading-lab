SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS `jiuyan_collection_days` (
  `trade_date` int NOT NULL,
  `status` varchar(16) NOT NULL,
  `source_board_count` int NOT NULL,
  `source_stock_count` int NOT NULL,
  `accepted_stock_count` int NOT NULL,
  `source_fingerprint` varchar(64) NOT NULL,
  `collected_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`trade_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT INTO `schema_migrations` (`version`)
VALUES ('006_create_jiuyan_collection_days')
ON DUPLICATE KEY UPDATE `applied_at` = `applied_at`;
