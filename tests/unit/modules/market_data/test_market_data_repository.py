from stock_lab.modules.market_data.repository import MarketDataRepository


class FakeQuery:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def __call__(self, sql, params=None, fetch=False):
        self.calls.append((sql, params, fetch))
        return self.rows


def test_trading_dates_reads_index_daily_canonical_column():
    query = FakeQuery([{"trade_date": 20260806}])

    result = MarketDataRepository(query).trading_dates(10)

    assert result == [20260806]
    assert "FROM `index_daily`" in query.calls[0][0]
    assert "stock_daily" not in query.calls[0][0]


def test_daily_quotes_query_uses_canonical_columns_and_preserves_code():
    query = FakeQuery([{"ts_code": "000001.SZ", "trade_date": 20260806, "close_price": 10}])

    result = MarketDataRepository(query).daily_quotes_for_date(20260806, [1])

    assert result[0]["ts_code"] == "000001.SZ"
    sql = query.calls[0][0]
    assert "FROM `daily_quotes`" in sql
    assert "`close_price`" in sql
    assert "stock_daily" not in sql


def test_daily_quotes_bare_symbol_matches_exchange_qualified_storage():
    query = FakeQuery([])

    MarketDataRepository(query).daily_quotes_for_date(20260806, ["000001"])

    assert "SUBSTRING_INDEX(`ts_code`, '.', 1)" in query.calls[0][0]


def test_securities_query_supports_market_filter():
    query = FakeQuery([{"ts_code": "600000.SH", "symbol": "600000"}])

    result = MarketDataRepository(query).securities(market="主板")

    assert result[0]["symbol"] == "600000"
    assert query.calls[0][1] == ("主板",)
    assert "FROM `securities`" in query.calls[0][0]
