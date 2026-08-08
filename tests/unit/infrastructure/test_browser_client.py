import sys
import threading
from pathlib import Path
from types import SimpleNamespace

from stock_lab.infrastructure.browser import client
from stock_lab.modules.strategy_pick.collector import create_strategy_pick_source


def test_new_browser_uses_composed_project_root_and_close_old_tabs(monkeypatch, tmp_path):
    observed = {}

    class Options:
        def set_timeouts(self, *values):
            observed["timeouts"] = values

        def set_user_data_path(self, value):
            observed["profile"] = value

    class Window:
        def max(self):
            observed["maximized"] = True

    class Browser:
        tab_ids = ["keep", "old"]
        tab_id = "keep"
        set = SimpleNamespace(window=Window())

        def close_tabs(self, tab_id, others=False):
            observed["closed"] = (tab_id, others)

    monkeypatch.setitem(
        sys.modules,
        "DrissionPage",
        SimpleNamespace(ChromiumOptions=Options, WebPage=lambda chromium_options: Browser()),
    )
    monkeypatch.setattr(
        "stock_lab.config.get_settings",
        lambda: (_ for _ in ()).throw(AssertionError("global settings used")),
    )
    settings = SimpleNamespace(
        project_root=Path(tmp_path),
        browser_close_old_tabs=True,
    )

    browser = client._new_browser(settings=settings)

    assert isinstance(browser, Browser)
    assert observed["profile"] == str(tmp_path / "data" / "chrome_profile")
    assert observed["closed"] == ("keep", True)


def test_create_page_forwards_composed_settings_to_browser(monkeypatch):
    settings = SimpleNamespace(
        project_root=Path("custom-root"),
        browser_close_old_tabs=False,
    )
    browser = SimpleNamespace(tab_id="main", tab_ids=["main"])
    observed = []
    monkeypatch.setattr(client, "_browser", None)
    monkeypatch.setattr(client, "_pages", {})
    monkeypatch.setattr(
        client,
        "_new_browser",
        lambda *, settings=None, close_old_tabs=None: observed.append(settings) or browser,
    )

    page = client.create_page("sample", use_main_tab=True, settings=settings)

    assert page is browser
    assert observed == [settings]


def test_strategy_pick_factory_binds_composed_settings_to_page_factory():
    settings = object()

    source = create_strategy_pick_source(object(), settings=settings)

    assert source.settings is settings
    assert source.page_factory.keywords["settings"] is settings


def test_create_page_returns_owned_page_when_stop_arrives_during_navigation(monkeypatch):
    stop_event = threading.Event()
    page = SimpleNamespace(
        tab_id="main",
        tab_ids=["main"],
        get=lambda *_args, **_kwargs: stop_event.set(),
    )
    settings = SimpleNamespace(
        project_root=Path("custom-root"),
        browser_close_old_tabs=False,
    )
    monkeypatch.setattr(client, "create_browser", lambda *args, **kwargs: page)
    monkeypatch.setattr(client, "_pages", {})

    created = client.create_page(
        "sample",
        url="https://example.test",
        use_main_tab=True,
        settings=settings,
        stop_event=stop_event,
    )

    assert created is page
