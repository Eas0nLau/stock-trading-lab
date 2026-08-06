import json
from datetime import datetime, timedelta

import pytest

from stock_lab.modules.research.providers import OfflineResearchProvider
from stock_lab.modules.research.results import SelectionResult
from stock_lab.modules.research.strategies import discover_strategies, get_strategy


FAMILY_REPRESENTATIVES = {
    "daily_quotes": "legacy_strategy_003",
    "dragon_tiger": "legacy_strategy_040",
    "jiuyan": "legacy_strategy_034",
    "fund_flow": "legacy_strategy_042",
    "kdj": "legacy_strategy_048",
    "dragon_tiger_premium": "legacy_strategy_057",
}


@pytest.mark.parametrize("identifier", [
    "legacy_strategy_003",  # volume and price
    "legacy_strategy_009",  # trend
    "legacy_strategy_035",  # new high
    "legacy_strategy_048",  # KDJ
    "legacy_strategy_052",  # Dragon Tiger with intraday confirmation
])
def test_representative_source_families_execute_with_offline_context(identifier):
    result = get_strategy(identifier).run(OfflineResearchProvider.builtin().context(20260102))
    assert isinstance(result, SelectionResult)
    assert result.strategy_id == identifier


def _qualified_security():
    return {
        "ts_code": "000001.SZ", "symbol": "000001", "name": "Fixture",
        "market": "主板", "list_status": "L",
    }


def _trend_quotes():
    dates = [
        int((datetime(2026, 1, 10) - timedelta(days=39 - index)).strftime("%Y%m%d"))
        for index in range(40)
    ]
    quotes = []
    for index, trade_date in enumerate(dates):
        close = 10 + index * 0.05
        high = 15.0 if index == 5 else close + 0.1
        open_price = close - 0.05
        change_pct = 1.0
        if index == 34:
            open_price = close + 0.05
            change_pct = -0.5
        if index == 39:
            close = 16.0
            high = 16.2
            open_price = 15.8
        quotes.append({
            "ts_code": "000001.SZ", "trade_date": trade_date,
            "open_price": open_price, "high_price": high, "low_price": open_price - 0.1,
            "close_price": close, "previous_close": close - 0.1,
            "change_pct": change_pct, "volume": 1000 + index,
            "turnover": 200000 + index * 1000, "stock_name": "Fixture",
        })
    return quotes


def test_non_empty_representatives_cover_every_declared_strategy_family():
    declared = {entry.metadata.strategy_family for entry in discover_strategies()}

    assert set(FAMILY_REPRESENTATIVES) == declared
    assert all(
        get_strategy(identifier).metadata.strategy_family == family
        for family, identifier in FAMILY_REPRESENTATIVES.items()
    )


@pytest.mark.parametrize("identifier", [FAMILY_REPRESENTATIVES["daily_quotes"], "legacy_strategy_009", "legacy_strategy_035"])
def test_price_trend_and_new_high_families_select_non_empty_fixture(identifier):
    fixture = {"securities": [_qualified_security()], "daily_quotes": _trend_quotes()}

    result = get_strategy(identifier).run(OfflineResearchProvider(fixture).context(20260110))

    assert result.rows
    assert result.rows[0]["ts_code"] == "000001.SZ"


def test_jiuyan_family_selects_non_empty_fixture():
    fixture = {
        "securities": [_qualified_security()],
        "daily_quotes": _trend_quotes()[-3:],
        "jiuyan_actions": [{
            "trade_date": 20260110, "board_name": "Bank", "board_stock_count": 12,
            "stock_code": "000001", "stock_name": "Fixture", "source_code": "sz000001",
            "limit_up_at": "09:30:00",
        }],
    }

    result = get_strategy(FAMILY_REPRESENTATIVES["jiuyan"]).run(
        OfflineResearchProvider(fixture).context(20260110)
    )

    assert result.rows
    assert result.rows[0]["ts_code"] == "000001.SZ"


def test_fund_flow_family_selects_non_empty_fixture():
    snapshot = [{
        "时间": "09:35", "板块代码": "BK001", "板块名称": "Banks",
        "龙头": "Fixture", "资金净流入(亿)": 60000,
    }]
    fixture = {
        "securities": [_qualified_security()],
        "daily_quotes": [{
            **_trend_quotes()[-1], "total_market_value": 6000000,
        }],
        "redis_lists": {"fund_flow:history:20260110": [json.dumps(snapshot)]},
    }

    result = get_strategy(FAMILY_REPRESENTATIVES["fund_flow"]).run(
        OfflineResearchProvider(fixture).context(20260110)
    )

    assert result.rows
    assert result.rows[0]["ts_code"] == "000001.SZ"


