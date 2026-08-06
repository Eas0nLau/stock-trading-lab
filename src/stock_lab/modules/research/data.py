from dataclasses import dataclass

from .context import DisabledCapability


@dataclass(slots=True)
class ResearchData:
    """Read-only facade over the canonical market-data repositories."""

    market_data: object
    dragon_tiger: object | None = None

    def __post_init__(self):
        if self.dragon_tiger is None:
            self.dragon_tiger = DisabledCapability("dragon_tiger")

    def securities(self, market=None):
        return self.market_data.securities(market=market)

    def security_codes(self, market=None):
        return [row["ts_code"] for row in self.securities(market)]

    def daily_quotes(self, stock_codes=None, start_date=None, end_date=None):
        return self.market_data.daily_quotes(stock_codes, start_date, end_date)

    def index_daily(self, start_date=None, end_date=None, limit=None):
        return self.market_data.index_daily(start_date, end_date, limit)

    def kdj_indicators(self, stock_codes=None, start_date=None, end_date=None):
        return self.market_data.kdj_indicators(stock_codes, start_date, end_date)

    def intraday_bars_5m(self, trade_date=None, stock_code=None):
        return self.market_data.intraday_bars_5m(trade_date, stock_code)

    def dragon_tiger_listings(self, **filters):
        return self.dragon_tiger.listings(**filters)

    def dragon_tiger_broker_history(self, **filters):
        return self.dragon_tiger.broker_history(**filters)
