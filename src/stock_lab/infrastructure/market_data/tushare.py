class TushareSource:
    def __init__(self, tokens):
        self.tokens = tuple(tokens)
        self._client = None

    @property
    def client(self):
        if self._client is None:
            if not self.tokens:
                raise RuntimeError("Tushare token is required for stock collection")
            import tushare

            self._client = tushare.pro_api(self.tokens[0])
        return self._client

    def fetch_securities(self):
        return self.client.stock_basic(
            exchange="",
            list_status="L",
            fields="ts_code,symbol,name,area,industry,market,list_date,list_status",
        )

    def fetch_daily_quotes(self, trade_date):
        return self.client.daily(ts_code="", trade_date=str(trade_date))
