def calculate_index_cycle(index_rows, market_rows):
    if not index_rows:
        return {"status": "empty", "error_message": "index_daily has no index data"}

    closes = [_float(row.get("close_price")) for row in index_rows]
    turnovers = [_float(row.get("turnover")) for row in index_rows]
    latest_index = index_rows[-1]
    trade_date = int(latest_index.get("trade_date") or 0)
    market = _matching_breadth(market_rows, trade_date)
    averages = {
        "ma5": _moving_average(closes, 5),
        "ma10": _moving_average(closes, 10),
        "ma20": _moving_average(closes, 20),
        "ma60": _moving_average(closes, 60),
    }
    slopes = {
        "ma5": _moving_average_slope(closes, 5, 3),
        "ma10": _moving_average_slope(closes, 10, 5),
        "ma20": _moving_average_slope(closes, 20, 5),
    }
    close = _float(latest_index.get("close_price"))
    index_turnover_ratio = _ratio(latest_index.get("turnover"), _average(turnovers[-20:]))
    market_turnover_ratio = _market_turnover_ratio(market_rows, market)
    scores = _score_components(
        close,
        averages,
        slopes,
        market,
        index_turnover_ratio,
        market_turnover_ratio,
    )
    score = round(sum(scores.values()), 1)
    state = _cycle_state(score, close, averages, slopes, market)
    return {
        "status": "success",
        "index_name": "上证指数",
        "trade_date": trade_date,
        "cycle_state": state,
        "cycle_score": score,
        "summary": _summary(state, score, close, averages, market),
        "index_quote": {
            "open_price": _round(latest_index.get("open_price"), 2),
            "close_price": _round(latest_index.get("close_price"), 2),
            "high_price": _round(latest_index.get("high_price"), 2),
            "low_price": _round(latest_index.get("low_price"), 2),
            "change_pct": _round(latest_index.get("change_pct"), 2),
            "turnover": _round(latest_index.get("turnover"), 2),
            "index_turnover_ratio": _round(index_turnover_ratio, 2),
        },
        "moving_averages": {key: _round(value, 2) for key, value in averages.items()},
        "moving_average_slopes": {key: _round(value, 2) for key, value in slopes.items()},
        "market_breadth": _format_breadth(market, market_turnover_ratio),
        "score_components": {key: _round(value, 1) for key, value in scores.items()},
        "signals": _signals(close, averages, slopes, market, index_turnover_ratio, market_turnover_ratio),
        "recent_trend": _recent_trend(index_rows, market_rows),
        "volatility_chart": _volatility_chart(index_rows, market_rows),
    }


def _matching_breadth(rows, trade_date):
    candidates = [row for row in rows if int(row.get("trade_date") or 0) <= trade_date]
    return candidates[-1] if candidates else rows[-1] if rows else {}


def _score_components(close, averages, slopes, market, index_turnover_ratio, market_turnover_ratio):
    trend = 0
    for points, name in ((5, "ma5"), (6, "ma10"), (8, "ma20"), (8, "ma60")):
        if close > averages.get(name, 0):
            trend += points
    if slopes.get("ma5", 0) > 0:
        trend += 4
    if slopes.get("ma10", 0) > 0:
        trend += 4

    total = max(_int(market.get("total_count")), 1)
    advancing_ratio = _int(market.get("up_count")) / total
    strong_balance = (_int(market.get("up_gt5_count")) - _int(market.get("down_lt5_count"))) / total
    average_change = _float(market.get("avg_pct_chg"))
    breadth = _clamp(
        advancing_ratio * 18 + ((strong_balance + 0.05) / 0.1) * 5 + ((average_change + 1) / 2) * 2,
        0,
        25,
    )
    limit_structure = _clamp(
        10 + _int(market.get("limit_up_count")) * 0.35 - _int(market.get("limit_down_count")) * 1.1,
        0,
        20,
    )
    turnover_ratio = max(index_turnover_ratio, market_turnover_ratio)
    if turnover_ratio >= 1.4:
        volume = 10
    elif turnover_ratio >= 1.15:
        volume = 9
    elif turnover_ratio >= 0.95:
        volume = 7
    elif turnover_ratio >= 0.75:
        volume = 5
    else:
        volume = 2
    risk_appetite = _clamp(
        5 + _int(market.get("up_gt5_count")) * 0.08 - _int(market.get("down_lt5_count")) * 0.12 + average_change,
        0,
        10,
    )
    return {
        "trend": _clamp(trend, 0, 35),
        "breadth": breadth,
        "limit_structure": limit_structure,
        "volume": volume,
        "risk_appetite": risk_appetite,
    }


