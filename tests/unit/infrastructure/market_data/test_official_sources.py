import sys
import types

from stock_lab.infrastructure.market_data.akshare import AkShareSource
from stock_lab.infrastructure.market_data.tushare import TushareSource


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
