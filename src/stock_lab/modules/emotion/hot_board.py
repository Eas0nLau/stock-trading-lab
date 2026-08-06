import math
import statistics
from dataclasses import dataclass

from stock_lab.config import get_settings


_legacy_config = None


@dataclass(frozen=True)
class HotBoardConfig:
    selection_threshold: int = 8
    climax_threshold: int = 20
    strong_continuation_ratio: float = 0.5
    promotion_change_pct: float = 9.5
    large_gain_pct: float = 5.0
    large_loss_pct: float = -5.0
    minimum_sample_count: int = 3
    minimum_quote_coverage: float = 70.0
    climax_score: float = 100.0
    continuation_weight: float = 0.30
    excluded_boards: tuple[str, ...] = ("ST板块", "公告", "其他")

    @classmethod
    def from_settings(cls, settings=None):
        settings = settings or get_settings()
        return cls(
            selection_threshold=settings.hot_board_emotion_selection_threshold,
            climax_threshold=settings.hot_board_emotion_climax_threshold,
            strong_continuation_ratio=settings.hot_board_emotion_strong_continuation_ratio,
            excluded_boards=tuple(settings.hot_board_emotion_excluded_boards),
        )


def legacy_runtime_config(config=None):
    config = config or get_legacy_config()
    return {
        "热门板块入选数量阈值": config.selection_threshold,
        "高潮数量阈值": config.climax_threshold,
        "强势延续晋级比例": config.strong_continuation_ratio,
        "排除板块": sorted(config.excluded_boards),
    }


def get_legacy_config():
    global _legacy_config
    if _legacy_config is None:
        _legacy_config = HotBoardConfig.from_settings()
    return _legacy_config


def refresh_legacy_config():
    global _legacy_config
    _legacy_config = HotBoardConfig.from_settings()
    return legacy_runtime_config(_legacy_config)


def legacy_config_value(name):
    config = get_legacy_config()
    values = {
        "_config": config,
        "热门板块入选数量阈值": config.selection_threshold,
        "高潮数量阈值": config.climax_threshold,
        "强势延续晋级比例": config.strong_continuation_ratio,
        "高潮基础分": config.climax_score,
        "晋级涨幅阈值": config.promotion_change_pct,
        "热门板块排除集合": set(config.excluded_boards),
    }
    if name == "状态强弱排序":
        from .service import STATE_STRENGTH_RANK

        return STATE_STRENGTH_RANK
    if name not in values:
        raise AttributeError(name)
    return values[name]


def analyze_legacy_hot_board_day(values, config=None):
    config = config or get_legacy_config()
    previous_stocks = [
        {"stock_code": str(row.get("股票代码") or "").zfill(6), "stock_name": row.get("股票名称")}
        for row in values.get("前日股票", [])
    ]
    current_stocks = [
        {"stock_code": str(row.get("股票代码") or "").zfill(6), "stock_name": row.get("股票名称")}
        for row in values.get("当日股票", [])
    ]
    quotes = {
        str(code).zfill(6): {
            "previous_close": row.get("pre_close"),
            "high_price": row.get("high"),
            "low_price": row.get("low"),
            "change_pct": row.get("pct_chg"),
        }
        for code, row in values.get("当日行情", {}).items()
    }
    return analyze_hot_board_day(
        trade_date=values.get("日期"),
        board_name=values.get("板块"),
        sample_trade_date=values.get("样本来源日期"),
        previous_stocks=previous_stocks,
        current_stocks=current_stocks,
        current_quotes=quotes,
        previous_board_count=values.get("前日板块数量"),
        current_board_count=values.get("当日板块数量"),
        previous_list_complete=values.get("前日榜单数据完整", True),
        current_list_complete=values.get("当日榜单数据完整", True),
        config=config,
    )


