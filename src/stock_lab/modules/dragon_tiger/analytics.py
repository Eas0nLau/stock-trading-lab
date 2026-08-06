from datetime import datetime, timedelta


EXCLUDED_BROKER_NAMES = {"深股通专用", "沪股通专用"}


def _value(row, name):
    if isinstance(row, dict):
        return row.get(name)
    return getattr(row, name)


def analyze_broker_premium(
    start_date,
    latest_date,
    repository,
    market_data_repository,
    net_buy_threshold=2000,
    average_return_threshold=2,
    minimum_samples=3,
):
    start_date = int(start_date)
    latest_date = int(latest_date)
    listings = repository.listings(trade_date=latest_date)
    history = repository.broker_history(start_date=start_date, end_date=latest_date)

    buyer_names = {}
    for listing in listings:
        key = (_value(listing, "stock_name"), _value(listing, "detail_type"))
        buyer_names.setdefault(key, [])
        for rank in range(1, 6):
            buyer_names[key].append(_value(listing, f"buy_{rank}_broker_name"))

    stats = {}
    latest_rows = []
    for row in history:
        net_amount = _value(row, "net_amount")
        if net_amount is None or net_amount < net_buy_threshold:
            continue
        broker_id = _value(row, "broker_id")
        broker_name = _value(row, "broker_name")
        if broker_name in EXCLUDED_BROKER_NAMES:
            continue
        stats.setdefault(broker_id, {"count": 0, "return_total": 0.0})

        stock_name = _value(row, "stock_name")
        reason = _value(row, "listing_reason")
        if (
            int(_value(row, "trade_date")) == latest_date
            and broker_name in buyer_names.get((stock_name, reason), ())
        ):
            latest_rows.append(row)

        trade_date = int(_value(row, "trade_date"))
        quote_end_date = min(
            int((datetime.strptime(str(trade_date), "%Y%m%d") + timedelta(days=20)).strftime("%Y%m%d")),
            latest_date,
        )
        quotes = market_data_repository.daily_quotes(
            [_value(row, "stock_code")], trade_date, quote_end_date
        )
        quotes = sorted(quotes, key=lambda quote: int(_value(quote, "trade_date")))
        if len(quotes) < 3:
            continue
        next_open = _value(quotes[1], "open_price")
        following_open = _value(quotes[2], "open_price")
        if next_open in (None, 0) or following_open is None:
            continue
        stats[broker_id]["count"] += 1
        stats[broker_id]["return_total"] += (following_open - next_open) / next_open * 100

    average_returns = {
        broker_id: values["return_total"] / values["count"] if values["count"] else 0.0
        for broker_id, values in stats.items()
    }
    lineup_returns = {}
    for row in latest_rows:
        stock_code = str(_value(row, "stock_code"))
        reason = _value(row, "listing_reason")
        lineup_returns.setdefault(stock_code, {}).setdefault(reason, []).append(
            average_returns[_value(row, "broker_id")]
        )

    selected_codes = set()
    ranking_scores = {}
    for stock_code, reason_groups in lineup_returns.items():
        for returns in reason_groups.values():
            unique_returns = set(returns)
            average_return = sum(unique_returns) / len(unique_returns)
            ranking_scores[stock_code] = average_return
            if len(unique_returns) > 2 and average_return > average_return_threshold:
                selected_codes.add(stock_code)

    ranked_codes = sorted(selected_codes, key=lambda code: ranking_scores[code], reverse=True)
    return [int(code) for code in ranked_codes]
