from threading import RLock

from loguru import logger


_browser = None
_browser_configuration = None
_lock = RLock()
_pages = {}


def _is_browser_available(browser):
    if browser is None:
        return False
    try:
        browser.tab_ids
        return True
    except Exception:
        return False


def _is_page_available(page):
    if page is None:
        return False
    try:
        tab_ids = getattr(page, "tab_ids", None)
        return bool(page.tab_id) and (tab_ids is None or page.tab_id in tab_ids)
    except Exception:
        return False


def _new_browser(*, settings=None, close_old_tabs=None):
    from DrissionPage import ChromiumOptions, WebPage

    if settings is None:
        from stock_lab.config import get_settings

        settings = get_settings()
    if not getattr(settings, "browser_auto_start", True):
        raise RuntimeError("BROWSER_AUTO_START is disabled; enable it before using browser-backed collection")
    options = ChromiumOptions()
    if getattr(settings, "browser_headless", False):
        options.headless(True)
    options.set_timeouts(1, 2, 5)
    options.set_user_data_path(str(settings.project_root / "data" / "chrome_profile"))
    browser = WebPage(chromium_options=options)
    should_close = settings.browser_close_old_tabs if close_old_tabs is None else close_old_tabs
    if should_close:
        try:
            tab_ids = list(browser.tab_ids)
            if len(tab_ids) > 1:
                keep_tab_id = browser.tab_id or tab_ids[0]
                browser.close_tabs(keep_tab_id, others=True)
                logger.info("Closed {} old browser tabs", len(tab_ids) - 1)
        except Exception as error:
            logger.warning("Could not close old browser tabs: {}", error)
    browser.set.window.max()
    return browser


def create_browser(close_old_tabs=None, *, settings=None):
    global _browser, _browser_configuration
    if settings is None:
        from stock_lab.config import get_settings

        settings = get_settings()
    should_close = settings.browser_close_old_tabs if close_old_tabs is None else close_old_tabs
    configuration = (
        str(settings.project_root),
        bool(should_close),
        bool(getattr(settings, "browser_auto_start", True)),
        bool(getattr(settings, "browser_headless", False)),
    )
    with _lock:
        if not _is_browser_available(_browser) or _browser_configuration != configuration:
            _browser = _new_browser(settings=settings, close_old_tabs=close_old_tabs)
            _browser_configuration = configuration
            _pages.clear()
        return _browser


def create_page(
    name,
    url=None,
    background=False,
    use_main_tab=False,
    close_old_tabs=None,
    *,
    settings=None,
    stop_event=None,
):
    if stop_event is not None and stop_event.is_set():
        return None
    with _lock:
        browser = create_browser(close_old_tabs, settings=settings)
        if stop_event is not None and stop_event.is_set():
            return None
        page = _pages.get(name)
        if not _is_page_available(page):
            page = browser if use_main_tab else browser.new_tab(background=background)
            _pages[name] = page
    if url and not (stop_event is not None and stop_event.is_set()):
        page.get(url, timeout=0)
    return page
