from stock_lab.modules.dragon_tiger.analytics import analyze_broker_premium


class FakeDragonTigerRepository:
    def __init__(self, listings, history):
        self._listings = listings
        self._history = history
        self.calls = []

    def listings(self, **filters):
        self.calls.append(("listings", filters))
        return self._listings

    def broker_history(self, start_date=None, end_date=None, broker_ids=None):
        self.calls.append(("history", {"start_date": start_date, "end_date": end_date}))
        return self._history


class FakeMarketDataRepository:
    def __init__(self, returns):
        self.returns = returns
        self.calls = []

    def daily_quotes(self, stock_codes=None, start_date=None, end_date=None):
        key = (stock_codes[0], start_date)
        self.calls.append((stock_codes, start_date, end_date))
        start = 10.0
        gain = self.returns.get(key)
        if gain is None:
            return []
        return [
            {"trade_date": start_date, "open_price": 9.0},
            {"trade_date": start_date + 1, "open_price": start},
            {"trade_date": start_date + 2, "open_price": start * (1 + gain / 100)},
        ]


def _history(broker_id, broker_name, trade_date, stock_code="000001", reason="Reason", net=3000):
    return {
        "data_id": f"{broker_id}_{trade_date}_{stock_code}_{reason}",
        "broker_id": broker_id,
        "broker_name": broker_name,
        "trade_date": trade_date,
        "stock_name": "Ping An",
        "stock_code": stock_code,
        "listing_reason": reason,
        "change_pct": 7.0,
        "buy_amount": 4000,
        "sell_amount": 1000,
        "net_amount": net,
        "board_name": None,
    }


def test_analysis_selects_latest_stock_when_three_broker_lineup_has_premium():
    latest_date = 20260806
    listing = {
        "stock_code": "000001",
        "stock_name": "Ping An",
        "detail_type": "Reason",
        **{f"buy_{rank}_broker_name": name for rank, name in enumerate(["One", "Two", "Three", None, None], 1)},
    }
    history = []
    returns = {}
    for broker_id, name, stock_code, gains in (
        ("B1", "One", "000001", [3.0, 4.0, 5.0]),
        ("B2", "Two", "600000", [2.5, 3.0, 3.5]),
        ("B3", "Three", "300001", [2.1, 2.2, 2.3]),
    ):
        for offset, gain in enumerate(gains, 1):
            trade_date = 20260700 + offset
            history.append(_history(broker_id, name, trade_date, stock_code=stock_code))
            returns[(stock_code, trade_date)] = gain
        history.append(_history(broker_id, name, latest_date))
    repository = FakeDragonTigerRepository([listing], history)
    market_data = FakeMarketDataRepository(returns)

    result = analyze_broker_premium(20260701, latest_date, repository, market_data)

    assert result == ["000001.SZ"]
    assert repository.calls[0] == ("listings", {"trade_date": latest_date})
    assert all(call[2] <= latest_date for call in market_data.calls)


def test_analysis_excludes_connect_seats_low_net_rows_and_short_quote_histories():
    listing = {
        "stock_code": "000001",
        "stock_name": "Ping An",
        "detail_type": "Reason",
        **{f"buy_{rank}_broker_name": name for rank, name in enumerate(["沪股通专用", "Low Net", "No Quotes", None, None], 1)},
    }
    history = [
        _history("CONNECT", "沪股通专用", 20260701),
        _history("LOW", "Low Net", 20260701, net=1999),
        _history("EMPTY", "No Quotes", 20260701),
        _history("CONNECT", "沪股通专用", 20260806),
        _history("LOW", "Low Net", 20260806, net=1999),
        _history("EMPTY", "No Quotes", 20260806),
    ]

    result = analyze_broker_premium(
        20260701,
        20260806,
        FakeDragonTigerRepository([listing], history),
        FakeMarketDataRepository({}),
    )

    assert result == []


def test_analysis_ranks_multiple_reasons_by_highest_qualifying_reason_score():
    latest_date = 20260806
    lineups = [
        ("000001", "Reason A", [("A1", "A One", 5.0), ("A2", "A Two", 6.0), ("A3", "A Three", 7.0)]),
        ("000001", "Reason B", [("B1", "B One", 2.2), ("B2", "B Two", 2.4), ("B3", "B Three", 2.6)]),
        ("000002", "Reason C", [("C1", "C One", 3.0), ("C2", "C Two", 3.2), ("C3", "C Three", 3.4)]),
    ]
    listings = []
    history = []
    returns = {}
    historical_code = 100
    for stock_code, reason, brokers in lineups:
        listings.append({
            "stock_code": stock_code,
            "stock_name": "Ping An",
            "detail_type": reason,
            **{f"buy_{rank}_broker_name": brokers[rank - 1][1] if rank <= 3 else None for rank in range(1, 6)},
        })
        for broker_id, broker_name, gain in brokers:
            historical_code += 1
            history_code = str(historical_code).zfill(6)
            history.append(_history(broker_id, broker_name, 20260701, stock_code=history_code))
            history.append(_history(
                broker_id,
                broker_name,
                latest_date,
                stock_code=stock_code,
                reason=reason,
            ))
            returns[(history_code, 20260701)] = gain

    result = analyze_broker_premium(
        20260701,
        latest_date,
        FakeDragonTigerRepository(listings, history),
        FakeMarketDataRepository(returns),
        minimum_samples=1,
    )

    assert result == ["000001.SZ", "000002.SZ"]


def test_analysis_excludes_brokers_below_minimum_sample_count():
    latest_date = 20260806
    listing = {
        "stock_code": "000001",
        "stock_name": "Ping An",
        "detail_type": "Reason",
        **{f"buy_{rank}_broker_name": name for rank, name in enumerate(["One", "Two", "Three", None, None], 1)},
    }
    history = []
    returns = {}
    for broker_id, name, stock_code, gains in (
        ("B1", "One", "000101", [3.0, 4.0, 5.0]),
        ("B2", "Two", "000102", [4.0, 5.0, 6.0]),
        ("B3", "Three", "000103", [6.0, 7.0]),
    ):
        for offset, gain in enumerate(gains, 1):
            trade_date = 20260700 + offset
            history.append(_history(broker_id, name, trade_date, stock_code=stock_code))
            returns[(stock_code, trade_date)] = gain
        history.append(_history(broker_id, name, latest_date))

    result = analyze_broker_premium(
        20260701,
        latest_date,
        FakeDragonTigerRepository([listing], history),
        FakeMarketDataRepository(returns),
        minimum_samples=3,
    )

    assert result == []
