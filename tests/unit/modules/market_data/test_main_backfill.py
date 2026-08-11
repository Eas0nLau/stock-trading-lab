import pandas as pd

from stock_lab.modules.market_data.collectors import MarketDataCollector


class FakeRepository:
    def __init__(self, existing):
        self.existing = existing
        self.upserted = []

    def trading_dates(self, limit):
        return [20260805, 20260806, 20260807]

    def daily_quote_dates(self, start_date, end_date):
        return self.existing

    def securities(self):
        return [{"symbol": "000001", "name": "Ping An", "ts_code": "000001.SZ"}]

    def upsert_daily_quotes(self, rows):
        self.upserted.extend(rows)
        return len(rows)


def test_daily_quotes_skips_existing_dates_and_fetches_only_gaps():
    requested = []
    repository = FakeRepository([20260805])
    source = lambda date: requested.append(date) or pd.DataFrame([{
        "ts_code": "000001.SZ", "trade_date": date, "open": 1,
        "high": 2, "low": 1, "close": 2, "pre_close": 1,
        "change": 1, "pct_chg": 100, "vol": 1, "amount": 1,
    }])
    collector = MarketDataCollector(
        repository, index_source=lambda _start, _end: pd.DataFrame(),
        security_source=lambda: pd.DataFrame(), quote_source=source,
    )

    collector.update_daily_quotes(20260805, 20260807)

    assert requested == [20260806, 20260807]
