/*
 LEGACY ARCHIVE - DO NOT USE FOR CURRENT SETUP.
 Use stock_trading_lab_v2.sql for a clean current installation. This historical
 dump creates the retired Chinese-identifier schema and is retained only as a
 migration reference.

 Navicat Premium Dump SQL

 Source Server         : 本机_docker_mysql8.0
 Source Server Type    : MySQL
 Source Server Version : 80043 (8.0.43)
 Source Host           : 127.0.0.1:3306
 Source Schema         : stock_trading_lab

 Target Server Type    : MySQL
 Target Server Version : 80043 (8.0.43)
 File Encoding         : 65001

 Date: 21/04/2026 00:24:41
*/

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ----------------------------
-- Table structure for akshare_sh000001
-- ----------------------------
DROP TABLE IF EXISTS `akshare_sh000001`;
CREATE TABLE `akshare_sh000001`  (
  `日期` int NOT NULL,
  `开盘` double NULL DEFAULT NULL,
  `收盘` double NULL DEFAULT NULL,
  `最高` double NULL DEFAULT NULL,
  `最低` double NULL DEFAULT NULL,
  `成交量` bigint NULL DEFAULT NULL,
  `成交额` double NULL DEFAULT NULL,
  `振幅` double NULL DEFAULT NULL,
  `涨跌幅` double NULL DEFAULT NULL,
  `涨跌额` double NULL DEFAULT NULL,
  `换手率` double NULL DEFAULT NULL,
  PRIMARY KEY (`日期`) USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for t_指数情绪周期_市场宽度
-- ----------------------------
DROP TABLE IF EXISTS `t_指数情绪周期_市场宽度`;
CREATE TABLE `t_指数情绪周期_市场宽度` (
  `日期` int NOT NULL COMMENT '交易日期 yyyyMMdd',
  `股票总数` int DEFAULT NULL,
  `上涨家数` int DEFAULT NULL,
  `下跌家数` int DEFAULT NULL,
  `涨超5家数` int DEFAULT NULL,
  `跌超5家数` int DEFAULT NULL,
  `涨停家数` int DEFAULT NULL,
  `跌停家数` int DEFAULT NULL,
  `成交额` double DEFAULT NULL COMMENT '全市场成交额，沿用 stock_daily.amount 单位',
  `平均涨跌幅` double DEFAULT NULL,
  `创建时间` datetime DEFAULT CURRENT_TIMESTAMP,
  `更新时间` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`日期`) USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci ROW_FORMAT = Dynamic COMMENT='指数情绪周期-每日市场宽度';

-- ----------------------------
-- Table structure for t_指数情绪周期_每日分析
-- ----------------------------
DROP TABLE IF EXISTS `t_指数情绪周期_每日分析`;
CREATE TABLE `t_指数情绪周期_每日分析` (
  `日期` int NOT NULL COMMENT '交易日期 yyyyMMdd',
  `指数名称` varchar(32) DEFAULT '上证指数',
  `周期状态` varchar(32) DEFAULT NULL,
  `周期分数` double DEFAULT NULL,
  `摘要` varchar(512) DEFAULT NULL,
  `开盘` double DEFAULT NULL,
  `收盘` double DEFAULT NULL,
  `最高` double DEFAULT NULL,
  `最低` double DEFAULT NULL,
  `涨跌幅` double DEFAULT NULL,
  `指数成交额` double DEFAULT NULL,
  `指数成交额比例` double DEFAULT NULL,
  `市场成交额比例` double DEFAULT NULL,
  `MA5` double DEFAULT NULL,
  `MA10` double DEFAULT NULL,
  `MA20` double DEFAULT NULL,
  `MA60` double DEFAULT NULL,
  `MA5斜率` double DEFAULT NULL,
  `MA10斜率` double DEFAULT NULL,
  `MA20斜率` double DEFAULT NULL,
  `趋势得分` double DEFAULT NULL,
  `市场宽度得分` double DEFAULT NULL,
  `涨跌停结构得分` double DEFAULT NULL,
  `量能得分` double DEFAULT NULL,
  `风险偏好得分` double DEFAULT NULL,
  `市场宽度JSON` json DEFAULT NULL,
  `信号JSON` json DEFAULT NULL,
  `最近走势JSON` json DEFAULT NULL,
  `波动图JSON` json DEFAULT NULL,
  `完整结果JSON` json DEFAULT NULL,
  `创建时间` datetime DEFAULT CURRENT_TIMESTAMP,
  `更新时间` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`日期`) USING BTREE,
  INDEX `idx_周期状态` (`周期状态`) USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci ROW_FORMAT = Dynamic COMMENT='指数情绪周期-每日分析结果';

-- ----------------------------
-- Table structure for t_热门板块情绪_每日分析
-- ----------------------------
DROP TABLE IF EXISTS `t_热门板块情绪_每日分析`;
CREATE TABLE `t_热门板块情绪_每日分析` (
  `日期` int NOT NULL COMMENT '当前交易日期 yyyyMMdd',
  `板块` varchar(32) NOT NULL,
  `样本来源日期` int DEFAULT NULL COMMENT '严格取上一交易日',
  `前日榜单数据完整` tinyint NOT NULL DEFAULT 0,
  `当日榜单数据完整` tinyint NOT NULL DEFAULT 0,
  `前日板块数量` int DEFAULT NULL COMMENT '韭研公社返回的板块个股数量',
  `前日股票池数量` int DEFAULT NULL COMMENT '前日实际落库去重股票数',
  `前日明细覆盖率` double DEFAULT NULL,
  `当日板块数量` int DEFAULT NULL,
  `当日股票明细数量` int DEFAULT NULL,
  `有效样本数` int DEFAULT NULL,
  `行情覆盖率` double DEFAULT NULL,
  `平均涨跌幅` double DEFAULT NULL,
  `中位数涨跌幅` double DEFAULT NULL,
  `平均振幅` double DEFAULT NULL,
  `涨幅标准差` double DEFAULT NULL,
  `晋级家数` int DEFAULT NULL,
  `晋级率` double DEFAULT NULL,
  `新晋级家数` int DEFAULT NULL COMMENT '当日股票池中不属于上一日股票池的涨停家数',
  `新晋级率` double DEFAULT NULL COMMENT '新增涨停家数占上一日股票池比例',
  `红盘家数` int DEFAULT NULL,
  `红盘率` double DEFAULT NULL,
  `大涨家数` int DEFAULT NULL,
  `大涨率` double DEFAULT NULL,
  `大跌家数` int DEFAULT NULL,
  `大跌率` double DEFAULT NULL,
  `炸板家数` int DEFAULT NULL,
  `炸板率` double DEFAULT NULL,
  `同板块留存家数` int DEFAULT NULL,
  `同板块留存率` double DEFAULT NULL,
  `热度阶段` varchar(16) DEFAULT NULL,
  `承接情绪` varchar(16) DEFAULT NULL,
  `综合状态` varchar(16) DEFAULT NULL,
  `情绪分` double DEFAULT NULL,
  `判定摘要` varchar(512) DEFAULT NULL,
  `判定依据JSON` json DEFAULT NULL,
  `创建时间` datetime DEFAULT CURRENT_TIMESTAMP,
  `更新时间` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`日期`, `板块`) USING BTREE,
  INDEX `idx_热门板块情绪_板块日期` (`板块`, `日期`) USING BTREE,
  INDEX `idx_热门板块情绪_状态日期` (`综合状态`, `日期`) USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci ROW_FORMAT = Dynamic COMMENT='热门板块隔日股票池情绪分析';

-- ----------------------------
-- Table structure for stock_basic
-- ----------------------------
DROP TABLE IF EXISTS `stock_basic`;
CREATE TABLE `stock_basic`  (
  `ts_code` text CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL,
  `symbol` int NULL DEFAULT NULL,
  `name` text CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL,
  `area` text CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL,
  `industry` text CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL,
  `market` text CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL,
  `list_date` bigint NULL DEFAULT NULL,
  `list_status` text CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for stock_daily
-- ----------------------------
DROP TABLE IF EXISTS `stock_daily`;
CREATE TABLE `stock_daily`  (
  `ts_code` int NOT NULL,
  `trade_date` int NULL DEFAULT NULL,
  `open` double NULL DEFAULT NULL,
  `high` double NULL DEFAULT NULL,
  `low` double NULL DEFAULT NULL,
  `close` double NULL DEFAULT NULL,
  `pre_close` double NULL DEFAULT NULL,
  `change` double NULL DEFAULT NULL,
  `pct_chg` double NULL DEFAULT NULL,
  `vol` double NULL DEFAULT NULL,
  `amount` double NULL DEFAULT NULL,
  `total_mv` double NULL DEFAULT NULL COMMENT '总市值，单位万元，Tushare daily_basic.total_mv',
  `circ_mv` double NULL DEFAULT NULL COMMENT '流通市值，单位万元，Tushare daily_basic.circ_mv',
  `free_share` double NULL DEFAULT NULL COMMENT '自由流通股本，单位万股，Tushare daily_basic.free_share',
  `free_mv` double NULL DEFAULT NULL COMMENT '自由流通市值，单位万元，stock_daily.close * free_share',
  `stock_name` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL,
  `data_id` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
  `dde` double NULL DEFAULT NULL COMMENT 'DDE 净额，单位元。',
  UNIQUE INDEX `stock_daily_unique`(`data_id` ASC) USING BTREE,
  INDEX `stock_daily_ts_code_IDX`(`ts_code` ASC, `trade_date` ASC) USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for stock_kdj
-- ----------------------------
DROP TABLE IF EXISTS `stock_kdj`;
CREATE TABLE `stock_kdj`  (
  `ts_code` int NOT NULL,
  `trade_date` int NOT NULL,
  `k` double NULL DEFAULT NULL,
  `d` double NULL DEFAULT NULL,
  `j` double NULL DEFAULT NULL,
  `data_id` varchar(16) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
  UNIQUE INDEX `stock_kdj_unique`(`data_id` ASC) USING BTREE,
  INDEX `stock_kdj_ts_code_IDX`(`ts_code` ASC) USING BTREE,
  INDEX `stock_kdj_trade_date_IDX`(`trade_date` ASC) USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for t_stock_5_min_k
-- ----------------------------
DROP TABLE IF EXISTS `t_stock_5_min_k`;
CREATE TABLE `t_stock_5_min_k`  (
  `date` int NOT NULL,
  `time` bigint NOT NULL,
  `code` int NOT NULL,
  `open` double NULL DEFAULT NULL,
  `high` double NULL DEFAULT NULL,
  `low` double NULL DEFAULT NULL,
  `close` double NULL DEFAULT NULL,
  `volume` double NULL DEFAULT NULL,
  `amount` double NULL DEFAULT NULL,
  `adjustflag` int NULL DEFAULT NULL,
  `data_id` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
  UNIQUE INDEX `t_stock_5_min_k_data_data_id_IDX`(`data_id` ASC) USING BTREE,
  INDEX `t_stock_5_min_k_data_date_IDX`(`date` ASC) USING BTREE,
  INDEX `t_stock_5_min_k_data_time_IDX`(`time` ASC) USING BTREE,
  INDEX `t_stock_5_min_k_data_code_IDX`(`code` ASC) USING BTREE,
  INDEX `t_stock_5_min_k_data_date_code_IDX`(`date` ASC, `code` ASC) USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for t_韭研公社异动解析
-- ----------------------------
DROP TABLE IF EXISTS `t_韭研公社异动解析`;
CREATE TABLE `t_韭研公社异动解析`  (
  `data_id` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `date` int NOT NULL COMMENT '日期',
  `板块` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `板块个股数量` int NOT NULL,
  `股票代码` int NOT NULL,
  `股票名称` varchar(16) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `code` varchar(16) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `涨停时间` datetime NULL DEFAULT NULL,
  `几天几板` varchar(16) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `涨幅` decimal(10, 2) NULL DEFAULT NULL,
  `涨停解析` varchar(1024) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  PRIMARY KEY (`data_id`) USING BTREE,
  INDEX `t_韭研公社异动解析_date_IDX`(`date` ASC) USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for t_龙虎榜
-- ----------------------------
DROP TABLE IF EXISTS `t_龙虎榜`;
CREATE TABLE `t_龙虎榜`  (
  `data_id` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
  `date` int NULL DEFAULT NULL,
  `rid` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL,
  `明细` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL,
  `日期类型` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL,
  `股票代码` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL,
  `股票名称` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL,
  `现价` float NULL DEFAULT NULL,
  `涨跌幅` float NULL DEFAULT NULL,
  `成交金额` float NULL DEFAULT NULL,
  `净买入额` float NULL DEFAULT NULL,
  `合计买入` float NULL DEFAULT NULL,
  `合计卖出` float NULL DEFAULT NULL,
  `买1营业部id` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL,
  `买1营业部` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL,
  `买1买入额` float NULL DEFAULT NULL,
  `买1卖出额` float NULL DEFAULT NULL,
  `买1净额` float NULL DEFAULT NULL,
  `买2营业部id` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL,
  `买2营业部` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL,
  `买2买入额` float NULL DEFAULT NULL,
  `买2卖出额` float NULL DEFAULT NULL,
  `买2净额` float NULL DEFAULT NULL,
  `买3营业部id` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL,
  `买3营业部` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL,
  `买3买入额` float NULL DEFAULT NULL,
  `买3卖出额` float NULL DEFAULT NULL,
  `买3净额` float NULL DEFAULT NULL,
  `买4营业部id` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL,
  `买4营业部` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL,
  `买4买入额` float NULL DEFAULT NULL,
  `买4卖出额` float NULL DEFAULT NULL,
  `买4净额` float NULL DEFAULT NULL,
  `买5营业部id` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL,
  `买5营业部` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL,
  `买5买入额` float NULL DEFAULT NULL,
  `买5卖出额` float NULL DEFAULT NULL,
  `买5净额` float NULL DEFAULT NULL,
  `卖1营业部id` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL,
  `卖1营业部` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL,
  `卖1买入额` float NULL DEFAULT NULL,
  `卖1卖出额` float NULL DEFAULT NULL,
  `卖1净额` float NULL DEFAULT NULL,
  `卖2营业部id` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL,
  `卖2营业部` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL,
  `卖2买入额` float NULL DEFAULT NULL,
  `卖2卖出额` float NULL DEFAULT NULL,
  `卖2净额` float NULL DEFAULT NULL,
  `卖3营业部id` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL,
  `卖3营业部` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL,
  `卖3买入额` float NULL DEFAULT NULL,
  `卖3卖出额` float NULL DEFAULT NULL,
  `卖3净额` float NULL DEFAULT NULL,
  `卖4营业部id` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL,
  `卖4营业部` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL,
  `卖4买入额` float NULL DEFAULT NULL,
  `卖4卖出额` float NULL DEFAULT NULL,
  `卖4净额` float NULL DEFAULT NULL,
  `卖5营业部id` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL,
  `卖5营业部` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL,
  `卖5买入额` float NULL DEFAULT NULL,
  `卖5卖出额` float NULL DEFAULT NULL,
  `卖5净额` float NULL DEFAULT NULL,
  PRIMARY KEY (`data_id`) USING BTREE,
  INDEX `t_龙虎榜_date_IDX`(`date` ASC) USING BTREE,
  INDEX `t_龙虎榜_date_code_IDX`(`date` ASC, `股票代码` ASC) USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for t_龙虎榜_营业部_上榜历史数据
-- ----------------------------
DROP TABLE IF EXISTS `t_龙虎榜_营业部_上榜历史数据`;
CREATE TABLE `t_龙虎榜_营业部_上榜历史数据`  (
  `营业部id` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL,
  `营业部名称` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL,
  `日期` int NULL DEFAULT NULL,
  `股票简称` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL,
  `股票代码` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL,
  `上榜原因` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL,
  `涨跌幅` double NULL DEFAULT NULL,
  `买入额` double NULL DEFAULT NULL,
  `卖出额` double NULL DEFAULT NULL,
  `买卖净额` double NULL DEFAULT NULL,
  `所属板块` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL,
  `data_id` varchar(225) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
  INDEX `t_龙虎榜_营业部上榜历史数据_营业部id_日期_IDX`(`营业部id` ASC, `日期` ASC) USING BTREE,
  INDEX `t_龙虎榜_营业部上榜历史数据_日期_IDX`(`日期` ASC) USING BTREE,
  INDEX `t_龙虎榜_营业部上榜历史数据_营业部id_IDX`(`营业部id` ASC) USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for t_龙虎榜_营业部_上榜次数最多
-- ----------------------------
DROP TABLE IF EXISTS `t_龙虎榜_营业部_上榜次数最多`;
CREATE TABLE `t_龙虎榜_营业部_上榜次数最多`  (
  `营业部id` text CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL,
  `营业部名称` text CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL,
  `上榜次数` text CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL,
  `合计动用资金` text CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL,
  `年内上榜次数` text CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL,
  `年内买入股票只数` text CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL,
  `年内3日跟买成功率` text CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for t_龙虎榜_营业部_全部
-- ----------------------------
DROP TABLE IF EXISTS `t_龙虎榜_营业部_全部`;
CREATE TABLE `t_龙虎榜_营业部_全部`  (
  `营业部id` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
  `营业部名称` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL,
  PRIMARY KEY (`营业部id`) USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for t_同花顺板块列表
-- ----------------------------
DROP TABLE IF EXISTS `t_同花顺板块列表`;
CREATE TABLE `t_同花顺板块列表`  (
  `板块代码` varchar(16) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '同花顺导入代码，概念一般为88开头',
  `板块类型` varchar(16) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '概念/行业',
  `板块名称` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `页面代码` varchar(16) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'q.10jqka.com.cn detail code',
  `详情路径` varchar(16) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'gn/thshy',
  `采集日期` int NOT NULL,
  `更新时间` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`板块代码`) USING BTREE,
  UNIQUE INDEX `uk_ths_board_type_page`(`板块类型` ASC, `页面代码` ASC) USING BTREE,
  INDEX `idx_ths_board_type_name`(`板块类型` ASC, `板块名称` ASC) USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for t_同花顺板块成分股
-- ----------------------------
DROP TABLE IF EXISTS `t_同花顺板块成分股`;
CREATE TABLE `t_同花顺板块成分股`  (
  `板块代码` varchar(16) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `股票代码` varchar(16) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `板块类型` varchar(16) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '概念/行业',
  `板块名称` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `页面代码` varchar(16) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `股票名称` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `采集日期` int NOT NULL,
  `更新时间` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`板块代码`, `股票代码`) USING BTREE,
  INDEX `idx_ths_constituent_stock`(`股票代码` ASC) USING BTREE,
  INDEX `idx_ths_constituent_type_name`(`板块类型` ASC, `板块名称` ASC) USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for t_同花顺股票板块概念对应关系
-- ----------------------------
DROP TABLE IF EXISTS `t_同花顺股票板块概念对应关系`;
CREATE TABLE `t_同花顺股票板块概念对应关系`  (
  `股票代码` varchar(16) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `股票名称` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `同花顺行业` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL,
  `同花顺行业代码` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL,
  `同花顺概念` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL,
  `同花顺概念代码` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL,
  `采集日期` int NOT NULL,
  `更新时间` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`股票代码`) USING BTREE,
  INDEX `idx_ths_stock_relation_name`(`股票名称` ASC) USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci ROW_FORMAT = Dynamic;

SET FOREIGN_KEY_CHECKS = 1;

