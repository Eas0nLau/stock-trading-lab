import json

import pytest

from stock_lab.modules.research import OfflineResearchProvider as PublicOfflineResearchProvider
from stock_lab.modules.research.context import ResearchExecutionError
from stock_lab.modules.research.providers import OfflineResearchProvider


def test_offline_provider_normalizes_fixture_codes_without_live_resources(tmp_path):
    fixture = tmp_path / "fixture.json"
    fixture.write_text(json.dumps({
        "securities": [{"ts_code": "1.sz", "symbol": "1", "name": "Fixture"}],
        "daily_quotes": [{
            "ts_code": "1.sz", "trade_date": 20260102, "open_price": 10,
            "high_price": 11, "low_price": 9, "close_price": 10.5,
            "previous_close": 10, "change_pct": 5, "volume": 1000, "turnover": 10000,
        }],
    }), encoding="utf-8")

    context = OfflineResearchProvider.from_json(fixture).context(20260102)

    assert context.target_date == 20260102
    assert context.market_data.security_codes() == ["000001.SZ"]
    assert context.market_data.daily_quotes()[0]["ts_code"] == "000001.SZ"


def test_builtin_offline_provider_has_no_network_or_database_capability():
    context = OfflineResearchProvider.builtin().context(20260102)
    assert context.target_date == 20260102
    assert context.query_provider.is_offline is True
    assert PublicOfflineResearchProvider is OfflineResearchProvider


def test_builtin_fixture_covers_strategy_family_data_capabilities():
    context = OfflineResearchProvider.builtin().context(20260102)
    assert context.market_data.daily_quotes()
    assert context.market_data.index_daily()
    assert context.market_data.kdj_indicators()
    assert context.market_data.intraday_bars_5m()
    assert context.market_data.dragon_tiger_listings(trade_date=20260102)


def test_offline_query_provider_reports_sql_schema_errors():
    context = OfflineResearchProvider.builtin().context(20260102)

    with pytest.raises(ResearchExecutionError, match="missing_column"):
        context.query_provider.query(
            "SELECT missing_column FROM daily_quotes",
            fetch=True,
        )


def test_offline_fixture_normalizes_domain_stock_codes():
    provider = OfflineResearchProvider({
        "dragon_tiger": [{"stock_code": "600000"}],
        "broker_listing_history": [{"stock_code": "430001"}],
        "jiuyan_actions": [{"stock_code": "1", "source_code": "sz000001"}],
        "kdj_indicators": [{"ts_code": "2", "trade_date": 20260102}],
    })

    assert provider.fixture["dragon_tiger"][0]["stock_code"] == "600000.SH"
    assert provider.fixture["broker_listing_history"][0]["stock_code"] == "430001.BJ"
    assert provider.fixture["jiuyan_actions"][0]["stock_code"] == "000001.SZ"
    assert provider.fixture["kdj_indicators"][0]["ts_code"] == "000002.SZ"


def test_offline_provider_exposes_fixture_redis_lists():
    provider = OfflineResearchProvider({"redis_lists": {"signals:1": ["first", "second"]}})

    assert provider.query_provider.cache.lrange("signals:1", 0, -1) == ["first", "second"]
    assert provider.query_provider.cache.lrange("signals:1", 1, 1) == ["second"]
