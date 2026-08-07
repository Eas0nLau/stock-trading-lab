-- Current clean-install schema for MySQL 8. This file is self-contained.
CREATE DATABASE IF NOT EXISTS `stock_trading_lab`
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE `stock_trading_lab`;

SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS `schema_migrations` (
  `version` varchar(64) NOT NULL,
  `applied_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`version`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `migration_validations` (
  `validation_version` varchar(64) NOT NULL,
  `status` varchar(16) NOT NULL,
  `validated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `details` varchar(512) DEFAULT NULL,
  PRIMARY KEY (`validation_version`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `index_daily` (
  `trade_date` int NOT NULL,
  `open_price` double DEFAULT NULL,
  `close_price` double DEFAULT NULL,
  `high_price` double DEFAULT NULL,
  `low_price` double DEFAULT NULL,
  `volume` bigint DEFAULT NULL,
  `turnover` double DEFAULT NULL,
  `amplitude_pct` double DEFAULT NULL,
  `change_pct` double DEFAULT NULL,
  `change_amount` double DEFAULT NULL,
  `turnover_rate` double DEFAULT NULL,
  PRIMARY KEY (`trade_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `index_market_breadth` (
  `trade_date` int NOT NULL,
  `stock_count` int DEFAULT NULL,
  `advancing_count` int DEFAULT NULL,
  `declining_count` int DEFAULT NULL,
  `advance_over_5_count` int DEFAULT NULL,
  `decline_over_5_count` int DEFAULT NULL,
  `limit_up_count` int DEFAULT NULL,
  `limit_down_count` int DEFAULT NULL,
  `market_turnover` double DEFAULT NULL,
  `average_change_pct` double DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`trade_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `index_emotion_daily` (
  `trade_date` int NOT NULL,
  `index_name` varchar(32) DEFAULT '上证指数',
  `cycle_state` varchar(32) DEFAULT NULL,
  `cycle_score` double DEFAULT NULL,
  `summary` varchar(512) DEFAULT NULL,
  `open_price` double DEFAULT NULL,
  `close_price` double DEFAULT NULL,
  `high_price` double DEFAULT NULL,
  `low_price` double DEFAULT NULL,
  `change_pct` double DEFAULT NULL,
  `index_turnover` double DEFAULT NULL,
  `index_turnover_ratio` double DEFAULT NULL,
  `market_turnover_ratio` double DEFAULT NULL,
  `ma5` double DEFAULT NULL,
  `ma10` double DEFAULT NULL,
  `ma20` double DEFAULT NULL,
  `ma60` double DEFAULT NULL,
  `ma5_slope` double DEFAULT NULL,
  `ma10_slope` double DEFAULT NULL,
  `ma20_slope` double DEFAULT NULL,
  `trend_score` double DEFAULT NULL,
  `breadth_score` double DEFAULT NULL,
  `limit_structure_score` double DEFAULT NULL,
  `volume_score` double DEFAULT NULL,
  `risk_appetite_score` double DEFAULT NULL,
  `market_breadth_json` json DEFAULT NULL,
  `signals_json` json DEFAULT NULL,
  `recent_trend_json` json DEFAULT NULL,
  `volatility_chart_json` json DEFAULT NULL,
  `full_result_json` json DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`trade_date`),
  KEY `idx_index_emotion_cycle_state` (`cycle_state`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `hot_board_emotion_daily` (
  `trade_date` int NOT NULL,
  `board_name` varchar(64) NOT NULL,
  `sample_trade_date` int DEFAULT NULL,
  `previous_list_complete` tinyint NOT NULL DEFAULT 0,
  `current_list_complete` tinyint NOT NULL DEFAULT 0,
  `previous_board_count` int DEFAULT NULL,
  `previous_stock_pool_count` int DEFAULT NULL,
  `previous_detail_coverage` double DEFAULT NULL,
  `current_board_count` int DEFAULT NULL,
  `current_stock_detail_count` int DEFAULT NULL,
  `valid_sample_count` int DEFAULT NULL,
  `quote_coverage` double DEFAULT NULL,
  `average_change_pct` double DEFAULT NULL,
  `median_change_pct` double DEFAULT NULL,
  `average_amplitude_pct` double DEFAULT NULL,
  `change_stddev` double DEFAULT NULL,
  `promotion_count` int DEFAULT NULL,
  `promotion_rate` double DEFAULT NULL,
  `new_promotion_count` int DEFAULT NULL,
  `new_promotion_rate` double DEFAULT NULL,
  `positive_count` int DEFAULT NULL,
  `positive_rate` double DEFAULT NULL,
  `large_gain_count` int DEFAULT NULL,
  `large_gain_rate` double DEFAULT NULL,
  `large_loss_count` int DEFAULT NULL,
  `large_loss_rate` double DEFAULT NULL,
  `failed_limit_count` int DEFAULT NULL,
  `failed_limit_rate` double DEFAULT NULL,
  `retained_count` int DEFAULT NULL,
  `retained_rate` double DEFAULT NULL,
  `heat_stage` varchar(32) DEFAULT NULL,
  `continuation_state` varchar(32) DEFAULT NULL,
  `overall_status` varchar(32) DEFAULT NULL,
  `emotion_score` double DEFAULT NULL,
  `decision_summary` varchar(512) DEFAULT NULL,
  `decision_reasons_json` json DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`trade_date`, `board_name`),
  KEY `idx_hot_board_name_date` (`board_name`, `trade_date`),
  KEY `idx_hot_board_status_date` (`overall_status`, `trade_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `securities` (
  `ts_code` varchar(16) NOT NULL,
  `symbol` varchar(8) NOT NULL,
  `name` varchar(64) NOT NULL,
  `area` varchar(64) DEFAULT NULL,
  `industry` varchar(128) DEFAULT NULL,
  `market` varchar(32) DEFAULT NULL,
  `list_date` int DEFAULT NULL,
  `list_status` varchar(8) DEFAULT NULL,
  PRIMARY KEY (`ts_code`),
  UNIQUE KEY `uk_securities_symbol` (`symbol`),
  KEY `idx_securities_market` (`market`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `daily_quotes` (
  `data_id` varchar(64) NOT NULL,
  `ts_code` varchar(16) NOT NULL,
  `trade_date` int NOT NULL,
  `open_price` double DEFAULT NULL,
  `high_price` double DEFAULT NULL,
  `low_price` double DEFAULT NULL,
  `close_price` double DEFAULT NULL,
  `previous_close` double DEFAULT NULL,
  `change_amount` double DEFAULT NULL,
  `change_pct` double DEFAULT NULL,
  `volume` double DEFAULT NULL,
  `turnover` double DEFAULT NULL,
  `total_market_value` double DEFAULT NULL,
  `circulating_market_value` double DEFAULT NULL,
  `free_float_shares` double DEFAULT NULL,
  `free_float_market_value` double DEFAULT NULL,
  `stock_name` varchar(64) DEFAULT NULL,
  `dde_net_amount` double DEFAULT NULL,
  PRIMARY KEY (`data_id`),
  UNIQUE KEY `uk_daily_quotes_code_date` (`ts_code`, `trade_date`),
  KEY `idx_daily_quotes_date` (`trade_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `fund_flow_snapshots` (
  `snapshot_id` bigint NOT NULL AUTO_INCREMENT,
  `flow_type` varchar(16) NOT NULL,
  `trade_date` int NOT NULL,
  `collected_at` varchar(32) NOT NULL,
  `record_count` int NOT NULL DEFAULT 0,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`snapshot_id`),
  UNIQUE KEY `uk_fund_flow_snapshot_batch` (`flow_type`, `trade_date`, `collected_at`),
  KEY `idx_fund_flow_snapshot_date` (`flow_type`, `trade_date`),
  KEY `idx_fund_flow_snapshot_time` (`flow_type`, `trade_date`, `collected_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `fund_flow_records` (
  `snapshot_id` bigint NOT NULL,
  `board_code` varchar(32) NOT NULL,
  `board_name` varchar(128) NOT NULL,
  `leader` varchar(128) DEFAULT NULL,
  `net_inflow_100m` decimal(20,6) NOT NULL,
  PRIMARY KEY (`snapshot_id`, `board_code`),
  KEY `idx_fund_flow_record_board` (`board_code`),
  CONSTRAINT `fk_fund_flow_record_snapshot` FOREIGN KEY (`snapshot_id`) REFERENCES `fund_flow_snapshots` (`snapshot_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `kdj_indicators` (
  `data_id` varchar(64) NOT NULL,
  `ts_code` varchar(16) NOT NULL,
  `trade_date` int NOT NULL,
  `k_value` double DEFAULT NULL,
  `d_value` double DEFAULT NULL,
  `j_value` double DEFAULT NULL,
  PRIMARY KEY (`data_id`),
  UNIQUE KEY `uk_kdj_code_date` (`ts_code`, `trade_date`),
  KEY `idx_kdj_trade_date` (`trade_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `intraday_bars_5m` (
  `data_id` varchar(64) NOT NULL,
  `trade_date` int NOT NULL,
  `trade_time` bigint NOT NULL,
  `stock_code` varchar(16) NOT NULL,
  `open_price` double DEFAULT NULL,
  `high_price` double DEFAULT NULL,
  `low_price` double DEFAULT NULL,
  `close_price` double DEFAULT NULL,
  `volume` double DEFAULT NULL,
  `turnover` double DEFAULT NULL,
  `adjustment_flag` int DEFAULT NULL,
  PRIMARY KEY (`data_id`),
  KEY `idx_intraday_date_code` (`trade_date`, `stock_code`),
  KEY `idx_intraday_time` (`trade_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `jiuyan_actions` (
  `data_id` varchar(64) NOT NULL,
  `trade_date` int NOT NULL,
  `board_name` varchar(64) NOT NULL,
  `board_stock_count` int NOT NULL,
  `stock_code` varchar(16) NOT NULL,
  `stock_name` varchar(64) DEFAULT NULL,
  `source_code` varchar(16) DEFAULT NULL,
  `limit_up_at` datetime DEFAULT NULL,
  `board_streak` varchar(32) DEFAULT NULL,
  `change_pct` decimal(10,2) DEFAULT NULL,
  `limit_up_reason` varchar(1024) DEFAULT NULL,
  PRIMARY KEY (`data_id`),
  KEY `idx_jiuyan_trade_date` (`trade_date`),
  KEY `idx_jiuyan_board_date` (`board_name`, `trade_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `dragon_tiger` (
  `data_id` varchar(64) NOT NULL,
  `trade_date` int DEFAULT NULL,
  `source_id` varchar(64) DEFAULT NULL,
  `detail_type` varchar(128) DEFAULT NULL,
  `date_type` varchar(64) DEFAULT NULL,
  `stock_code` varchar(16) DEFAULT NULL,
  `stock_name` varchar(100) DEFAULT NULL,
  `current_price` double DEFAULT NULL,
  `change_pct` double DEFAULT NULL,
  `turnover` double DEFAULT NULL,
  `net_buy_amount` double DEFAULT NULL,
  `total_buy_amount` double DEFAULT NULL,
  `total_sell_amount` double DEFAULT NULL,
  `buy_1_broker_id` varchar(64) DEFAULT NULL,
  `buy_1_broker_name` varchar(128) DEFAULT NULL,
  `buy_1_buy_amount` double DEFAULT NULL,
  `buy_1_sell_amount` double DEFAULT NULL,
  `buy_1_net_amount` double DEFAULT NULL,
  `buy_2_broker_id` varchar(64) DEFAULT NULL,
  `buy_2_broker_name` varchar(128) DEFAULT NULL,
  `buy_2_buy_amount` double DEFAULT NULL,
  `buy_2_sell_amount` double DEFAULT NULL,
  `buy_2_net_amount` double DEFAULT NULL,
  `buy_3_broker_id` varchar(64) DEFAULT NULL,
  `buy_3_broker_name` varchar(128) DEFAULT NULL,
  `buy_3_buy_amount` double DEFAULT NULL,
  `buy_3_sell_amount` double DEFAULT NULL,
  `buy_3_net_amount` double DEFAULT NULL,
  `buy_4_broker_id` varchar(64) DEFAULT NULL,
  `buy_4_broker_name` varchar(128) DEFAULT NULL,
  `buy_4_buy_amount` double DEFAULT NULL,
  `buy_4_sell_amount` double DEFAULT NULL,
  `buy_4_net_amount` double DEFAULT NULL,
  `buy_5_broker_id` varchar(64) DEFAULT NULL,
  `buy_5_broker_name` varchar(128) DEFAULT NULL,
  `buy_5_buy_amount` double DEFAULT NULL,
  `buy_5_sell_amount` double DEFAULT NULL,
  `buy_5_net_amount` double DEFAULT NULL,
  `sell_1_broker_id` varchar(64) DEFAULT NULL,
  `sell_1_broker_name` varchar(128) DEFAULT NULL,
  `sell_1_buy_amount` double DEFAULT NULL,
  `sell_1_sell_amount` double DEFAULT NULL,
  `sell_1_net_amount` double DEFAULT NULL,
  `sell_2_broker_id` varchar(64) DEFAULT NULL,
  `sell_2_broker_name` varchar(128) DEFAULT NULL,
  `sell_2_buy_amount` double DEFAULT NULL,
  `sell_2_sell_amount` double DEFAULT NULL,
  `sell_2_net_amount` double DEFAULT NULL,
  `sell_3_broker_id` varchar(64) DEFAULT NULL,
  `sell_3_broker_name` varchar(128) DEFAULT NULL,
  `sell_3_buy_amount` double DEFAULT NULL,
  `sell_3_sell_amount` double DEFAULT NULL,
  `sell_3_net_amount` double DEFAULT NULL,
  `sell_4_broker_id` varchar(64) DEFAULT NULL,
  `sell_4_broker_name` varchar(128) DEFAULT NULL,
  `sell_4_buy_amount` double DEFAULT NULL,
  `sell_4_sell_amount` double DEFAULT NULL,
  `sell_4_net_amount` double DEFAULT NULL,
  `sell_5_broker_id` varchar(64) DEFAULT NULL,
  `sell_5_broker_name` varchar(128) DEFAULT NULL,
  `sell_5_buy_amount` double DEFAULT NULL,
  `sell_5_sell_amount` double DEFAULT NULL,
  `sell_5_net_amount` double DEFAULT NULL,
  PRIMARY KEY (`data_id`),
  KEY `idx_dragon_tiger_date_code` (`trade_date`, `stock_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `broker_listing_history` (
  `data_id` varchar(225) NOT NULL,
  `broker_id` varchar(64) DEFAULT NULL,
  `broker_name` varchar(255) DEFAULT NULL,
  `trade_date` int DEFAULT NULL,
  `stock_name` varchar(64) DEFAULT NULL,
  `stock_code` varchar(16) DEFAULT NULL,
  `listing_reason` varchar(255) DEFAULT NULL,
  `change_pct` double DEFAULT NULL,
  `buy_amount` double DEFAULT NULL,
  `sell_amount` double DEFAULT NULL,
  `net_amount` double DEFAULT NULL,
  `board_name` varchar(64) DEFAULT NULL,
  PRIMARY KEY (`data_id`),
  KEY `idx_broker_history_broker_date` (`broker_id`, `trade_date`),
  KEY `idx_broker_history_date` (`trade_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `broker_top_stats` (
  `broker_id` varchar(64) NOT NULL,
  `broker_name` varchar(255) DEFAULT NULL,
  `listing_count` int DEFAULT NULL,
  `total_capital_used` double DEFAULT NULL,
  `year_listing_count` int DEFAULT NULL,
  `year_stock_count` int DEFAULT NULL,
  `three_day_follow_success_rate` double DEFAULT NULL,
  PRIMARY KEY (`broker_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `brokers` (
  `broker_id` varchar(64) NOT NULL,
  `broker_name` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`broker_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `ths_boards` (
  `board_code` varchar(16) NOT NULL,
  `board_type` varchar(16) NOT NULL,
  `board_name` varchar(64) NOT NULL,
  `page_code` varchar(16) NOT NULL,
  `detail_path` varchar(16) NOT NULL,
  `collected_date` int NOT NULL,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`board_code`),
  UNIQUE KEY `uk_ths_board_type_page` (`board_type`, `page_code`),
  KEY `idx_ths_board_type_name` (`board_type`, `board_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `ths_board_constituents` (
  `board_code` varchar(16) NOT NULL,
  `stock_code` varchar(16) NOT NULL,
  `board_type` varchar(16) NOT NULL,
  `board_name` varchar(64) NOT NULL,
  `page_code` varchar(16) NOT NULL,
  `stock_name` varchar(64) NOT NULL,
  `collected_date` int NOT NULL,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`board_code`, `stock_code`),
  KEY `idx_ths_constituent_stock` (`stock_code`),
  KEY `idx_ths_constituent_type_name` (`board_type`, `board_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `ths_stock_relations` (
  `stock_code` varchar(16) NOT NULL,
  `stock_name` varchar(64) NOT NULL,
  `industry_names` text DEFAULT NULL,
  `industry_codes` text DEFAULT NULL,
  `concept_names` text DEFAULT NULL,
  `concept_codes` text DEFAULT NULL,
  `collected_date` int NOT NULL,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`stock_code`),
  KEY `idx_ths_stock_relation_name` (`stock_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
