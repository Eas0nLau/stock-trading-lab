import json
import os
import random
import threading
import time

from loguru import logger

from .jiuyan_parsing import IncompleteJiuyanResponse, ParsedJiuyanBatch, parse_batch, parse_response



class HumanVerificationRequired(IncompleteJiuyanResponse):
    pass


PAGE_TEMPLATE = os.getenv("JIUYAN_ACTION_URL_TEMPLATE", "https://www.jiuyangongshe.com/action/{date_text}")
LISTEN_TARGET = "/jystock-app/api/v1/action/field"
MIN_REQUEST_INTERVAL_SECONDS = max(int(os.getenv("JIUYAN_MIN_REQUEST_INTERVAL_SECONDS", "60")), 1)
MAX_REQUEST_INTERVAL_SECONDS = max(int(os.getenv("JIUYAN_MAX_REQUEST_INTERVAL_SECONDS", "105")), MIN_REQUEST_INTERVAL_SECONDS)
MAX_ATTEMPTS = max(int(os.getenv("JIUYAN_MAX_ATTEMPTS", "2")), 1)
_request_lock = threading.Lock()
_last_request_time = 0.0


def wait_for_request_slot():
    global _last_request_time
    with _request_lock:
        now = time.monotonic()
        wait_seconds = max(0.0, random.uniform(MIN_REQUEST_INTERVAL_SECONDS, MAX_REQUEST_INTERVAL_SECONDS) - (now - _last_request_time))
        if wait_seconds:
            time.sleep(wait_seconds)
        _last_request_time = time.monotonic()


def format_page_date(trade_date):
    return time.strftime("%Y-%m-%d", time.strptime(str(int(trade_date)), "%Y%m%d"))


def _decode_response(body):
    if isinstance(body, dict):
        return body
    text = str(body or "").strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("("), text.rfind(")")
        return json.loads(text[start + 1:end]) if start >= 0 and end > start else None


def page_requires_human_verification(page) -> bool:
    prompts = ("拖动下方滑块完成拼图", "拖动左边滑块完成上方拼图")
    for prompt in prompts:
        try:
            if page.ele(f"text={prompt}", timeout=0.1):
                return True
        except Exception:
            continue
    try:
        return any(prompt in str(getattr(page, "html", "") or "") for prompt in prompts)
    except Exception:
        return False


class JiuyanBrowserSource:
    def __init__(self, page_factory):
        self.page_factory = page_factory

    def __call__(self, trade_date):
        url = PAGE_TEMPLATE.format(date=int(trade_date), date_text=format_page_date(trade_date))
        wait_for_request_slot()
        page = self.page_factory("jiuyan-action", background=True)
        page.listen.start([LISTEN_TARGET])
        page.get(url, timeout=0)
        if page_requires_human_verification(page):
            raise HumanVerificationRequired("Jiuyan requires manual slider verification")
        tab = page.ele("text=全部异动解析")
        if tab:
            tab.click()
        for packet in page.listen.steps(timeout=15):
            if LISTEN_TARGET in str(getattr(packet, "target", "")):
                response = _decode_response(getattr(packet.response, "body", None))
                if response is not None:
                    return response
        raise IncompleteJiuyanResponse(f"Jiuyan response timed out for {trade_date}")


class JiuyanCollector:
    def __init__(self, repository, response_source, parser=parse_response, max_attempts=MAX_ATTEMPTS):
        self.repository = repository
        self.response_source = response_source
        self.parser = parser
        self.max_attempts = max(int(max_attempts), 1)

    def collect(self, trade_date):
        last_error = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                rows = self.parser(self.response_source(int(trade_date)), int(trade_date))
                canonical = [{
                    "data_id": row.get("data_id"), "trade_date": row.get("date"),
                    "board_name": row.get("板块"), "board_stock_count": row.get("板块个股数量"),
                    "stock_code": str(row.get("股票代码") or "").zfill(6), "stock_name": row.get("股票名称"),
                    "source_code": row.get("code"), "limit_up_at": row.get("涨停时间"),
                    "board_streak": row.get("几天几板"), "change_pct": row.get("涨幅"),
                    "limit_up_reason": row.get("涨停解析"),
                } for row in rows]
                return self.repository.upsert_jiuyan_actions(canonical)
            except HumanVerificationRequired:
                raise
            except Exception as error:
                last_error = error
                logger.warning("Jiuyan collection attempt {}/{} failed: {}", attempt, self.max_attempts, error)
        raise IncompleteJiuyanResponse(f"Jiuyan collection failed for {trade_date}: {last_error}") from last_error


def create_default_collector():
    from stock_lab.infrastructure.browser import create_page

    from .collectors import create_default_repository

    return JiuyanCollector(create_default_repository(), JiuyanBrowserSource(create_page))


def collect_jiuyan_actions(trade_date):
    return create_default_collector().collect(trade_date)
