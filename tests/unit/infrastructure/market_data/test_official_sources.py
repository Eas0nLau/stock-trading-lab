import sys
import types

import pytest

from stock_lab.infrastructure.market_data.akshare import AkShareSource
from stock_lab.infrastructure.market_data.tushare import TushareSource
from stock_lab.shared.errors import InfrastructureError


def test_akshare_import_is_lazy(monkeypatch):
    calls = []
    monkeypatch.setitem(sys.modules, "akshare", types.SimpleNamespace(
        stock_zh_index_daily=lambda symbol: calls.append(symbol) or "index-frame"
    ))

    source = AkShareSource()

    assert calls == []
    assert source.fetch_index_daily() == "index-frame"
    assert calls == ["sh000001"]


def test_tushare_client_creation_is_lazy(monkeypatch):
    calls = []
    client = types.SimpleNamespace(
        stock_basic=lambda **kwargs: ("securities", kwargs),
        daily=lambda **kwargs: ("quotes", kwargs),
    )
    monkeypatch.setitem(sys.modules, "tushare", types.SimpleNamespace(
        pro_api=lambda token: calls.append(token) or client
    ))
    source = TushareSource(("token-1",))

    assert calls == []
    assert source.fetch_daily_quotes(20260807) == (
        "quotes",
        {"ts_code": "", "trade_date": "20260807"},
    )
    assert calls == ["token-1"]


def test_tushare_rotates_tokens_once_per_request():
    calls = []

    class Client:
        def __init__(self, result=None, error=None):
            self.result = result
            self.error = error

        def daily(self, **_kwargs):
            if self.error:
                raise self.error
            return self.result

    clients = {
        "bad": Client(error=RuntimeError("频率限制")),
        "good": Client(result="quotes"),
    }
    source = TushareSource(
        ("bad", "good"),
        client_factory=lambda token: calls.append(token) or clients[token],
    )

    assert source.fetch_daily_quotes(20260807) == "quotes"
    assert calls == ["bad", "good"]


def test_tushare_daily_basic_uses_required_fields():
    calls = []
    client = types.SimpleNamespace(
        daily_basic=lambda **kwargs: calls.append(kwargs) or "daily-basic"
    )
    source = TushareSource(("token",), client_factory=lambda _token: client)

    assert source.fetch_daily_basic(20260807) == "daily-basic"
    assert calls == [{
        "trade_date": "20260807",
        "fields": "ts_code,trade_date,total_mv,circ_mv,free_share",
    }]


def test_tushare_reports_all_token_failure():
    class Client:
        def daily(self, **_kwargs):
            raise RuntimeError("source down")

    source = TushareSource(
        ("one", "two"),
        client_factory=lambda _token: Client(),
    )

    with pytest.raises(InfrastructureError, match="daily failed for all 2 tokens"):
        source.fetch_daily_quotes(20260807)
