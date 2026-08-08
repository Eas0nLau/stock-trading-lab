import requests
import pytest

from stock_lab.infrastructure.market_data.dragon_tiger import DragonTigerHttpSource


class Response:
    text = "listing html"

    def raise_for_status(self):
        return None


def test_source_retries_transient_timeout_before_returning_response():
    calls = []

    def get(url, **kwargs):
        calls.append((url, kwargs))
        if len(calls) < 3:
            raise requests.ReadTimeout("slow upstream")
        return Response()

    source = DragonTigerHttpSource(get=get, timeout=5, max_attempts=3, retry_delay=0)

    assert source.fetch_listing_page(20260807) == "listing html"
    assert len(calls) == 3


def test_source_reports_url_and_attempt_count_when_timeout_persists():
    def get(_url, **_kwargs):
        raise requests.ReadTimeout("slow upstream")

    source = DragonTigerHttpSource(get=get, timeout=5, max_attempts=2, retry_delay=0)

    with pytest.raises(RuntimeError, match=r"2 attempts.*lhbggxq/report/2026-08-07"):
        source.fetch_listing_page(20260807)