def _cycle_state(score, close, averages, slopes, market):
    total = max(_int(market.get("total_count")), 1)
    advancing_ratio = _int(market.get("up_count")) / total
    trend_down = close < averages.get("ma20", 0) and slopes.get("ma5", 0) < 0
    if trend_down and (
        advancing_ratio < 0.42
        or _int(market.get("limit_down_count")) > _int(market.get("limit_up_count"))
    ):
        return "退潮"
    if score < 25:
        return "冰点"
    if score < 40:
        return "弱修复"
    if score < 60:
        return "震荡"
    if score < 75:
        return "发酵"
    if score < 88:
        return "高潮"
    return "过热高潮"


def _volatility_chart(index_rows, market_rows, limit=30):
    market_by_date = {int(row.get("trade_date") or 0): row for row in market_rows}
    closes = [_float(row.get("close_price")) for row in index_rows]
    turnovers = [_float(row.get("turnover")) for row in index_rows]
    result = []
    for index in range(max(0, len(index_rows) - limit), len(index_rows)):
        row = index_rows[index]
        trade_date = int(row.get("trade_date") or 0)
        market = market_by_date.get(trade_date, {})
        current_closes = closes[:index + 1]
        averages = {name: _moving_average(current_closes, period) for name, period in (("ma5", 5), ("ma10", 10), ("ma20", 20), ("ma60", 60))}
        slopes = {name: _moving_average_slope(current_closes, period, offset) for name, period, offset in (("ma5", 5, 3), ("ma10", 10, 5), ("ma20", 20, 5))}
        index_ratio = _ratio(row.get("turnover"), _average(turnovers[:index + 1][-20:]))
        market_ratio = _market_turnover_ratio(market_rows, market)
        scores = _score_components(_float(row.get("close_price")), averages, slopes, market, index_ratio, market_ratio)
        score = round(sum(scores.values()), 1)
        total = max(_int(market.get("total_count")), 1)
        result.append({
            "trade_date": trade_date,
            "emotion_score": score,
            "cycle_state": _cycle_state(score, _float(row.get("close_price")), averages, slopes, market),
            "close_price": _round(row.get("close_price"), 2),
            "change_pct": _round(row.get("change_pct"), 2),
            "advancing_ratio": _round(_int(market.get("up_count")) / total * 100, 1) if market else None,
        })
    return result


def _summary(state, score, close, averages, market):
    total = max(_int(market.get("total_count")), 1)
    advancing_ratio = _int(market.get("up_count")) / total * 100
    position = "上方" if close >= averages.get("ma20", 0) else "下方"
    return f"当前指数周期为{state}，情绪分 {score:.1f}。上证收盘位于 MA20 {position}，全市场上涨占比 {advancing_ratio:.1f}%。"


