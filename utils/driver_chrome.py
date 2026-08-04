from threading import RLock

from DrissionPage import WebPage, ChromiumOptions
from loguru import logger

import config


_driver_web = None
_driver_lock = RLock()
_pages = {}


def _创建浏览器():
    co = ChromiumOptions()
    co.set_timeouts(1, 2, 5)
    co.set_user_data_path(f'{config.project_path}/data/chrome_profile')
    driver_web = WebPage(chromium_options=co)
    _启动时关闭旧页面(driver_web)
    driver_web.set.window.max()
    return driver_web


def _启动时关闭旧页面(driver_web):
    if not config.启动时关闭旧浏览器页面:
        return

    try:
        tab_ids = list(driver_web.tab_ids)
        if len(tab_ids) <= 1:
            return

        keep_tab_id = driver_web.tab_id or tab_ids[0]
        driver_web.close_tabs(keep_tab_id, others=True)
        logger.info(f"启动时已关闭旧浏览器页面 {len(tab_ids) - 1} 个，保留页面 {keep_tab_id}")
    except Exception as e:
        logger.warning(f"启动时关闭旧浏览器页面失败: {e}")


def _浏览器可用(driver_web):
    if driver_web is None:
        return False
    try:
        _ = driver_web.tab_ids
        return True
    except Exception:
        return False


def _页面可用(page):
    if page is None:
        return False
    try:
        _ = page.tab_id
        return True
    except Exception:
        return False


def 初始化浏览器():
    global _driver_web
    with _driver_lock:
        if not _浏览器可用(_driver_web):
            _driver_web = _创建浏览器()
            _pages.clear()
        return _driver_web


def 初始化页面(页面名称, url=None, background=False, 使用主标签页=False):
    with _driver_lock:
        driver_web = 初始化浏览器()
        page = _pages.get(页面名称)
        if not _页面可用(page):
            page = driver_web if 使用主标签页 else driver_web.new_tab(background=background)
            _pages[页面名称] = page

    if url:
        page.get(url, timeout=0)
    return page


def initDriver():
    return 初始化浏览器()
