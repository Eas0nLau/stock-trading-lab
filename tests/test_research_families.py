import pytest

from stock_lab.modules.research.providers import OfflineResearchProvider
from stock_lab.modules.research.results import SelectionResult
from stock_lab.modules.research.strategies import get_strategy


@pytest.mark.parametrize("identifier", [
    "legacy_strategy_003",  # volume and price
    "legacy_strategy_009",  # trend
    "legacy_strategy_035",  # new high
    "legacy_strategy_048",  # KDJ
    "legacy_strategy_052",  # Dragon Tiger with intraday confirmation
])
def test_representative_source_families_select_with_offline_context(identifier):
    result = get_strategy(identifier).run(OfflineResearchProvider.builtin().context(20260102))
    assert isinstance(result, SelectionResult)
    assert result.strategy_id == identifier


def test_dragon_tiger_premium_family_returns_canonical_qualified_code():
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
        "daily_quotes": quotes,
        "dragon_tiger": [{
            "stock_code": "000001", "stock_name": "Fixture", "detail_type": "Reason",
            "trade_date": latest, "buy_1_broker_name": "Broker One",
            "buy_2_broker_name": "Broker Two", "buy_3_broker_name": "Broker Three",
            "buy_4_broker_name": None, "buy_5_broker_name": None,
        }],
        "broker_listing_history": history,
    }
    context = OfflineResearchProvider(fixture).context(latest).with_parameters(start_date=20260101)

    result = get_strategy("legacy_strategy_057").run(context)

    assert result.rows == [{
        "ts_code": "000001.SZ", "stock_name": "Fixture", "trade_date": latest,
    }]