def _signals(close, averages, slopes, market, index_ratio, market_ratio):
    total = max(_int(market.get("total_count")), 1)
    advancing_ratio = _int(market.get("up_count")) / total * 100
    turnover_ratio = max(index_ratio, market_ratio)
    return [
        {"name": "趋势位置", "state": "强" if close > averages.get("ma20", 0) else "弱", "value": f"收盘 {close:.2f} / MA20 {averages.get('ma20', 0):.2f}", "description": "站上 MA20 代表中短期环境偏暖，跌破则指数周期承压。"},
        {"name": "均线斜率", "state": "向上" if slopes.get("ma5", 0) > 0 and slopes.get("ma10", 0) > 0 else "分歧", "value": f"MA5 {slopes.get('ma5', 0):.2f} / MA10 {slopes.get('ma10', 0):.2f}", "description": "短均线斜率反映指数修复或退潮速度。"},
        {"name": "市场宽度", "state": "强" if advancing_ratio >= 60 else "弱" if advancing_ratio < 40 else "中性", "value": f"上涨占比 {advancing_ratio:.1f}%", "description": "上涨家数越多，指数上涨越有扩散基础。"},
        {"name": "涨跌停结构", "state": "强" if _int(market.get("limit_up_count")) > _int(market.get("limit_down_count")) else "弱", "value": f"涨停 {_int(market.get('limit_up_count'))} / 跌停 {_int(market.get('limit_down_count'))}", "description": "跌停数量扩大会压制风险偏好。"},
        {"name": "量能", "state": "放量" if turnover_ratio >= 1.15 else "缩量" if turnover_ratio < 0.85 else "正常", "value": f"指数 {index_ratio:.2f}x / 全市场 {market_ratio:.2f}x", "description": "量能相对 20 日均量放大，修复和发酵更容易延续。"},
    ]


def _recent_trend(index_rows, market_rows, limit=20):
    market_by_date = {int(row.get("trade_date") or 0): row for row in market_rows}
    result = []
    for row in index_rows[-limit:]:
        trade_date = int(row.get("trade_date") or 0)
        market = market_by_date.get(trade_date, {})
        total = max(_int(market.get("total_count")), 1)
        result.append({
            "trade_date": trade_date, "close_price": _round(row.get("close_price"), 2),
            "change_pct": _round(row.get("change_pct"), 2),
            "stock_count": _int(market.get("total_count")) if market else None,
            "advancing_count": _int(market.get("up_count")) if market else None,
            "declining_count": _int(market.get("down_count")) if market else None,
            "advancing_ratio": _round(_int(market.get("up_count")) / total * 100, 1) if market else None,
            "limit_up_count": _int(market.get("limit_up_count")) if market else None,
            "limit_down_count": _int(market.get("limit_down_count")) if market else None,
        })
    return result


def _format_breadth(market, turnover_ratio):
    total = max(_int(market.get("total_count")), 1)
    return {
        "trade_date": _int(market.get("trade_date")), "stock_count": total,
        "advancing_count": _int(market.get("up_count")), "declining_count": _int(market.get("down_count")),
        "advancing_ratio": _round(_int(market.get("up_count")) / total * 100, 1),
        "advance_over_5_count": _int(market.get("up_gt5_count")),
        "decline_over_5_count": _int(market.get("down_lt5_count")),
        "limit_up_count": _int(market.get("limit_up_count")), "limit_down_count": _int(market.get("limit_down_count")),
        "average_change_pct": _round(market.get("avg_pct_chg"), 2), "turnover_ratio": _round(turnover_ratio, 2),
    }


def _market_turnover_ratio(rows, latest):
    if not latest:
        return 0
    trade_date = int(latest.get("trade_date") or 0)
    previous = [_float(row.get("amount")) for row in rows if int(row.get("trade_date") or 0) <= trade_date]
    return _ratio(latest.get("amount"), _average(previous[-20:]))


def _moving_average(values, period):
    return _average(values[-period:]) if len(values) >= period else 0


def _moving_average_slope(values, period, offset):
    if len(values) < period + offset:
        return 0
    return _average(values[-period:]) - _average(values[-period - offset:-offset])


def _average(values):
    valid = [_float(value) for value in values if value is not None]
    return sum(valid) / len(valid) if valid else 0


def _ratio(value, base):
    return _float(value) / _float(base) if _float(base) else 0


def _clamp(value, minimum, maximum):
    return max(minimum, min(maximum, _float(value)))


def _float(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _int(value):
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _round(value, digits):
    return round(_float(value), digits)