def coerce_int(value):
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def analyze_hot_board_day(
    *,
    trade_date,
    board_name,
    sample_trade_date,
    previous_stocks,
    current_stocks,
    current_quotes,
    previous_board_count,
    current_board_count,
    previous_list_complete=True,
    current_list_complete=True,
    config=None,
):
    config = config or HotBoardConfig.from_settings()
    previous_stocks = _deduplicate(previous_stocks)
    current_stocks = _deduplicate(current_stocks)
    current_codes = {str(row.get("stock_code") or "").zfill(6) for row in current_stocks}
    metrics = _continuation_metrics(previous_stocks, current_quotes, current_codes, config)
    previous_pool_count = metrics["previous_stock_pool_count"]
    heat_stage = _heat_stage(current_board_count, current_list_complete, config)
    continuation_state, matched_rule = _continuation_state(metrics, previous_list_complete, config)
    if heat_stage == "未上榜" and _int(previous_board_count) > 0:
        continuation_state = "退潮"
        matched_rule = "上一交易日上榜且当日未上榜，板块热度消失"
    overall_status = _overall_status(heat_stage, continuation_state, previous_board_count, current_board_count, config)
    emotion_score = _emotion_score(metrics, current_board_count, current_list_complete, heat_stage, config)
    emotion_score = _calibrate_score(emotion_score, overall_status, heat_stage, config)
    return {
        "trade_date": _int(trade_date),
        "board_name": str(board_name),
        "sample_trade_date": _optional_int(sample_trade_date),
        "previous_list_complete": int(bool(previous_list_complete)),
        "current_list_complete": int(bool(current_list_complete)),
        "previous_board_count": _optional_int(previous_board_count),
        "previous_stock_pool_count": previous_pool_count,
        "previous_detail_coverage": _percentage(previous_pool_count, previous_board_count) if previous_board_count else None,
        "current_board_count": _optional_int(current_board_count),
        "current_stock_detail_count": len(current_stocks),
        **metrics,
        "heat_stage": heat_stage,
        "continuation_state": continuation_state,
        "overall_status": overall_status,
        "emotion_score": emotion_score,
        "decision_summary": _decision_summary(previous_pool_count, previous_board_count, current_board_count, metrics, heat_stage, continuation_state, overall_status, config),
        "decision_reasons": {
            "rule_version": "v9",
            "stock_scope": "沪深主板且股票名称不含ST",
            "matched_rule": matched_rule,
            "sample_confidence": _sample_confidence(metrics),
            "thresholds": {
                "selection_count": config.selection_threshold,
                "climax_count": config.climax_threshold,
                "strong_continuation_ratio": config.strong_continuation_ratio,
                "promotion_change_pct": config.promotion_change_pct,
                "large_gain_pct": config.large_gain_pct,
                "large_loss_pct": config.large_loss_pct,
                "minimum_sample_count": config.minimum_sample_count,
                "minimum_quote_coverage": config.minimum_quote_coverage,
            },
        },
    }


def _continuation_metrics(previous_stocks, quotes, current_codes, config):
    previous_codes = {str(stock.get("stock_code") or "").zfill(6) for stock in previous_stocks}
    previous_codes.discard("000000")
    current_codes.discard("000000")
    changes = []
    amplitudes = []
    promotion_count = positive_count = large_gain_count = large_loss_count = failed_limit_count = retained_count = 0
    for stock in previous_stocks:
        code = str(stock.get("stock_code") or "").zfill(6)
        if code in current_codes:
            retained_count += 1
        quote = quotes.get(code)
        if not quote:
            continue
        change_pct = _optional_float(quote.get("change_pct"))
        if change_pct is None:
            continue
        changes.append(change_pct)
        previous_close = _optional_float(quote.get("previous_close"))
        high = _optional_float(quote.get("high_price"))
        low = _optional_float(quote.get("low_price"))
        high_pct = None
        if previous_close and previous_close > 0 and high is not None and low is not None:
            amplitudes.append((high - low) / previous_close * 100)
            high_pct = (high / previous_close - 1) * 100
        promotion_count += change_pct >= config.promotion_change_pct
        positive_count += change_pct > 0
        large_gain_count += change_pct >= config.large_gain_pct
        large_loss_count += change_pct <= config.large_loss_pct
        failed_limit_count += high_pct is not None and high_pct >= config.promotion_change_pct and change_pct < config.promotion_change_pct
    pool_count = len(previous_stocks)
    valid_count = len(changes)
    new_promotion_count = len(current_codes - previous_codes)
    return {
        "previous_stock_pool_count": pool_count,
        "valid_sample_count": valid_count,
        "quote_coverage": _percentage(valid_count, pool_count) if pool_count else None,
        "average_change_pct": _average(changes),
        "median_change_pct": _round(statistics.median(changes), 2) if changes else None,
        "average_amplitude_pct": _average(amplitudes),
        "change_stddev": _round(statistics.pstdev(changes), 2) if len(changes) > 1 else 0.0 if changes else None,
        "promotion_count": promotion_count,
        "promotion_rate": _percentage(promotion_count, pool_count) if pool_count else None,
        "new_promotion_count": new_promotion_count,
        "new_promotion_rate": _percentage(new_promotion_count, pool_count) if pool_count else None,
        "positive_count": positive_count,
        "positive_rate": _percentage(positive_count, valid_count) if valid_count else None,
        "large_gain_count": large_gain_count,
        "large_gain_rate": _percentage(large_gain_count, valid_count) if valid_count else None,
        "large_loss_count": large_loss_count,
        "large_loss_rate": _percentage(large_loss_count, valid_count) if valid_count else None,
        "failed_limit_count": failed_limit_count,
        "failed_limit_rate": _percentage(failed_limit_count, valid_count) if valid_count else None,
        "retained_count": retained_count,
        "retained_rate": _percentage(retained_count, pool_count) if pool_count else None,
    }


