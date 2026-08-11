CREATE TABLE IF NOT EXISTS `jiuyan_collection_days` (
  `trade_date` int NOT NULL,
  `row_count` int NOT NULL,
  `status` varchar(16) NOT NULL,
  `updated_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`trade_date`),
  KEY `idx_jiuyan_collection_status_date` (`status`, `trade_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
