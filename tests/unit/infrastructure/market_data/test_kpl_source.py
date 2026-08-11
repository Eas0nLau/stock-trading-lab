import datetime as dt

import pytest

from stock_lab.infrastructure.market_data.kpl import (
    KplDdeSource,
    normalize_stock_code,
)
from stock_lab.shared.errors import InfrastructureError


class Response:
    def __init__(self, payload=None, error=None):
        self.payload = payload
        self.error = error

    def raise_for_status(self):
        if self.error:
            raise self.error

    def json(self):
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


class Session:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.headers = {}
        self.calls = []

    def post(self, url, data, timeout):
        self.calls.append((url, data, timeout))
        return next(self.responses)


class Limiter:
    def __init__(self):
        self.calls = 0

    def wait(self):
        self.calls += 1


@pytest.mark.parametrize(("value", "expected"), [
    (1, "000001"),
    ("000001.SZ", "000001"),
    ("sz000001", "000001"),
    ("BJ.920001", "920001"),
])
def test_normalize_stock_code(value, expected):
    assert normalize_stock_code(value) == expected


def test_daily_dde_request_and_parsing():
    limiter = Limiter()
    session = Session([Response({
        "errcode": "0",
        "Date": ["20260807", "20260806", "broken"],
        "DDJE": ["325000000", "-50000000", "bad"],
    })])
    source = KplDdeSource(
        session=session,
        limiter=limiter,
        device_id="device-1",
        today=lambda: dt.date(2026, 8, 11),
    )

    rows = source.fetch_daily_dde(
        "000001.SZ",
        start_date=20260806,
        end_date=20260807,
    )

    assert rows == [
        {"stock_code": "000001", "trade_date": 20260807, "dde": 325000000.0},
        {"stock_code": "000001", "trade_date": 20260806, "dde": -50000000.0},
    ]
    url, params, timeout = session.calls[0]
    assert url == "https://apphis.longhuvip.com/w1/api/index.php"
    assert timeout == 20
    assert params["a"] == "GetDaDanKLine2New"
    assert params["c"] == "StockLineData"
    assert params["StockID"] == "000001"
    assert params["DeviceID"] == "device-1"
    assert params["Index"] == "0"
    assert params["st"] == "15"
    assert limiter.calls == 1


def test_daily_dde_paginates_and_deduplicates_dates():
    session = Session([
        Response({"errcode": "0", "Date": ["20260807", "20260806"], "DDJE": ["3", "2"]}),
        Response({"errcode": "0", "Date": ["20260806", "20260805"], "DDJE": ["9", "1"]}),
    ])
    source = KplDdeSource(
        session=session,
        limiter=Limiter(),
        today=lambda: dt.date(2026, 8, 11),
    )

    rows = source.fetch_daily_dde("000001", count=3)

    assert [row["trade_date"] for row in rows] == [20260807, 20260806, 20260805]
    assert rows[1]["dde"] == 2.0
    assert [call[1]["Index"] for call in session.calls] == ["0", "2"]


def test_daily_dde_retries_business_error_with_backoff():
    sleeps = []
    limiter = Limiter()
    session = Session([
        Response({"errcode": "1", "msg": "busy"}),
        Response({"errcode": "0", "Date": ["20260807"], "DDJE": ["3"]}),
    ])
    source = KplDdeSource(
        session=session,
        limiter=limiter,
        sleep=sleeps.append,
    )

    assert source.fetch_daily_dde("000001", count=1, retries=2)[0]["dde"] == 3
    assert sleeps == [0.5]
    assert limiter.calls == 2


def test_daily_dde_reports_exhausted_retry():
    session = Session([
        Response({"errcode": "1"}),
        Response({"errcode": "1"}),
    ])
    source = KplDdeSource(session=session, limiter=Limiter(), sleep=lambda _seconds: None)

    with pytest.raises(InfrastructureError, match="request failed"):
        source.fetch_daily_dde("000001", count=1, retries=2)


def test_daily_dde_stops_on_page_without_valid_dates():
    session = Session([
        Response({"errcode": "0", "Date": ["broken"], "DDJE": ["3"]}),
        Response({"errcode": "0", "Date": ["20260807"], "DDJE": ["4"]}),
    ])
    source = KplDdeSource(session=session, limiter=Limiter())

    assert source.fetch_daily_dde("000001", count=2) == []
    assert len(session.calls) == 1


def test_daily_dde_rejects_excessive_pagination():
    repeated = Response({
        "errcode": "0",
        "Date": ["20260807"],
        "DDJE": ["3"],
    })
    session = Session([repeated, repeated, repeated])
    source = KplDdeSource(
        session=session,
        limiter=Limiter(),
        today=lambda: dt.date(2026, 8, 11),
    )

    with pytest.raises(InfrastructureError, match="pagination limit"):
        source.fetch_daily_dde(
            "000001",
            start_date=20260801,
            end_date=20260807,
        )
