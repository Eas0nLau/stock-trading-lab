-- Destructive finalization. Run only after backup, module cutover, and validation.
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