def _heat_stage(current_count, list_complete, config):
    if not list_complete:
        return "数据缺失"
    count = _int(current_count)
    if count >= config.climax_threshold:
        return "高潮"
    if count >= config.selection_threshold:
        return "升温"
    if count > 0:
        return "活跃"
    return "未上榜"


def _continuation_state(metrics, list_complete, config):
    if not list_complete:
        return "数据缺失", "上一交易日榜单数据缺失"
    pool_count = _int(metrics.get("previous_stock_pool_count"))
    if pool_count <= 0:
        return "无前日样本", "上一交易日该板块没有落库股票池"
    valid_count = _int(metrics.get("valid_sample_count"))
    coverage = _float(metrics.get("quote_coverage"))
    average_change = _float(metrics.get("average_change_pct"))
    positive_rate = _float(metrics.get("positive_rate"))
    promotion_count = _int(metrics.get("promotion_count"))
    new_promotion_count = _int(metrics.get("new_promotion_count"))
    large_loss_rate = _float(metrics.get("large_loss_rate"))
    average_amplitude = _float(metrics.get("average_amplitude_pct"))
    change_stddev = _float(metrics.get("change_stddev"))
    threshold = max(1, math.ceil(pool_count * config.strong_continuation_ratio))
    strong_matches = []
    if promotion_count >= threshold:
        strong_matches.append(f"旧池晋级{promotion_count}只")
    if new_promotion_count >= threshold:
        strong_matches.append(f"新增涨停{new_promotion_count}只")
    if strong_matches:
        return "强势延续", f"上一日股票池{pool_count}只、晋级门槛{threshold}只，{'、'.join(strong_matches)}达到门槛"
    if promotion_count > 0:
        return "分化", f"上一日股票池{pool_count}只中有{promotion_count}只继续涨停，未达到{threshold}只强势延续门槛"
    if valid_count < config.minimum_sample_count or coverage < config.minimum_quote_coverage:
        return "数据不足", f"有效样本{valid_count}只，行情覆盖率{coverage:.1f}%"
    if average_change <= -2 or large_loss_rate >= 30 or (positive_rate <= 30 and average_change < 0):
        return "退潮", "平均涨幅、红盘率或大跌率达到退潮阈值"
    if average_change > 0 and (positive_rate < 60 or change_stddev >= 4):
        return "分化", "板块平均上涨，但红盘覆盖不足或个股涨幅离散较大"
    if average_change <= 0 or (average_amplitude >= 6 and positive_rate < 60):
        return "分歧", "平均涨幅或振幅结构显示分歧"
    return "良性承接", "平均涨幅、红盘率和波动结构保持良性"


