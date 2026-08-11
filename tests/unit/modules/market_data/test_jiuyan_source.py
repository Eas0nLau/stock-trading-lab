from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from stock_lab.modules.market_data.jiuyan_source import (
    HumanVerificationRequired,
    IncompleteJiuyanResponse,
    JiuyanBrowserSource,
)


class _Listen:
    def __init__(self, packets=(), on_steps=None) -> None:
        self.packets = packets
        self.on_steps = on_steps
        self.started = []
        self.timeouts = []
        self.stop_count = 0

    def start(self, targets) -> None:
        self.started.append(targets)

    def steps(self, timeout):
        self.timeouts.append(timeout)
        if self.on_steps is not None:
            self.on_steps()
        return iter(self.packets)

    def stop(self) -> None:
        self.stop_count += 1


class _Page:
    def __init__(self, *, packets=(), slider=False, get_error=None) -> None:
        self.listen = _Listen(packets)
        self.slider = slider
        self.get_error = get_error
        self.get_calls = []
        self.html = ""

    def get(self, url, timeout):
        self.get_calls.append((url, timeout))
        if self.get_error:
            raise self.get_error

    def ele(self, selector, timeout=0):
        if "滑块" in selector and self.slider:
            return object()
        return None


def _packet(body, target="/jystock-app/api/v1/action/field"):
    return SimpleNamespace(target=target, response=SimpleNamespace(body=body))


class _Clock:
    def __init__(self, value=100.0, step=0.25) -> None:
        self.value = value
        self.step = step

    def __call__(self):
        value = self.value
        self.value += self.step
        return value


def _source(page: _Page, *, clock=None):
    names = []
    closed = []

    def factory(name, background=True):
        names.append((name, background))
        return page

    source = JiuyanBrowserSource(
        factory,
        lambda name, owned_page: closed.append((name, owned_page)),
        clock=clock or _Clock(),
        request_slot=lambda **_kwargs: None,
    )
    return source, names, closed


def test_source_returns_decoded_packet_with_bounded_timeouts_and_cleanup() -> None:
    response = {"date": "2026-08-05", "data": []}
    page = _Page(packets=[_packet(json.dumps(response))])
    source, names, closed = _source(page)

    assert source(20260805, deadline=110.0, attempt=1) == response
    assert names[0][0].startswith("jiuyan-action-20260805-1-")
    assert names[0][1] is True
    assert page.get_calls[0][1] <= 10.0
    assert page.listen.timeouts[0] <= 10.0
    assert page.listen.stop_count == 1
    assert closed == [(names[0][0], page)]


@pytest.mark.parametrize(
    ("page", "error_type"),
    [
        (_Page(), IncompleteJiuyanResponse),
        (_Page(get_error=RuntimeError("navigation failed")), RuntimeError),
        (_Page(packets=[_packet("not-json")]), IncompleteJiuyanResponse),
        (_Page(slider=True), HumanVerificationRequired),
    ],
)
def test_source_cleans_up_all_failure_paths(page, error_type) -> None:
    source, names, closed = _source(page)

    with pytest.raises(error_type):
        source(20260805, deadline=110.0, attempt=1)

    assert page.listen.stop_count == 1
    assert closed == [(names[0][0], page)]


def test_source_uses_a_fresh_unique_page_for_each_attempt() -> None:
    pages = [
        _Page(packets=[_packet({"date": "2026-08-05", "data": []})]),
        _Page(packets=[_packet({"date": "2026-08-05", "data": []})]),
    ]
    names = []

    def factory(name, background=True):
        names.append(name)
        return pages[len(names) - 1]

    source = JiuyanBrowserSource(
        factory,
        lambda *_args: None,
        clock=_Clock(),
        request_slot=lambda **_kwargs: None,
    )

    source(20260805, deadline=110.0, attempt=1)
    source(20260805, deadline=110.0, attempt=2)

    assert names[0].startswith("jiuyan-action-20260805-1-")
    assert names[1].startswith("jiuyan-action-20260805-2-")
    assert names[0] != names[1]


def test_source_does_not_create_page_after_deadline() -> None:
    created = []
    source = JiuyanBrowserSource(
        lambda *args, **kwargs: created.append((args, kwargs)),
        lambda *_args: None,
        clock=lambda: 110.0,
        request_slot=lambda **_kwargs: None,
    )

    with pytest.raises(IncompleteJiuyanResponse, match="deadline"):
        source(20260805, deadline=110.0, attempt=1)

    assert created == []


def test_source_passes_absolute_deadline_to_request_slot() -> None:
    observed = []
    page = _Page(packets=[_packet({"date": "2026-08-05", "data": []})])
    source = JiuyanBrowserSource(
        lambda *args, **kwargs: page,
        lambda *_args: None,
        clock=_Clock(),
        request_slot=lambda **kwargs: observed.append(kwargs),
    )

    source(20260805, deadline=110.0, attempt=1)

    assert observed == [{"deadline": 110.0}]


def test_slider_appearing_while_listener_waits_is_not_reported_as_timeout() -> None:
    page = _Page()
    page.listen = _Listen(on_steps=lambda: setattr(page, "slider", True))
    source, _names, _closed = _source(page)

    with pytest.raises(HumanVerificationRequired):
        source(20260805, deadline=110.0, attempt=1)
