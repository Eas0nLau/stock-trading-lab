from stock_lab.shared.errors import DataValidationError


LEGACY_KEY_MAP = {
    "状态": "status",
    "错误信息": "error_message",
    "指数周期": "index_cycle",
    "指数名称": "index_name",
    "交易日期": "trade_date",
    "日期": "trade_date",
    "最新交易日": "latest_trade_date",
    "周期状态": "cycle_state",
    "周期分数": "cycle_score",
    "摘要": "summary",
    "指数": "index_quote",
    "开盘": "open_price",
    "收盘": "close_price",
    "最高": "high_price",
    "最低": "low_price",
    "涨跌幅": "change_pct",
    "成交额": "turnover",
    "指数成交额比例": "index_turnover_ratio",
    "市场成交额比例": "market_turnover_ratio",
    "均线": "moving_averages",
    "均线斜率": "moving_average_slopes",
    "MA5": "ma5",
    "MA10": "ma10",
    "MA20": "ma20",
    "MA60": "ma60",
    "市场宽度": "market_breadth",
    "股票总数": "stock_count",
    "上涨家数": "advancing_count",
    "下跌家数": "declining_count",
    "上涨占比": "advance_ratio",
    "涨超5家数": "advance_over_5_count",
    "跌超5家数": "decline_over_5_count",
    "涨停": "limit_up_count",
    "涨停家数": "limit_up_count",
    "跌停": "limit_down_count",
    "跌停家数": "limit_down_count",
    "平均涨跌幅": "average_change_pct",
    "成交额比例": "turnover_ratio",
    "分项得分": "score_components",
    "趋势": "trend",
    "涨跌停结构": "limit_structure",
    "量能": "volume",
    "风险偏好": "risk_appetite",
    "信号": "signals",
    "名称": "name",
    "数值": "value",
    "说明": "description",
    "最近走势": "recent_trend",
    "近期走势": "recent_trend",
    "波动图": "volatility_chart",
    "情绪分": "emotion_score",
    "可选日期": "available_dates",
    "统计交易日数": "trading_day_count",
    "热门板块数量": "hot_board_count",
    "板块列表": "boards",
    "配置": "config",
    "数据口径": "methodology",
    "板块": "board_name",
    "近30日峰值数量": "peak_count_30d",
    "最近高潮日期": "latest_climax_date",
    "高潮次数": "climax_count",
    "最新状态": "latest_status",
    "最新情绪分": "latest_emotion_score",
    "近期强度": "recent_strength",
    "最新记录": "latest_record",
    "样本来源日期": "sample_trade_date",
    "前日榜单数据完整": "previous_list_complete",
    "当日榜单数据完整": "current_list_complete",
    "前日板块数量": "previous_board_count",
    "前日股票池数量": "previous_stock_pool_count",
    "前日明细覆盖率": "previous_detail_coverage",
    "当日板块数量": "current_board_count",
    "当日股票明细数量": "current_stock_detail_count",
    "有效样本数": "valid_sample_count",
    "行情覆盖率": "quote_coverage",
    "中位数涨跌幅": "median_change_pct",
    "平均振幅": "average_amplitude_pct",
    "涨幅标准差": "change_stddev",
    "晋级家数": "promotion_count",
    "晋级率": "promotion_rate",
    "新晋级家数": "new_promotion_count",
    "新晋级率": "new_promotion_rate",
    "红盘家数": "positive_count",
    "红盘率": "positive_rate",
    "大涨家数": "large_gain_count",
    "大涨率": "large_gain_rate",
    "大跌家数": "large_loss_count",
    "大跌率": "large_loss_rate",
    "炸板家数": "failed_limit_count",
    "炸板率": "failed_limit_rate",
    "同板块留存家数": "retained_count",
    "同板块留存率": "retained_rate",
    "热度阶段": "heat_stage",
    "承接情绪": "continuation_state",
    "综合状态": "overall_status",
    "判定摘要": "decision_summary",
    "判定依据": "decision_reasons",
    "热门板块入选数量阈值": "selection_threshold",
    "高潮数量阈值": "climax_threshold",
    "强势延续晋级比例": "strong_continuation_ratio",
    "排除板块": "excluded_boards",
    "热门板块": "hot_board_definition",
    "高潮定义": "climax_definition",
    "退潮定义": "ebb_definition",
    "强势延续定义": "strong_continuation_definition",
    "分化定义": "dispersion_definition",
    "正向承接门槛": "positive_continuation_threshold",
    "情绪分口径": "emotion_score_methodology",
    "晋级定义": "promotion_definition",
    "股票范围": "stock_universe",
    "规则版本": "rule_version",
    "部分晋级定义": "partial_promotion_definition",
    "情绪分样本置信度": "emotion_score_sample_confidence",
    "命中规则": "matched_rules",
    "阈值": "thresholds",
    "热门板块入选数量": "selection_count",
    "高潮数量": "climax_count",
    "晋级涨幅": "promotion_change_pct",
    "大涨涨幅": "large_gain_change_pct",
    "大跌涨幅": "large_loss_change_pct",
    "最低有效样本数": "minimum_valid_sample_count",
    "最低行情覆盖率": "minimum_quote_coverage",
}


CONTEXT_KEY_MAP = {
    ("score_components", "市场宽度"): "breadth",
    ("methodology", "承接情绪"): "continuation_methodology",
}
CANONICAL_KEY_MAP = {target: source for source, target in LEGACY_KEY_MAP.items()}
CANONICAL_CONTEXT_KEY_MAP = {
    ("methodology", "continuation_methodology"): "承接情绪",
}


def translate_legacy_payload(value, *, parent_key=None):
    if isinstance(value, list):
        return [translate_legacy_payload(item, parent_key=parent_key) for item in value]
    if not isinstance(value, dict):
        return value

    translated = {}
    for key, nested in value.items():
        target_key = CONTEXT_KEY_MAP.get((parent_key, key), LEGACY_KEY_MAP.get(key, key))
        if not str(target_key).isascii():
            raise DataValidationError(f"Unmapped legacy emotion key: {key}")
        translated_value = translate_legacy_payload(nested, parent_key=target_key)
        if target_key not in translated or translated_value is not None:
            translated[target_key] = translated_value
    return translated


def translate_canonical_payload(value, *, parent_key=None):
    if isinstance(value, list):
        return [translate_canonical_payload(item, parent_key=parent_key) for item in value]
    if not isinstance(value, dict):
        return value

    translated = {}
    for key, nested in value.items():
        target_key = CANONICAL_CONTEXT_KEY_MAP.get((parent_key, key), CANONICAL_KEY_MAP.get(key, key))
        translated[target_key] = translate_canonical_payload(nested, parent_key=key)
    return translated
