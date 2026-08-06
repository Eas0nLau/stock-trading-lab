import json

from .contracts import translate_legacy_payload


class EmotionService:
    def __init__(
        self,
        repository,
        *,
        selection_threshold: int = 8,
        climax_threshold: int = 20,
        strong_continuation_ratio: float = 0.5,
        excluded_boards=("ST板块", "公告", "其他"),
    ):
        self.repository = repository
        self.selection_threshold = selection_threshold
        self.climax_threshold = climax_threshold
        self.strong_continuation_ratio = strong_continuation_ratio
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
                "latest_record": latest,
                "recent_trend": trend,
            })

        boards.sort(key=lambda item: (-(float(item.get("latest_emotion_score") or 0)), -item["peak_count_30d"], item["board_name"]))
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
