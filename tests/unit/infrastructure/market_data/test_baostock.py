import builtins
import importlib

import pytest

from stock_lab.infrastructure.market_data import baostock as baostock_module
from stock_lab.infrastructure.market_data.baostock import BaoStockSource
from stock_lab.shared.errors import InfrastructureError


class Result:
    def __init__(self, rows=(), error_code="0", error_msg="", fields=None):
        self.fields = fields or [
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
    def __init__(self, result, login_code="0", login_error=None, query_error=None, logout_error=None):
        self.result = result
        self.login_result = Result(error_code=login_code, error_msg="login failed")
        self.login_error = login_error
        self.query_error = query_error
        self.logout_error = logout_error
        self.calls = []
        self.login_count = 0
        self.logout_count = 0

    def login(self):
        self.login_count += 1
        if self.login_error:
            raise self.login_error
        return self.login_result

    def logout(self):
        self.logout_count += 1
        if self.logout_error:
            raise self.logout_error

    def query_history_k_data_plus(self, code, fields, **options):
        if self.query_error:
            raise self.query_error
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


def test_source_is_lazy_until_first_fetch(monkeypatch):
    client = Client(Result([]))
    imports = []

    def load(name):
        imports.append(name)
        return client

    monkeypatch.setattr(importlib, "import_module", load)

    source = BaoStockSource()

    assert imports == []
    assert client.login_count == 0
    source.fetch_5m_bars("20260806", "20260806", "000001.SZ")
    assert imports == ["baostock"]
    assert client.login_count == 1


def test_importing_adapter_does_not_import_baostock(monkeypatch):
    imported = []
    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name == "baostock":
            imported.append(name)
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)

    importlib.reload(baostock_module)

    assert imported == []


def test_login_exception_is_mapped_without_logout():
    client = Client(Result([]), login_error=RuntimeError("login exploded"))

    with pytest.raises(InfrastructureError, match="login exploded"):
        BaoStockSource(client=client).fetch_5m_bars("20260806", "20260806", "000001.SZ")

    assert client.logout_count == 0


def test_query_exception_is_mapped_and_logs_out():
    client = Client(Result([]), query_error=RuntimeError("query exploded"))

    with pytest.raises(InfrastructureError, match="query exploded"):
        BaoStockSource(client=client).fetch_5m_bars("20260806", "20260806", "000001.SZ")

    assert client.logout_count == 1


def test_logout_exception_after_success_is_mapped():
    client = Client(Result([]), logout_error=RuntimeError("logout exploded"))

    with pytest.raises(InfrastructureError, match="logout exploded"):
        BaoStockSource(client=client).fetch_5m_bars("20260806", "20260806", "000001.SZ")

    assert client.logout_count == 1


def test_logout_exception_does_not_mask_query_exception():
    client = Client(
        Result([]),
        query_error=RuntimeError("query exploded"),
        logout_error=RuntimeError("logout exploded"),
    )

    with pytest.raises(InfrastructureError, match="query exploded"):
        BaoStockSource(client=client).fetch_5m_bars("20260806", "20260806", "000001.SZ")

    assert client.logout_count == 1


def test_index_source_uses_buffer_and_computes_previous_close_fields():
    fields = [
        "date", "code", "open", "close", "high", "low", "volume",
        "amount", "adjustflag", "turn", "pctChg",
    ]
    client = Client(Result([
        ["2026-08-06", "sh.000001", "10", "11", "12", "9", "1000", "2000", "3", "1.2", "10"],
        ["2026-08-07", "sh.000001", "11", "12", "13", "10", "1200", "2500", "3", "1.3", "9.09"],
    ], fields=fields))

    rows = BaoStockSource(client=client).fetch_index_daily(20260807, 20260807)

    assert client.calls == [("sh.000001", ",".join(fields), {
        "start_date": "2026-07-18",
        "end_date": "2026-08-07",
        "frequency": "d",
        "adjustflag": "3",
    })]
    assert rows == [{
        "date": "2026-08-07",
        "open": 11.0,
        "close": 12.0,
        "high": 13.0,
        "low": 10.0,
        "volume": 12.0,
        "amount": 2500.0,
        "amplitude": pytest.approx((13.0 - 10.0) / 11.0 * 100),
        "pct_chg": 9.09,
        "change": 1.0,
        "turnover": 1.3,
    }]
    assert client.login_count == 1
    assert client.logout_count == 1


def test_index_source_returns_empty_rows_without_crashing():
    fields = [
        "date", "code", "open", "close", "high", "low", "volume",
        "amount", "adjustflag", "turn", "pctChg",
    ]
    client = Client(Result([], fields=fields))

    assert BaoStockSource(client=client).fetch_index_daily(20260807, 20260807) == []
    assert client.logout_count == 1


def test_index_source_rejects_malformed_rows():
    fields = [
        "date", "code", "open", "close", "high", "low", "volume",
        "amount", "adjustflag", "turn", "pctChg",
    ]
    client = Client(Result([["2026-08-07", "sh.000001"]], fields=fields))

    with pytest.raises(InfrastructureError, match="malformed"):
        BaoStockSource(client=client).fetch_index_daily(20260807, 20260807)

    assert client.logout_count == 1
