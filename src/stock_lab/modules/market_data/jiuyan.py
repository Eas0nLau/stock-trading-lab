import datetime as dt
import json
import os
import re
import threading
import time

from loguru import logger


class IncompleteJiuyanResponse(RuntimeError):
    pass


PAGE_TEMPLATE = os.getenv("JIUYAN_ACTION_URL_TEMPLATE", "https://www.jiuyangongshe.com/action/{date_text}")
LISTEN_TARGET = "/jystock-app/api/v1/action/field"
MIN_REQUEST_INTERVAL_SECONDS = max(int(os.getenv("JIUYAN_MIN_REQUEST_INTERVAL_SECONDS", "60")), 1)
MAX_ATTEMPTS = max(int(os.getenv("JIUYAN_MAX_ATTEMPTS", "2")), 1)
_request_lock = threading.Lock()
_last_request_time = 0.0


def wait_for_request_slot():
    global _last_request_time
    with _request_lock:
        now = time.monotonic()
        wait_seconds = max(0.0, MIN_REQUEST_INTERVAL_SECONDS - (now - _last_request_time))
        if wait_seconds:
            time.sleep(wait_seconds)
        _last_request_time = time.monotonic()


def format_page_date(trade_date):
    return dt.datetime.strptime(str(int(trade_date)), "%Y%m%d").strftime("%Y-%m-%d")


def _value(row, *names, default=None):
    return next((row[name] for name in names if name in row and row[name] not in (None, "")), default)


def _float(value):
    try:
        return float(str(value).replace("%", "").strip())
    except (TypeError, ValueError):
        return None


def _int(value):
    try:
        text = str(value).strip()
        if not re.fullmatch(r"[+-]?\d+(?:\.\d+)?", text):
            text = "".join(re.findall(r"\d+", text))
        return int(float(text)) if text else 0
    except (TypeError, ValueError):
        return 0


def _date_time(trade_date, value):
    if value in (None, ""):
        return None
    text = str(value).strip()
    if len(text) <= 8 and ":" in text:
        return f"{str(trade_date)[:4]}-{str(trade_date)[4:6]}-{str(trade_date)[6:8]} {text}"
    return text


def _unwrap_rows(response):
    if not isinstance(response, dict):
        return []
    data = response.get("data", response)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return next((data[key] for key in ("rows", "list", "items", "records", "data", "diff") if isinstance(data.get(key), list)), [])
    return []


def parse_response(response, trade_date):
    records = []
    for group in _unwrap_rows(response):
        response_date = str(group.get("date") or "").replace("-", "") if isinstance(group, dict) else ""
        if response_date and response_date != str(int(trade_date)):
            raise IncompleteJiuyanResponse(
                f"请求日期 {trade_date} 与响应日期 {group.get('date')} 不一致"
            )
        if not isinstance(group, dict) or not isinstance(group.get("list"), list):
            records.append(group)
            continue
        for stock in group["list"]:
            action = (stock.get("article") or {}).get("action_info") or {}
            records.append({
                "板块": group.get("name"), "板块个股数量": group.get("count"),
                "股票代码": stock.get("code"), "股票名称": stock.get("name"),
                "涨幅": _float(action.get("shares_range")) / 100 if action.get("shares_range") else None,
                "涨停时间": action.get("time"), "几天几板": action.get("num"),
                "涨停解析": action.get("expound") or action.get("reason"),
            })
    rows = []
    for record in records:
        if not isinstance(record, dict):
            continue
        board = str(_value(record, "板块", "板块名称", "board", "board_name", default="")).strip()
        code = _int(_value(record, "股票代码", "code", "stock_code", "symbol"))
        change_pct = _float(_value(record, "涨幅", "涨跌幅", "pct_chg", "pct"))
        if not board or not code or change_pct is None or not 9.5 <= change_pct <= 10.2:
            continue
        rows.append({
            "data_id": f"{int(trade_date)}_{board}_{code}", "date": int(trade_date),
            "板块": board, "板块个股数量": _int(_value(record, "板块个股数量", "板块数量", "board_count")),
            "股票代码": code, "股票名称": _value(record, "股票名称", "name", "stock_name"),
            "code": _value(record, "code", "原始代码", default=str(code)),
            "涨停时间": _date_time(trade_date, _value(record, "涨停时间", "涨停时间文本", "limit_up_time")),
            "几天几板": _value(record, "几天几板", "连板", "board_count_text"),
            "涨幅": change_pct, "涨停解析": _value(record, "涨停解析", "解析", "description", default=""),
        })
    if not rows:
        raise IncompleteJiuyanResponse(f"No valid Jiuyan action records for {trade_date}")
    return rows


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


class JiuyanBrowserSource:
    def __init__(self, page_factory):
        self.page_factory = page_factory

    def __call__(self, trade_date):
        url = PAGE_TEMPLATE.format(date=int(trade_date), date_text=format_page_date(trade_date))
        wait_for_request_slot()
        page = self.page_factory("jiuyan-action", background=True)
        page.listen.start([LISTEN_TARGET])
        page.get(url, timeout=0)
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
