from __future__ import annotations

import threading
import time

import requests

from stock_lab.shared.errors import DataValidationError, InfrastructureError
from stock_lab.shared.rate_limit import RequestRateLimiter


THS_ROOT = "https://q.10jqka.com.cn"
THS_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/89.0.4389.90 Safari/537.36"
)


def create_ths_cookie():
    from akshare.datasets import get_ths_js
    from py_mini_racer import MiniRacer

    context = MiniRacer()
    with open(get_ths_js("ths.js"), encoding="utf-8") as source_file:
        context.eval(source_file.read())
    return f"v={context.call('v')}"


class ThsHttpSource:
    def __init__(
        self,
        *,
        session=None,
        limiter=None,
        cookie_factory=create_ths_cookie,
        sleep=time.sleep,
        timeout=20,
        attempts=3,
    ):
        self.session = session or requests.Session()
        self.limiter = limiter or RequestRateLimiter(0.5)
        self.cookie_factory = cookie_factory
        self.sleep = sleep
        self.timeout = int(timeout)
        self.attempts = int(attempts)
        self._cookie = None
        self._cookie_lock = threading.Lock()

    def _refresh_cookie(self):
        with self._cookie_lock:
            self._cookie = str(self.cookie_factory())
            return self._cookie

    def _headers(self, *, referer=None, host=None):
        if self._cookie is None:
            self._refresh_cookie()
        headers = {
            "User-Agent": THS_USER_AGENT,
            "Cookie": self._cookie,
            "Referer": referer or f"{THS_ROOT}/",
        }
        if host:
            headers["Host"] = host
        return headers

    def get_text(self, url, *, referer=None, host=None):
        last_error = None
        for attempt in range(1, self.attempts + 1):
            self.limiter.wait()
            headers = self._headers(referer=referer, host=host)
            try:
                response = self.session.get(
                    url,
                    headers=headers,
                    timeout=self.timeout,
                )
                if response.status_code in {401, 403} and attempt < self.attempts:
                    self._refresh_cookie()
                    self.sleep(attempt)
                    continue
                response.raise_for_status()
                return response.text
            except requests.RequestException as error:
                last_error = error
                if attempt < self.attempts:
                    self.sleep(attempt)
        raise InfrastructureError(f"THS request failed for {url}: {last_error}") from last_error

    @staticmethod
    def board_directory_url(board_type):
        paths = {"concept": "gn", "industry": "thshy"}
        if board_type not in paths:
            raise DataValidationError(f"Unsupported THS board type: {board_type!r}")
        return f"{THS_ROOT}/{paths[board_type]}/"

    @staticmethod
    def concept_detail_url(page_code):
        return f"{THS_ROOT}/gn/detail/code/{page_code}/"

    @staticmethod
    def blockrank_url(board_code, rank_code):
        return f"https://d.10jqka.com.cn/v2/blockrank/{board_code}/8/{rank_code}.js"

    @staticmethod
    def constituent_page_url(board, page):
        if int(page) == 1:
            return (
                f"{THS_ROOT}/{board.detail_path}/detail/code/{board.page_code}/"
            )
        return (
            f"{THS_ROOT}/{board.detail_path}/detail/field/199112/order/desc/"
            f"page/{int(page)}/ajax/1/code/{board.page_code}/"
        )

    def board_directory_html(self, board_type):
        url = self.board_directory_url(board_type)
        return self.get_text(url, referer=url)

    def concept_detail_html(self, page_code):
        url = self.concept_detail_url(page_code)
        return self.get_text(url, referer=url)

    def blockrank_text(self, board_code, rank_code):
        url = self.blockrank_url(board_code, rank_code)
        return self.get_text(
            url,
            referer=f"{THS_ROOT}/",
            host="d.10jqka.com.cn",
        )

    def constituent_page_html(self, board, page):
        url = self.constituent_page_url(board, page)
        return self.get_text(url, referer=url)
