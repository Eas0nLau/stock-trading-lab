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

DROP PROCEDURE IF EXISTS assert_table_compatible;
DROP PROCEDURE IF EXISTS validate_english_schema;

DELIMITER $$
CREATE PROCEDURE assert_table_compatible(
  IN p_table varchar(64),
  IN p_columns longtext,
  IN p_indexes text
)
BEGIN
  DECLARE v_engine varchar(64);
  DECLARE v_columns longtext;
  DECLARE v_indexes text;
  DECLARE v_message varchar(128);

  SELECT `ENGINE`
  INTO v_engine
  FROM `information_schema`.`TABLES`
  WHERE `TABLE_SCHEMA` = DATABASE() AND `TABLE_NAME` = p_table;

  SELECT GROUP_CONCAT(
    CONCAT(`COLUMN_NAME`, ':', `COLUMN_TYPE`, ':', `IS_NULLABLE`)
    ORDER BY `ORDINAL_POSITION` SEPARATOR '|'
  )
  INTO v_columns
  FROM `information_schema`.`COLUMNS`
  WHERE `TABLE_SCHEMA` = DATABASE() AND `TABLE_NAME` = p_table;

  SELECT GROUP_CONCAT(
    CONCAT(indexes.`INDEX_NAME`, ':', indexes.`NON_UNIQUE`, '(', indexes.column_names, ')')
    ORDER BY indexes.`INDEX_NAME` SEPARATOR '|'
  )
  INTO v_indexes
  FROM (
    SELECT
      `INDEX_NAME`,
      `NON_UNIQUE`,
      GROUP_CONCAT(`COLUMN_NAME` ORDER BY `SEQ_IN_INDEX` SEPARATOR ',') AS column_names
    FROM `information_schema`.`STATISTICS`
    WHERE `TABLE_SCHEMA` = DATABASE() AND `TABLE_NAME` = p_table
    GROUP BY `INDEX_NAME`, `NON_UNIQUE`
  ) AS indexes;

  IF v_engine IS NULL OR v_engine <> 'InnoDB' OR NOT (v_columns <=> p_columns) OR NOT (v_indexes <=> p_indexes) THEN
    SET v_message = CONCAT('Incompatible existing schema: ', p_table);
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = v_message;
  END IF;
END$$

