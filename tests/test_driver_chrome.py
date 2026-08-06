from types import SimpleNamespace

from utils import driver_chrome


def test_closed_cached_tab_is_not_usable():
    page = SimpleNamespace(tab_id="closed-tab", tab_ids=["active-tab"])

    assert driver_chrome._页面可用(page) is False


def test_active_cached_tab_is_usable():
    page = SimpleNamespace(tab_id="active-tab", tab_ids=["active-tab"])

    assert driver_chrome._页面可用(page) is True
