import json

from .contracts import translate_legacy_payload


STATE_STRENGTH_RANK = {
    "高潮": 100,
    "强势延续": 90,
    "良性承接": 80,
    "升温": 70,
    "分化": 60,
    "活跃": 55,
    "分歧": 40,
    "数据不足": 30,
    "退潮": 20,
    "沉寂": 10,
    "未上榜": 5,
    "数据缺失": 0,
}


class EmotionService:
    def __init__(
        self,
        repository,
        *,
        selection_threshold: int = 8,
        climax_threshold: int = 20,
        strong_continuation_ratio: float = 0.5,
        promotion_change_pct: float = 9.5,
        climax_score: float = 100.0,
        excluded_boards=("ST板块", "公告", "其他"),
    ):
        self.repository = repository
        self.selection_threshold = selection_threshold
        self.climax_threshold = climax_threshold
        self.strong_continuation_ratio = strong_continuation_ratio
        self.promotion_change_pct = promotion_change_pct
        self.climax_score = climax_score
        self.excluded_boards = set(excluded_boards)

    def current_index_emotion(self):
        row = self.repository.latest_index_emotion()
        if not row:
            return {"status": "empty", "error_message": "No index emotion data is available"}

        persisted = _json_value(row.get("full_result_json"), {})
        if persisted:
            index_cycle = translate_legacy_payload(persisted)
            index_cycle.pop("status", None)
        else:
            index_cycle = self._index_cycle_from_row(row)
        return {"status": "success", "index_cycle": index_cycle}

    def hot_board_emotion(self, days: int = 30):
        days = max(5, min(60, int(days or 30)))
        dates = sorted(int(row["trade_date"]) for row in self.repository.recent_hot_board_dates(days))
        if not dates:
            return {"status": "empty", "error_message": "No hot-board emotion data is available"}

        grouped = {}
        for raw in self.repository.hot_board_rows(dates):
            row = dict(raw)
            row["decision_reasons"] = _json_value(row.pop("decision_reasons_json", None), {})
            board_name = row.get("board_name")
            if board_name and board_name not in self.excluded_boards:
                grouped.setdefault(board_name, []).append(row)

        boards = []
        latest_date = dates[-1]
        for board_name, trend in grouped.items():
            trend.sort(key=lambda item: int(item["trade_date"]))
            peak_count = max((int(item.get("current_board_count") or 0) for item in trend), default=0)
            if peak_count < self.selection_threshold:
                continue
            latest = next((item for item in reversed(trend) if int(item["trade_date"]) == latest_date), trend[-1])
            recent_strength = _recent_strength(trend)
            climax_dates = [
                int(item["trade_date"])
                for item in trend
                if int(item.get("current_board_count") or 0) >= self.climax_threshold
            ]
            boards.append({
                "board_name": board_name,
                "peak_count_30d": peak_count,
                "latest_climax_date": max(climax_dates) if climax_dates else None,
                "climax_count": len(climax_dates),
                "latest_status": latest.get("overall_status"),
                "latest_emotion_score": latest.get("emotion_score"),
                "recent_strength": recent_strength,
                "latest_record": latest,
                "recent_trend": trend,
                "sort_value": (
                    STATE_STRENGTH_RANK.get(latest.get("overall_status"), 0) * 1000
                    + _float_value(latest.get("emotion_score")) * 5
                    + recent_strength
                ),
            })

        boards.sort(key=lambda item: (-item["sort_value"], -item["peak_count_30d"], item["board_name"]))
        for board in boards:
            board.pop("sort_value")
        excluded = "、".join(sorted(self.excluded_boards))
        ratio = self.strong_continuation_ratio * 100
        return {
            "status": "success",
            "latest_trade_date": latest_date,
            "available_dates": dates,
            "trading_day_count": len(dates),
            "hot_board_count": len(boards),
            "boards": boards,
            "config": {
                "selection_threshold": self.selection_threshold,
                "climax_threshold": self.climax_threshold,
                "strong_continuation_ratio": self.strong_continuation_ratio,
                "excluded_boards": sorted(self.excluded_boards),
            },
            "methodology": {
                "hot_board_definition": f"近{len(dates)}个交易日内至少一天板块个股数量达到{self.selection_threshold}只，排除板块：{excluded}",
                "climax_definition": f"仅当日板块数量达到{self.climax_threshold}只触发，与平均涨幅、晋级率和情绪分无关",
                "ebb_definition": "上一交易日上榜而当日未上榜时，不受可跟踪样本数量限制，综合状态直接判定为退潮",
                "strong_continuation_definition": f"旧池晋级家数或新增涨停家数达到上一日股票池的{ratio:.0f}%",
                "dispersion_definition": f"旧池至少1只继续连板、但未达到{ratio:.0f}%强势延续门槛时判定为分化；当日未上榜仍按退潮处理",
                "positive_continuation_threshold": f"强势延续或良性承接仅在板块达到{self.selection_threshold}只入选阈值后生效；低热度小样本最多按活跃处理",
                "emotion_score_methodology": f"当日板块数量贡献0至{self.climax_score:.0f}分，承接指标仅按样本置信度小幅修正；高潮固定为{self.climax_score:.0f}分",
                "continuation_methodology": "严格使用上一交易日实际落库股票池，统计本交易日平均涨幅、振幅、晋级率等指标",
                "promotion_definition": f"当日涨幅达到{self.promotion_change_pct:g}%",
                "stock_universe": "仅统计沪深主板股票，并剔除股票名称中含ST的股票",
            },
        }

    @staticmethod
    def _index_cycle_from_row(row):
        return {
            "trade_date": row.get("trade_date"),
            "index_name": row.get("index_name"),
            "cycle_state": row.get("cycle_state"),
            "cycle_score": row.get("cycle_score"),
            "summary": row.get("summary"),
            "index_quote": {
                "open_price": row.get("open_price"),
                "close_price": row.get("close_price"),
                "high_price": row.get("high_price"),
                "low_price": row.get("low_price"),
                "change_pct": row.get("change_pct"),
                "turnover": row.get("index_turnover"),
                "index_turnover_ratio": row.get("index_turnover_ratio"),
            },
            "moving_averages": {name: row.get(name) for name in ("ma5", "ma10", "ma20", "ma60")},
            "moving_average_slopes": {name: row.get(f"{name}_slope") for name in ("ma5", "ma10", "ma20")},
            "market_breadth": _json_value(row.get("market_breadth_json"), {}),
            "signals": _json_value(row.get("signals_json"), []),
            "recent_trend": _json_value(row.get("recent_trend_json"), []),
            "volatility_chart": _json_value(row.get("volatility_chart_json"), []),
        }


def _json_value(value, default):
    if value in (None, ""):
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return default


def _recent_strength(trend):
    scores = [_float_value(item.get("emotion_score")) for item in trend[-3:]]
    if not scores:
        return 0.0
    weights = [0.2, 0.3, 0.5][-len(scores):]
    return round(sum(score * weight for score, weight in zip(scores, weights)) / sum(weights), 1)


def _float_value(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0