CREATE PROCEDURE validate_english_schema()
BEGIN
  CALL assert_table_compatible(
    'schema_migrations',
    'version:varchar(64):NO|applied_at:datetime:NO',
    'PRIMARY:0(version)'
  );
  CALL assert_table_compatible(
    'migration_validations',
    'validation_version:varchar(64):NO|status:varchar(16):NO|validated_at:datetime:NO|details:varchar(512):YES',
    'PRIMARY:0(validation_version)'
  );
  CALL assert_table_compatible(
    'index_daily',
    'trade_date:int:NO|open_price:double:YES|close_price:double:YES|high_price:double:YES|low_price:double:YES|volume:bigint:YES|turnover:double:YES|amplitude_pct:double:YES|change_pct:double:YES|change_amount:double:YES|turnover_rate:double:YES',
    'PRIMARY:0(trade_date)'
  );
  CALL assert_table_compatible(
    'index_market_breadth',
    'trade_date:int:NO|stock_count:int:YES|advancing_count:int:YES|declining_count:int:YES|advance_over_5_count:int:YES|decline_over_5_count:int:YES|limit_up_count:int:YES|limit_down_count:int:YES|market_turnover:double:YES|average_change_pct:double:YES|created_at:datetime:YES|updated_at:datetime:YES',
    'PRIMARY:0(trade_date)'
  );
  CALL assert_table_compatible(
    'index_emotion_daily',
    'trade_date:int:NO|index_name:varchar(32):YES|cycle_state:varchar(32):YES|cycle_score:double:YES|summary:varchar(512):YES|open_price:double:YES|close_price:double:YES|high_price:double:YES|low_price:double:YES|change_pct:double:YES|index_turnover:double:YES|index_turnover_ratio:double:YES|market_turnover_ratio:double:YES|ma5:double:YES|ma10:double:YES|ma20:double:YES|ma60:double:YES|ma5_slope:double:YES|ma10_slope:double:YES|ma20_slope:double:YES|trend_score:double:YES|breadth_score:double:YES|limit_structure_score:double:YES|volume_score:double:YES|risk_appetite_score:double:YES|market_breadth_json:json:YES|signals_json:json:YES|recent_trend_json:json:YES|volatility_chart_json:json:YES|full_result_json:json:YES|created_at:datetime:YES|updated_at:datetime:YES',
    'idx_index_emotion_cycle_state:1(cycle_state)|PRIMARY:0(trade_date)'
  );
  CALL assert_table_compatible(
    'hot_board_emotion_daily',
    'trade_date:int:NO|board_name:varchar(64):NO|sample_trade_date:int:YES|previous_list_complete:tinyint:NO|current_list_complete:tinyint:NO|previous_board_count:int:YES|previous_stock_pool_count:int:YES|previous_detail_coverage:double:YES|current_board_count:int:YES|current_stock_detail_count:int:YES|valid_sample_count:int:YES|quote_coverage:double:YES|average_change_pct:double:YES|median_change_pct:double:YES|average_amplitude_pct:double:YES|change_stddev:double:YES|promotion_count:int:YES|promotion_rate:double:YES|new_promotion_count:int:YES|new_promotion_rate:double:YES|positive_count:int:YES|positive_rate:double:YES|large_gain_count:int:YES|large_gain_rate:double:YES|large_loss_count:int:YES|large_loss_rate:double:YES|failed_limit_count:int:YES|failed_limit_rate:double:YES|retained_count:int:YES|retained_rate:double:YES|heat_stage:varchar(32):YES|continuation_state:varchar(32):YES|overall_status:varchar(32):YES|emotion_score:double:YES|decision_summary:varchar(512):YES|decision_reasons_json:json:YES|created_at:datetime:YES|updated_at:datetime:YES',
    'idx_hot_board_name_date:1(board_name,trade_date)|idx_hot_board_status_date:1(overall_status,trade_date)|PRIMARY:0(trade_date,board_name)'
  );
  CALL assert_table_compatible(
    'securities',
    'ts_code:varchar(16):NO|symbol:varchar(8):NO|name:varchar(64):NO|area:varchar(64):YES|industry:varchar(128):YES|market:varchar(32):YES|list_date:int:YES|list_status:varchar(8):YES',
    'idx_securities_market:1(market)|PRIMARY:0(ts_code)|uk_securities_symbol:0(symbol)'
  );
  CALL assert_table_compatible(
    'daily_quotes',
    'data_id:varchar(64):NO|ts_code:varchar(16):NO|trade_date:int:NO|open_price:double:YES|high_price:double:YES|low_price:double:YES|close_price:double:YES|previous_close:double:YES|change_amount:double:YES|change_pct:double:YES|volume:double:YES|turnover:double:YES|total_market_value:double:YES|circulating_market_value:double:YES|free_float_shares:double:YES|free_float_market_value:double:YES|stock_name:varchar(64):YES|dde_net_amount:double:YES',
    'idx_daily_quotes_date:1(trade_date)|PRIMARY:0(data_id)|uk_daily_quotes_code_date:0(ts_code,trade_date)'
  );
  CALL assert_table_compatible(
    'kdj_indicators',
    'data_id:varchar(64):NO|ts_code:varchar(16):NO|trade_date:int:NO|k_value:double:YES|d_value:double:YES|j_value:double:YES',
    'idx_kdj_trade_date:1(trade_date)|PRIMARY:0(data_id)|uk_kdj_code_date:0(ts_code,trade_date)'
  );
  CALL assert_table_compatible(
    'intraday_bars_5m',
    'data_id:varchar(64):NO|trade_date:int:NO|trade_time:bigint:NO|stock_code:varchar(16):NO|open_price:double:YES|high_price:double:YES|low_price:double:YES|close_price:double:YES|volume:double:YES|turnover:double:YES|adjustment_flag:int:YES',
    'idx_intraday_date_code:1(trade_date,stock_code)|idx_intraday_time:1(trade_time)|PRIMARY:0(data_id)'
  );
  CALL assert_table_compatible(
    'jiuyan_actions',
    'data_id:varchar(64):NO|trade_date:int:NO|board_name:varchar(64):NO|board_stock_count:int:NO|stock_code:varchar(16):NO|stock_name:varchar(64):YES|source_code:varchar(16):YES|limit_up_at:datetime:YES|board_streak:varchar(32):YES|change_pct:decimal(10,2):YES|limit_up_reason:varchar(1024):YES',
    'idx_jiuyan_board_date:1(board_name,trade_date)|idx_jiuyan_trade_date:1(trade_date)|PRIMARY:0(data_id)'
  );
  CALL assert_table_compatible(
    'dragon_tiger',
    'data_id:varchar(64):NO|trade_date:int:YES|source_id:varchar(64):YES|detail_type:varchar(128):YES|date_type:varchar(64):YES|stock_code:varchar(16):YES|stock_name:varchar(100):YES|current_price:double:YES|change_pct:double:YES|turnover:double:YES|net_buy_amount:double:YES|total_buy_amount:double:YES|total_sell_amount:double:YES|buy_1_broker_id:varchar(64):YES|buy_1_broker_name:varchar(128):YES|buy_1_buy_amount:double:YES|buy_1_sell_amount:double:YES|buy_1_net_amount:double:YES|buy_2_broker_id:varchar(64):YES|buy_2_broker_name:varchar(128):YES|buy_2_buy_amount:double:YES|buy_2_sell_amount:double:YES|buy_2_net_amount:double:YES|buy_3_broker_id:varchar(64):YES|buy_3_broker_name:varchar(128):YES|buy_3_buy_amount:double:YES|buy_3_sell_amount:double:YES|buy_3_net_amount:double:YES|buy_4_broker_id:varchar(64):YES|buy_4_broker_name:varchar(128):YES|buy_4_buy_amount:double:YES|buy_4_sell_amount:double:YES|buy_4_net_amount:double:YES|buy_5_broker_id:varchar(64):YES|buy_5_broker_name:varchar(128):YES|buy_5_buy_amount:double:YES|buy_5_sell_amount:double:YES|buy_5_net_amount:double:YES|sell_1_broker_id:varchar(64):YES|sell_1_broker_name:varchar(128):YES|sell_1_buy_amount:double:YES|sell_1_sell_amount:double:YES|sell_1_net_amount:double:YES|sell_2_broker_id:varchar(64):YES|sell_2_broker_name:varchar(128):YES|sell_2_buy_amount:double:YES|sell_2_sell_amount:double:YES|sell_2_net_amount:double:YES|sell_3_broker_id:varchar(64):YES|sell_3_broker_name:varchar(128):YES|sell_3_buy_amount:double:YES|sell_3_sell_amount:double:YES|sell_3_net_amount:double:YES|sell_4_broker_id:varchar(64):YES|sell_4_broker_name:varchar(128):YES|sell_4_buy_amount:double:YES|sell_4_sell_amount:double:YES|sell_4_net_amount:double:YES|sell_5_broker_id:varchar(64):YES|sell_5_broker_name:varchar(128):YES|sell_5_buy_amount:double:YES|sell_5_sell_amount:double:YES|sell_5_net_amount:double:YES',
    'idx_dragon_tiger_date_code:1(trade_date,stock_code)|PRIMARY:0(data_id)'
  );
  CALL assert_table_compatible(
    'broker_listing_history',
    'data_id:varchar(225):NO|broker_id:varchar(64):YES|broker_name:varchar(255):YES|trade_date:int:YES|stock_name:varchar(64):YES|stock_code:varchar(16):YES|listing_reason:varchar(255):YES|change_pct:double:YES|buy_amount:double:YES|sell_amount:double:YES|net_amount:double:YES|board_name:varchar(64):YES',
    'idx_broker_history_broker_date:1(broker_id,trade_date)|idx_broker_history_date:1(trade_date)|PRIMARY:0(data_id)'
  );
  CALL assert_table_compatible(
    'broker_top_stats',
    'broker_id:varchar(64):NO|broker_name:varchar(255):YES|listing_count:int:YES|total_capital_used:double:YES|year_listing_count:int:YES|year_stock_count:int:YES|three_day_follow_success_rate:double:YES',
    'PRIMARY:0(broker_id)'
  );
  CALL assert_table_compatible(
    'brokers',
    'broker_id:varchar(64):NO|broker_name:varchar(255):YES',
    'PRIMARY:0(broker_id)'
  );
  CALL assert_table_compatible(
    'ths_boards',
    'board_code:varchar(16):NO|board_type:varchar(16):NO|board_name:varchar(64):NO|page_code:varchar(16):NO|detail_path:varchar(16):NO|collected_date:int:NO|updated_at:datetime:NO',
    'idx_ths_board_type_name:1(board_type,board_name)|PRIMARY:0(board_code)|uk_ths_board_type_page:0(board_type,page_code)'
  );
  CALL assert_table_compatible(
    'ths_board_constituents',
    'board_code:varchar(16):NO|stock_code:varchar(16):NO|board_type:varchar(16):NO|board_name:varchar(64):NO|page_code:varchar(16):NO|stock_name:varchar(64):NO|collected_date:int:NO|updated_at:datetime:NO',
    'idx_ths_constituent_stock:1(stock_code)|idx_ths_constituent_type_name:1(board_type,board_name)|PRIMARY:0(board_code,stock_code)'
  );
  CALL assert_table_compatible(
    'ths_stock_relations',
    'stock_code:varchar(16):NO|stock_name:varchar(64):NO|industry_names:text:YES|industry_codes:text:YES|concept_names:text:YES|concept_codes:text:YES|collected_date:int:NO|updated_at:datetime:NO',
    'idx_ths_stock_relation_name:1(stock_name)|PRIMARY:0(stock_code)'
  );
END$$
DELIMITER ;

SET SESSION group_concat_max_len = 65535;
CALL validate_english_schema();
DROP PROCEDURE validate_english_schema;
DROP PROCEDURE assert_table_compatible;

INSERT INTO `schema_migrations` (`version`) VALUES ('001_create_english_schema')
ON DUPLICATE KEY UPDATE `applied_at`=`applied_at`;