def _overall_status(heat_stage, continuation_state, previous_count, current_count, config):
    if heat_stage == "高潮":
        return "高潮"
    if heat_stage == "数据缺失" or continuation_state == "数据缺失":
        return "数据缺失"
    previous_count, current_count = max(_int(previous_count), 0), max(_int(current_count), 0)
    if heat_stage == "未上榜" and previous_count > 0:
        return "退潮"
    if current_count <= 0:
        return "沉寂"
    if continuation_state == "分化":
        return "分化"
    previous_selected = previous_count >= config.selection_threshold
    current_selected = current_count >= config.selection_threshold
    negative = {"分化", "分歧", "退潮"}
    if not previous_selected and not current_selected:
        return continuation_state if continuation_state in negative else heat_stage
    if not previous_selected and current_selected:
        return heat_stage
    if previous_selected and not current_selected:
        if continuation_state == "强势延续":
            return "强势延续"
        if continuation_state == "退潮" or current_count / previous_count <= 0.2:
            return "退潮"
        return "分化"
    if continuation_state in {"强势延续", "良性承接", "分化", "分歧", "退潮"}:
        return continuation_state
    return heat_stage


def _emotion_score(metrics, current_count, list_complete, heat_stage, config):
    count = _int(current_count) if list_complete else 0
    heat_score = min(max(count, 0), config.climax_threshold) / config.climax_threshold * config.climax_score
    pool_count = _int(metrics.get("previous_stock_pool_count"))
    valid_count = _int(metrics.get("valid_sample_count"))
    if pool_count <= 0 or valid_count <= 0:
        score = heat_score
    else:
        continuation_score = (
            50 + _clamp(_float(metrics.get("average_change_pct")), -5, 5) * 4
            + (_float(metrics.get("positive_rate")) - 50) * 0.25
            + min(_float(metrics.get("promotion_rate")), 50) * 0.30
            - _float(metrics.get("large_loss_rate")) * 0.20
        )
        score = heat_score + (continuation_score - 50) * _sample_confidence(metrics) * config.continuation_weight
    if heat_stage == "高潮":
        score = config.climax_score
    return _round(_clamp(score, 0, 100), 1)


def _calibrate_score(score, status, heat_stage, config):
    if heat_stage == "高潮":
        return _round(config.climax_score, 1)
    limits = {"强势延续": 99, "良性承接": 95, "升温": 99, "分化": 85, "活跃": 99, "分歧": 70, "数据不足": 70, "退潮": 40, "沉寂": 20, "数据缺失": 0}
    maximum = min(limits.get(status, 99), 99)
    if status == "退潮" and heat_stage == "未上榜":
        maximum = min(maximum, 30)
    return _round(_clamp(min(_float(score), maximum), 0, 100), 1)


def _sample_confidence(metrics):
    valid_count = _int(metrics.get("valid_sample_count"))
    coverage = _clamp(_float(metrics.get("quote_coverage")), 0, 100)
    return _round(min(valid_count / 5, 1) * coverage / 100, 2)


def _decision_summary(pool_count, previous_count, current_count, metrics, heat_stage, continuation_state, status, config):
    previous_count, current_count = _int(previous_count), _int(current_count)
    if heat_stage == "未上榜" and previous_count > 0:
        return f"上一交易日板块上榜{previous_count}只，今日未上榜，按热度消失判定为退潮。"
    if pool_count <= 0:
        return f"板块上榜数量由{previous_count}只变为{current_count}只；上一交易日无可跟踪股票池，综合判定为{status}。"
    return (
        f"板块上榜数量由{previous_count}只变为{current_count}只；前日股票池{pool_count}只，"
        f"今日平均涨幅{_format_pct(metrics.get('average_change_pct'))}，旧池晋级{_int(metrics.get('promotion_count'))}只，"
        f"新增涨停{_int(metrics.get('new_promotion_count'))}只；承接情绪为{continuation_state}，综合判定为{status}。"
    )


def _deduplicate(rows):
    result = {}
    for row in rows or []:
        code = str(row.get("stock_code") or "").zfill(6)
        if code != "000000":
            result[code] = row
    return list(result.values())


def _average(values):
    return _round(sum(values) / len(values), 2) if values else None


def _percentage(value, total):
    return _round(value / total * 100, 1) if total else None


def _format_pct(value):
    number = _optional_float(value)
    return "-" if number is None else f"{number:.1f}%"


def _clamp(value, minimum, maximum):
    return max(minimum, min(maximum, value))


def _int(value):
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _optional_int(value):
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _float(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _optional_float(value):
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _round(value, digits=2):
    return None if value is None else round(float(value), digits)
