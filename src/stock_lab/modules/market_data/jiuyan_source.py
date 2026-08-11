from __future__ import annotations

import datetime as dt
import json
import os
import random
import threading
import time
import uuid

from .jiuyan_parsing import IncompleteJiuyanResponse


class HumanVerificationRequired(IncompleteJiuyanResponse):
    pass


PAGE_TEMPLATE = os.getenv(
    "JIUYAN_ACTION_URL_TEMPLATE",
    "https://www.jiuyangongshe.com/action/{date_text}",
)
LISTEN_TARGET = "/jystock-app/api/v1/action/field"
MIN_REQUEST_INTERVAL_SECONDS = max(
    int(os.getenv("JIUYAN_MIN_REQUEST_INTERVAL_SECONDS", "60")), 1
)
MAX_REQUEST_INTERVAL_SECONDS = max(
    int(os.getenv("JIUYAN_MAX_REQUEST_INTERVAL_SECONDS", "105")),
    MIN_REQUEST_INTERVAL_SECONDS,
)
_request_lock = threading.Lock()
_last_request_time = 0.0


def wait_for_request_slot():
    global _last_request_time
    with _request_lock:
        now = time.monotonic()
        interval = random.uniform(
            MIN_REQUEST_INTERVAL_SECONDS, MAX_REQUEST_INTERVAL_SECONDS
        )
        wait_seconds = max(0.0, interval - (now - _last_request_time))
        if wait_seconds:
            time.sleep(wait_seconds)
        _last_request_time = time.monotonic()


def format_page_date(trade_date):
    return dt.datetime.strptime(str(int(trade_date)), "%Y%m%d").strftime("%Y-%m-%d")


def decode_response(body):
    if isinstance(body, dict):
        return body
    text = str(body or "").strip()
    if not text:
        return None
    try:
        decoded = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("("), text.rfind(")")
        if start < 0 or end <= start:
            return None
        try:
            decoded = json.loads(text[start + 1 : end])
        except json.JSONDecodeError:
            return None
    return decoded if isinstance(decoded, dict) else None


def page_requires_human_verification(page, timeout=0.1) -> bool:
    prompts = ("拖动下方滑块完成拼图", "拖动左边滑块完成上方拼图")
    for prompt in prompts:
        try:
            if page.ele(f"text={prompt}", timeout=timeout):
                return True
        except Exception:
            continue
    try:
        return any(prompt in str(getattr(page, "html", "") or "") for prompt in prompts)
    except Exception:
        return False


class JiuyanBrowserSource:
    def __init__(
        self,
        page_factory,
        page_closer,
        *,
        clock=time.monotonic,
        request_slot=wait_for_request_slot,
    ):
        self.page_factory = page_factory
        self.page_closer = page_closer
        self.clock = clock
        self.request_slot = request_slot

    def _remaining(self, trade_date, deadline):
        remaining = float(deadline) - float(self.clock())
        if remaining <= 0:
            raise IncompleteJiuyanResponse(
                f"Jiuyan collection deadline exceeded for {trade_date}"
            )
        return remaining

    def _raise_if_verification_required(self, page, trade_date, deadline):
        remaining = self._remaining(trade_date, deadline)
        if page_requires_human_verification(page, timeout=min(0.1, remaining)):
            raise HumanVerificationRequired(
                "Jiuyan requires manual slider verification"
            )

    def __call__(self, trade_date, *, deadline, attempt):
        trade_date = int(trade_date)
        self._remaining(trade_date, deadline)
        self.request_slot()
        self._remaining(trade_date, deadline)
        name = (
            f"jiuyan-action-{trade_date}-{int(attempt)}-"
            f"{uuid.uuid4().hex[:8]}"
        )
        page = None
        try:
            page = self.page_factory(name, background=True)
            page.listen.start([LISTEN_TARGET])
            remaining = self._remaining(trade_date, deadline)
            url = PAGE_TEMPLATE.format(
                date=trade_date,
                date_text=format_page_date(trade_date),
            )
            page.get(url, timeout=remaining)
            self._raise_if_verification_required(page, trade_date, deadline)
            remaining = self._remaining(trade_date, deadline)
            tab = page.ele("text=全部异动解析", timeout=min(1.0, remaining))
            if tab:
                tab.click()
            remaining = self._remaining(trade_date, deadline)
            for packet in page.listen.steps(timeout=min(15.0, remaining)):
                self._raise_if_verification_required(page, trade_date, deadline)
                if LISTEN_TARGET not in str(getattr(packet, "target", "")):
                    continue
                response = decode_response(getattr(packet.response, "body", None))
                if response is not None:
                    return response
            self._remaining(trade_date, deadline)
            raise IncompleteJiuyanResponse(
                f"Jiuyan response timed out for {trade_date}"
            )
        finally:
            if page is not None:
                try:
                    page.listen.stop()
                except Exception:
                    pass
                try:
                    self.page_closer(name, page)
                except Exception:
                    pass
