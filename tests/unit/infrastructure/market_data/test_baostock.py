import pytest

from stock_lab.infrastructure.market_data.baostock import BaoStockSource
from stock_lab.shared.errors import InfrastructureError


class Result:
    def __init__(self, rows=(), error_code="0", error_msg=""):
        self.fields = [
            "open", "close", "date", "time", "code", "high", "low",
            "volume", "amount", "adjustflag",
        ]
        self.error_code = error_code
        self.error_msg = error_msg
        self._rows = iter(rows)
        self._current = None

    def next(self):
        try:
            self._current = next(self._rows)
        except StopIteration:
            return False
        return True

    def get_row_data(self):
        return self._current


class Client:
    def __init__(self, result, login_code="0"):
        self.result = result
        self.login_result = Result(error_code=login_code, error_msg="login failed")
        self.calls = []
        self.logout_count = 0

    def login(self):
        return self.login_result

    def logout(self):
        self.logout_count += 1

    def query_history_k_data_plus(self, code, fields, **options):
        self.calls.append((code, fields, options))
        return self.result


def test_source_parses_complete_result_and_logs_out():
    client = Client(Result([["10", "11", "2026-08-06", "20260806093500000", "sz.000001", "12", "9", "100", "1100", "3"]]))

    rows = BaoStockSource(client=client).fetch_5m_bars("20260806", "20260806", "000001.SZ")

    assert rows == [{
        "open": "10", "close": "11", "date": "2026-08-06",
        "time": "20260806093500000", "code": "sz.000001", "high": "12",
        "low": "9", "volume": "100", "amount": "1100", "adjustflag": "3",
    }]
    assert client.calls == [("sz.000001", "open,close,date,time,code,high,low,volume,amount,adjustflag", {
        "start_date": "2026-08-06", "end_date": "2026-08-06", "frequency": "5", "adjustflag": "3",
    })]
    assert client.logout_count == 1


@pytest.mark.parametrize("client", [
    Client(Result([]), login_code="1"),
    Client(Result([], error_code="2", error_msg="query failed")),
])
def test_source_maps_baostock_failures_and_logs_out_after_query(client):
    source = BaoStockSource(client=client)

    with pytest.raises(InfrastructureError):
        source.fetch_5m_bars("20260806", "20260806", "000001.SZ")

    assert client.logout_count == (0 if client.login_result.error_code != "0" else 1)
