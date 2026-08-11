from stock_lab.shared.errors import InfrastructureError


class TushareSource:
    def __init__(self, tokens, client_factory=None):
        self.tokens = tuple(tokens)
        self._client_factory = client_factory
        self._clients = {}

    def _client(self, token):
        if token not in self._clients:
            if self._client_factory is None:
                import tushare

                factory = tushare.pro_api
            else:
                factory = self._client_factory
            self._clients[token] = factory(token)
        return self._clients[token]

    def _call(self, method_name, **kwargs):
        if not self.tokens:
            raise InfrastructureError(
                "Tushare token is required for stock collection"
            )
        errors = []
        for token in self.tokens:
            try:
                return getattr(self._client(token), method_name)(**kwargs)
            except Exception as error:
                errors.append(error)
        raise InfrastructureError(
            f"Tushare {method_name} failed for all {len(self.tokens)} tokens: "
            f"{errors[-1]}"
        ) from errors[-1]

    def fetch_securities(self):
        return self._call(
            "stock_basic",
            exchange="",
            list_status="L",
            fields=(
                "ts_code,symbol,name,area,industry,market,list_date,list_status"
            ),
        )

    def fetch_daily_quotes(self, trade_date):
        return self._call("daily", ts_code="", trade_date=str(trade_date))

    def fetch_daily_basic(self, trade_date):
        return self._call(
            "daily_basic",
            trade_date=str(trade_date),
            fields="ts_code,trade_date,total_mv,circ_mv,free_share",
        )
