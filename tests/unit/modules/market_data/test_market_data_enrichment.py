from types import SimpleNamespace

import pytest

from stock_lab.modules.market_data.helpers import (
    dde_from_source,
    market_cap_from_source,
)
from stock_lab.modules.market_data.repository import MarketDataRepository


class Connection:
    def __init__(self):
        self.calls = []

    def execute(self, statement, params):
        self.calls.append((str(statement), params))
        return SimpleNamespace(rowcount=len(params))


class Begin:
    def __init__(self, connection):
        self.connection = connection

    def __enter__(self):
        return self.connection

    def __exit__(self, *_args):
        return False


class Engine:
    def __init__(self):
        self.connection = Connection()

    def begin(self):
        return Begin(self.connection)


def test_market_cap_normalization_preserves_tushare_units():
    row = market_cap_from_source({
        "ts_code": "000001.SZ",
        "trade_date": "20260807",
        "total_mv": "10000",
        "circ_mv": "8000",
        "free_share": "500",
    }, close_price=12.5)

    assert row == {
        "ts_code": "000001.SZ",
        "trade_date": 20260807,
        "total_market_value": 10000.0,
        "circulating_market_value": 8000.0,
        "free_float_shares": 500.0,
        "free_float_market_value": 6250.0,
    }


def test_market_cap_normalization_converts_nan_to_none():
    row = market_cap_from_source({
        "ts_code": "000001.SZ",
        "trade_date": "20260807",
        "total_mv": float("nan"),
        "circ_mv": float("inf"),
        "free_share": float("nan"),
    }, close_price=12.5)

    assert row["total_market_value"] is None
    assert row["circulating_market_value"] is None
    assert row["free_float_shares"] is None
    assert row["free_float_market_value"] is None


def test_dde_normalization_keeps_yuan():
    assert dde_from_source({
        "stock_code": "1",
        "trade_date": "2026-08-07",
        "dde": "325000000",
    }) == {
        "ts_code": "000001.SZ",
        "trade_date": 20260807,
        "dde_net_amount": 325000000.0,
    }


def test_enrichment_update_preserves_non_null_target_for_null_source():
    engine = Engine()
    repository = MarketDataRepository(lambda *_args, **_kwargs: [], engine)

    count = repository.update_daily_quote_enrichment(
        [{
            "ts_code": "000001.SZ",
            "trade_date": 20260807,
            "total_market_value": None,
            "circulating_market_value": 8000,
        }],
        fields=("total_market_value", "circulating_market_value"),
    )

    sql, params = engine.connection.calls[0]
    assert count == 1
    assert "`total_market_value` = COALESCE(:total_market_value, `total_market_value`)" in sql
    assert "`circulating_market_value` = COALESCE(:circulating_market_value, `circulating_market_value`)" in sql
    assert "WHERE `ts_code` = :ts_code AND `trade_date` = :trade_date" in sql
    assert params[0]["ts_code"] == "000001.SZ"


def test_only_missing_enrichment_does_not_replace_existing_value():
    engine = Engine()
    repository = MarketDataRepository(lambda *_args, **_kwargs: [], engine)

    repository.update_daily_quote_enrichment(
        [{
            "ts_code": "000001.SZ",
            "trade_date": 20260807,
            "dde_net_amount": 100,
        }],
        fields=("dde_net_amount",),
        only_missing=True,
    )

    sql = engine.connection.calls[0][0]
    assert (
        "`dde_net_amount` = CASE WHEN `dde_net_amount` IS NULL "
        "THEN :dde_net_amount ELSE `dde_net_amount` END"
    ) in sql


def test_enrichment_rejects_unknown_fields():
    repository = MarketDataRepository(lambda *_args, **_kwargs: [], Engine())

    with pytest.raises(ValueError, match="Unsupported daily quote enrichment"):
        repository.update_daily_quote_enrichment(
            [{"ts_code": "000001.SZ", "trade_date": 20260807, "close_price": 10}],
            fields=("close_price",),
        )


def test_base_quote_upsert_does_not_erase_enrichment_with_nulls():
    engine = Engine()
    repository = MarketDataRepository(lambda *_args, **_kwargs: [], engine)

    repository.upsert_daily_quotes([{
        "data_id": "quote-1",
        "ts_code": "000001.SZ",
        "trade_date": 20260807,
        "close_price": 12.5,
        "total_market_value": None,
        "dde_net_amount": None,
    }])

    sql = engine.connection.calls[0][0]
    assert (
        "`total_market_value` = COALESCE(VALUES(`total_market_value`), "
        "`total_market_value`)"
    ) in sql
    assert (
        "`dde_net_amount` = COALESCE(VALUES(`dde_net_amount`), "
        "`dde_net_amount`)"
    ) in sql
    assert "`close_price` = VALUES(`close_price`)" in sql