def test_kdj_family_selects_non_empty_fixture():
    fixture = {
        "securities": [_qualified_security()],
        "daily_quotes": _trend_quotes()[-2:],
        "kdj_indicators": [
            {"ts_code": "000001", "trade_date": 20260109, "d_value": 20, "j_value": 10},
            {"ts_code": "000001", "trade_date": 20260110, "d_value": 10, "j_value": 20},
        ],
    }

    result = get_strategy(FAMILY_REPRESENTATIVES["kdj"]).run(
        OfflineResearchProvider(fixture).context(20260110)
    )

    assert result.rows
    assert result.rows[0]["ts_code"] == "000001.SZ"


def test_dragon_tiger_listing_count_family_uses_canonical_lookup_keys():
    target_date = 20260120
    dates = [
        int((datetime(2026, 1, 20) - timedelta(days=19 - index)).strftime("%Y%m%d"))
        for index in range(20)
    ]
    closes = [20.0] * 15 + [10.2, 10.1, 10.0, 9.9, 10.0]
    volumes = [1000.0] * 15 + [500.0, 400.0, 300.0, 100.0, 200.0]
    quotes = [{
        "ts_code": "000001.SZ", "trade_date": trade_date,
        "open_price": close - 0.1, "high_price": close + 0.2,
        "low_price": close - 0.2, "close_price": close,
        "previous_close": close - 0.1, "change_pct": 1.0,
        "volume": volume, "turnover": volume * close,
        "stock_name": "Fixture",
    } for trade_date, close, volume in zip(dates, closes, volumes)]
    fixture = {
        "securities": [_qualified_security()],
        "daily_quotes": quotes,
        "dragon_tiger": [{
            "data_id": f"listing-{index}", "stock_code": "000001",
            "stock_name": "Fixture", "trade_date": target_date,
        } for index in range(11)],
    }

    result = get_strategy(FAMILY_REPRESENTATIVES["dragon_tiger"]).run(
        OfflineResearchProvider(fixture).context(target_date)
    )

    assert result.rows
    assert result.rows[0]["ts_code"] == "000001.SZ"
    assert result.rows[0]["龙虎榜上榜次数"] == 11


@pytest.mark.parametrize("identifier", ["legacy_strategy_052", FAMILY_REPRESENTATIVES["dragon_tiger_premium"]])
def test_dragon_tiger_premium_family_returns_canonical_qualified_code(identifier):
    latest = 20260110
    brokers = (("B1", "Broker One", "000101"), ("B2", "Broker Two", "000102"), ("B3", "Broker Three", "000103"))
    history = []
    quotes = []
    for broker_index, (broker_id, broker_name, historical_code) in enumerate(brokers):
        for trade_date in (20260101, 20260104, 20260107):
            history.append({
                "broker_id": broker_id, "broker_name": broker_name, "stock_code": historical_code,
                "stock_name": "Historical", "listing_reason": "Reason", "trade_date": trade_date,
                "net_amount": 3000,
            })
            quotes.extend([
                {"ts_code": historical_code + ".SZ", "trade_date": trade_date, "open_price": 9, "close_price": 9},
                {"ts_code": historical_code + ".SZ", "trade_date": trade_date + 1, "open_price": 10, "close_price": 10},
                {"ts_code": historical_code + ".SZ", "trade_date": trade_date + 2, "open_price": 11 + broker_index, "close_price": 11 + broker_index},
            ])
        history.append({
            "broker_id": broker_id, "broker_name": broker_name, "stock_code": "000001",
            "stock_name": "Fixture", "listing_reason": "Reason", "trade_date": latest,
            "net_amount": 3000,
        })
    fixture = {
        "securities": [{"ts_code": "000001.SZ", "symbol": "000001", "name": "Fixture"}],
        "daily_quotes": quotes + [{
            "ts_code": "000001.SZ", "trade_date": latest, "open_price": 10,
            "high_price": 11, "low_price": 9, "close_price": 10.5,
            "previous_close": 10, "change_pct": 5, "volume": 1000,
            "turnover": 10000, "stock_name": "Fixture",
        }],
        "dragon_tiger": [{
            "stock_code": "000001", "stock_name": "Fixture", "detail_type": "Reason",
            "trade_date": latest, "buy_1_broker_name": "Broker One",
            "buy_2_broker_name": "Broker Two", "buy_3_broker_name": "Broker Three",
            "buy_4_broker_name": None, "buy_5_broker_name": None,
        }],
        "broker_listing_history": history,
    }
    context = OfflineResearchProvider(fixture).context(latest).with_parameters(start_date=20260101)

    result = get_strategy(identifier).run(context)

    assert len(result.rows) == 1
    assert result.rows[0]["ts_code"] == "000001.SZ"
    assert result.rows[0]["stock_name"] == "Fixture"
    assert result.rows[0]["trade_date"] == latest
