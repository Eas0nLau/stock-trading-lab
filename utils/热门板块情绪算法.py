from stock_lab.modules.emotion.contracts import LEGACY_KEY_MAP
from stock_lab.modules.emotion.hot_board import HotBoardConfig, analyze_hot_board_day


_config = HotBoardConfig.from_settings()
热门板块入选数量阈值 = _config.selection_threshold
高潮数量阈值 = _config.climax_threshold
强势延续晋级比例 = _config.strong_continuation_ratio
高潮基础分 = _config.climax_score
晋级涨幅阈值 = _config.promotion_change_pct
热门板块排除集合 = set()
状态强弱排序 = {"高潮": 100, "强势延续": 90, "良性承接": 80, "升温": 70, "分化": 60, "活跃": 55, "分歧": 40, "数据不足": 30, "退潮": 20, "沉寂": 10, "未上榜": 5, "数据缺失": 0}


def 刷新运行配置():
    global _config, 热门板块入选数量阈值, 高潮数量阈值, 强势延续晋级比例
    _config = HotBoardConfig.from_settings()
    热门板块入选数量阈值 = _config.selection_threshold
    高潮数量阈值 = _config.climax_threshold
    强势延续晋级比例 = _config.strong_continuation_ratio
    return {"热门板块入选数量阈值": 热门板块入选数量阈值, "高潮数量阈值": 高潮数量阈值, "强势延续晋级比例": 强势延续晋级比例, "排除板块": []}


def _legacy_value(value):
    reverse = {target: source for source, target in LEGACY_KEY_MAP.items()}
    if isinstance(value, list):
        return [_legacy_value(item) for item in value]
    if isinstance(value, dict):
        return {reverse.get(key, key): _legacy_value(nested) for key, nested in value.items()}
    return value


def 生成每日分析(**values):
    previous_stocks = [{"stock_code": str(row.get("股票代码") or "").zfill(6), "stock_name": row.get("股票名称")} for row in values.get("前日股票", [])]
    current_stocks = [{"stock_code": str(row.get("股票代码") or "").zfill(6), "stock_name": row.get("股票名称")} for row in values.get("当日股票", [])]
    quotes = {str(code).zfill(6): {"previous_close": row.get("pre_close"), "high_price": row.get("high"), "low_price": row.get("low"), "change_pct": row.get("pct_chg")} for code, row in values.get("当日行情", {}).items()}
    result = analyze_hot_board_day(
        trade_date=values.get("日期"), board_name=values.get("板块"), sample_trade_date=values.get("样本来源日期"),
        previous_stocks=previous_stocks, current_stocks=current_stocks, current_quotes=quotes,
        previous_board_count=values.get("前日板块数量"), current_board_count=values.get("当日板块数量"),
        previous_list_complete=values.get("前日榜单数据完整", True), current_list_complete=values.get("当日榜单数据完整", True), config=_config,
    )
    return _legacy_value(result)


def 取整数(value):
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
