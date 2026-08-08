from pathlib import Path

from stock_lab.infrastructure.tdx import TdxQuoteSubscription
import pytest

from stock_lab.modules.tdx.runtime import run_auction_monitor, run_global_monitor


class Settings:
    tdx_root = str(Path("C:/tdx"))
    tdx_cache_refresh_interval_seconds = 20.0


class FakeTq:
    def __init__(self):
        self.closed = False

    def subscribe_hq(self, stock_list, callback):
        callback('{"Code":"000001.SZ","Price":11,"PreClose":10,"Open":10}')

    def unsubscribe_hq(self, stock_list):
        pass

    def close(self):
        self.closed = True

    def get_market_snapshot(self, stock_code):
        return {"Code": stock_code, "Price": 11, "PreClose": 10, "Open": 10}


class ExplodingSubscription:
    def subscribe(self, tq, codes):
        raise RuntimeError("subscription setup failed")


def test_global_runtime_uses_injected_client_and_closes_it():
    client = FakeTq()

    rows = run_global_monitor(
        Settings(),
        codes=["000001.SZ"],
        max_loops=1,
        client_factory=lambda root: client,
        refresh=lambda tq: None,
        subscription_factory=lambda: TdxQuoteSubscription(warmup_seconds=0),
        emit=lambda event: None,
    )

    assert rows[0]["最新价"] == 11
    assert client.closed is True


@pytest.mark.parametrize("runner", [run_global_monitor, run_auction_monitor])
def test_runtime_closes_acquired_client_when_subscription_setup_raises(runner):
    client = FakeTq()
    kwargs = {
        "settings": Settings(),
        "codes": ["000001.SZ"],
        "client_factory": lambda root: client,
        "subscription_factory": ExplodingSubscription,
    }
    if runner is run_auction_monitor:
        class Repository:
            def securities(self, market=None):
                return []
        kwargs["repository"] = Repository()

    with pytest.raises(RuntimeError, match="subscription setup failed"):
        runner(**kwargs)

    assert client.closed is True
