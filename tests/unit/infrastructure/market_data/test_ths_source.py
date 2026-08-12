from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import requests

from stock_lab.infrastructure.market_data.ths import ThsHttpSource, create_ths_cookie
from stock_lab.modules.ths.contracts import ThsBoardSeed
from stock_lab.shared.errors import InfrastructureError


class _MiniRacer:
    def __init__(self, observed) -> None:
        self.observed = observed

    def eval(self, _source) -> None:
        self.observed.append("eval")

    def call(self, name):
        self.observed.append(("call", name))
        return "token"


class _Response:
    def __init__(self, status_code=200, text="ok") -> None:
        self.status_code = status_code
        self.text = text

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"status={self.status_code}", response=self)


class _Session:
    def __init__(self, responses) -> None:
        self.responses = list(responses)
        self.calls = []

    def get(self, url, *, headers, timeout):
        self.calls.append({"url": url, "headers": dict(headers), "timeout": timeout})
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class _Limiter:
    def __init__(self) -> None:
        self.calls = 0

    def wait(self):
        self.calls += 1


def test_cookie_factory_loads_js_runtime_only_when_called(monkeypatch, tmp_path: Path) -> None:
    observed = []
    js_path = tmp_path / "ths.js"
    js_path.write_text("function v(){ return 'token'; }", encoding="utf-8")
    monkeypatch.setitem(
        sys.modules,
        "akshare.datasets",
        SimpleNamespace(get_ths_js=lambda _name: str(js_path)),
    )
    monkeypatch.setitem(
        sys.modules,
        "py_mini_racer",
        SimpleNamespace(MiniRacer=lambda: _MiniRacer(observed)),
    )

    assert create_ths_cookie() == "v=token"
    assert observed == ["eval", ("call", "v")]


def test_get_text_refreshes_cookie_after_403_and_uses_global_limiter() -> None:
    session = _Session([_Response(403), _Response(200, "body")])
    limiter = _Limiter()
    sleeps = []
    cookies = iter(["v=first", "v=second"])
    source = ThsHttpSource(
        session=session,
        limiter=limiter,
        cookie_factory=lambda: next(cookies),
        sleep=sleeps.append,
    )

    assert source.get_text("https://example.test") == "body"
    assert limiter.calls == 2
    assert sleeps == [1]
    assert session.calls[0]["headers"]["Cookie"] == "v=first"
    assert session.calls[1]["headers"]["Cookie"] == "v=second"
    assert session.calls[0]["timeout"] == 20


def test_get_text_retries_exactly_three_times_without_final_sleep() -> None:
    error = requests.Timeout("slow")
    session = _Session([error, error, error])
    limiter = _Limiter()
    sleeps = []
    source = ThsHttpSource(
        session=session,
        limiter=limiter,
        cookie_factory=lambda: "v=token",
        sleep=sleeps.append,
    )

    with pytest.raises(InfrastructureError, match="example.test"):
        source.get_text("https://example.test/path")

    assert limiter.calls == 3
    assert sleeps == [1, 2]
    assert len(session.calls) == 3


def test_source_builds_exact_urls_and_blockrank_host() -> None:
    session = _Session([_Response(200)])
    source = ThsHttpSource(
        session=session,
        limiter=_Limiter(),
        cookie_factory=lambda: "v=token",
        sleep=lambda _seconds: None,
    )
    board = ThsBoardSeed("885001", "concept", "Robotics", "301558", "gn")

    assert source.board_directory_url("concept") == "https://q.10jqka.com.cn/gn/"
    assert source.board_directory_url("industry") == "https://q.10jqka.com.cn/thshy/"
    assert source.concept_detail_url("301558") == (
        "https://q.10jqka.com.cn/gn/detail/code/301558/"
    )
    assert source.blockrank_url("885001", "d15") == (
        "https://d.10jqka.com.cn/v2/blockrank/885001/8/d15.js"
    )
    assert source.constituent_page_url(board, 1).endswith(
        "/gn/detail/code/301558/"
    )
    assert source.constituent_page_url(board, 2).endswith(
        "/gn/detail/field/199112/order/desc/page/2/ajax/1/code/301558/"
    )

    source.blockrank_text("885001", "d15")
    assert session.calls[0]["headers"]["Host"] == "d.10jqka.com.cn"
