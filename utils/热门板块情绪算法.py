from stock_lab.modules.emotion.contracts import translate_canonical_payload
from stock_lab.modules.emotion.hot_board import (
    HotBoardConfig,
    analyze_legacy_hot_board_day,
    coerce_int,
    legacy_runtime_config,
)
from stock_lab.modules.emotion.service import STATE_STRENGTH_RANK


_config = HotBoardConfig.from_settings()
热门板块入选数量阈值 = _config.selection_threshold
高潮数量阈值 = _config.climax_threshold
强势延续晋级比例 = _config.strong_continuation_ratio
高潮基础分 = _config.climax_score
晋级涨幅阈值 = _config.promotion_change_pct
热门板块排除集合 = set()
状态强弱排序 = STATE_STRENGTH_RANK


def 刷新运行配置():
    return legacy_runtime_config()


def 生成每日分析(**values):
    return translate_canonical_payload(analyze_legacy_hot_board_day(values, _config))


def 取整数(value):
    return coerce_int(value)
