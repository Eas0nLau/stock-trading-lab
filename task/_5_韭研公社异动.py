import datetime as dt
import json
import os
import random
import re
import threading
import time

from loguru import logger

from task.data_sources import _upsert_rows


class IncompleteJiuyanResponse(RuntimeError):
    """The Jiuyan response did not contain a usable action board."""


class 需要人工验证(IncompleteJiuyanResponse):
    """The page is blocked by a manual slider verification."""


页面模板 = os.getenv(
    "JIUYAN_ACTION_URL_TEMPLATE",
    "https://www.jiuyangongshe.com/action/{date_text}",
)
监听路径 = "/jystock-app/api/v1/action/field"
最小请求间隔秒 = max(int(os.getenv("JIUYAN_MIN_REQUEST_INTERVAL_SECONDS", "60")), 1)
最大随机请求间隔秒 = max(int(os.getenv("JIUYAN_MAX_REQUEST_INTERVAL_SECONDS", "105")), 最小请求间隔秒)
最大尝试次数 = max(int(os.getenv("JIUYAN_MAX_ATTEMPTS", "2")), 1)
Redis请求锁 = "jiuyan:action:request_slot"
_频率锁 = threading.Lock()
_上次请求时间 = 0.0


def 随机请求间隔秒():
    return random.uniform(最小请求间隔秒, 最大随机请求间隔秒)


def 等待请求频率():
    global _上次请求时间
    with _频率锁:
        now = time.monotonic()
        wait_seconds = max(0.0, 随机请求间隔秒() - (now - _上次请求时间))
        if wait_seconds:
            time.sleep(wait_seconds)
        _上次请求时间 = time.monotonic()


def _等待Redis请求频率():
    try:
        from utils import db
    except Exception:
        return

    while True:
        try:
            if db.redis_con_localhost.set(
                    Redis请求锁,
                    str(time.time()),
                    nx=True,
                    ex=最小请求间隔秒,
            ):
                return
            ttl = db.redis_con_localhost.ttl(Redis请求锁)
            time.sleep(max(int(ttl or 1), 1))
        except Exception as error:
            logger.warning(f"韭研请求频率 Redis 锁不可用，使用进程内限流：{error}")
            return


def _value(row, *names, default=None):
    for name in names:
        if name in row and row[name] not in (None, ""):
            return row[name]
    return default


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


def _date_time(date, value):
    if value in (None, ""):
        return None
    text = str(value).strip()
    if len(text) <= 8 and ":" in text:
        return f"{str(date)[:4]}-{str(date)[4:6]}-{str(date)[6:8]} {text}"
    return text


def 格式化页面日期(date):
    return dt.datetime.strptime(str(int(date)), "%Y%m%d").strftime("%Y-%m-%d")


def _unwrap_rows(response):
    if not isinstance(response, dict):
        return []
    data = response.get("data", response)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("rows", "list", "items", "records", "data", "diff"):
            value = data.get(key)
            if isinstance(value, list):
                return value
    return []


def 解析异动响应(response, date):
    records = []
    for group in _unwrap_rows(response):
        response_date = str(group.get("date") or "").replace("-", "") if isinstance(group, dict) else ""
        if response_date and response_date != str(int(date)):
            raise IncompleteJiuyanResponse(
                f"请求日期 {date} 与响应日期 {group.get('date')} 不一致"
            )
        if not isinstance(group, dict) or not isinstance(group.get("list"), list):
            records.append(group)
            continue
        for stock in group["list"]:
            article = stock.get("article") or {}
            action_info = article.get("action_info") or {}
            records.append({
                "板块": group.get("name"),
                "板块个股数量": group.get("count"),
                "股票代码": stock.get("code"),
                "股票名称": stock.get("name"),
                "涨幅": _float(action_info.get("shares_range")) / 100 if action_info.get("shares_range") else None,
                "涨停时间": action_info.get("time"),
                "几天几板": action_info.get("num"),
                "涨停解析": action_info.get("expound") or action_info.get("reason"),
            })
    rows = []
    for record in records:
        if not isinstance(record, dict):
            continue
        board = str(_value(record, "板块", "板块名称", "board", "board_name", default="")).strip()
        code = _int(_value(record, "股票代码", "股票代码", "code", "stock_code", "symbol"))
        pct = _float(_value(record, "涨幅", "涨跌幅", "pct_chg", "pct"))
        if not board or not code or pct is None or not 9.5 <= pct <= 10.2:
            continue
        rows.append({
            "data_id": f"{int(date)}_{board}_{code}",
            "date": int(date),
            "板块": board,
            "板块个股数量": _int(_value(record, "板块个股数量", "板块数量", "board_count")),
            "股票代码": code,
            "股票名称": _value(record, "股票名称", "name", "stock_name"),
            "code": _value(record, "code", "原始代码", default=str(code)),
            "涨停时间": _date_time(date, _value(record, "涨停时间", "涨停时间文本", "limit_up_time")),
            "几天几板": _value(record, "几天几板", "连板", "board_count_text"),
            "涨幅": pct,
            "涨停解析": _value(record, "涨停解析", "解析", "description", default=""),
        })
    if not rows:
        raise IncompleteJiuyanResponse(f"{date} 未解析到有效韭研公社异动记录")
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
        start = text.find("(")
        end = text.rfind(")")
        if start >= 0 and end > start:
            return json.loads(text[start + 1:end])
    return None


def _采集响应(date):
    from utils import driver_chrome

    url = 页面模板.format(date=int(date), date_text=格式化页面日期(date))
    等待请求频率()
    _等待Redis请求频率()
    page = driver_chrome.初始化页面(
        "jiuyan-action",
        url=None,
        background=True,
        关闭旧页面=False,
    )
    page.listen.start([监听路径])
    page.get(url, timeout=0)
    if 页面需要人工验证(page):
        raise 需要人工验证("韭研公社页面需要人工完成滑块验证")
    tab = page.ele("text=全部异动解析")
    if tab:
        tab.click()
    for packet in page.listen.steps(timeout=15):
        target = str(getattr(packet, "target", ""))
        if 监听路径 not in target:
            continue
        response = _decode_response(getattr(packet.response, "body", None))
        if response is not None:
            return response
    raise IncompleteJiuyanResponse(f"{date} 韭研公社异动接口响应超时")


def 韭研公社异动采集(date):
    last_error = None
    for attempt in range(1, 最大尝试次数 + 1):
        try:
            rows = 解析异动响应(_采集响应(int(date)), int(date))
            columns = [
                "data_id", "date", "板块", "板块个股数量", "股票代码", "股票名称", "code",
                "涨停时间", "几天几板", "涨幅", "涨停解析",
            ]
            return _upsert_rows("t_韭研公社异动解析", columns, rows, ["data_id"])
        except 需要人工验证:
            raise
        except Exception as error:
            last_error = error
            logger.warning(f"韭研公社异动采集失败，第 {attempt}/{最大尝试次数} 次：{error}")
    raise IncompleteJiuyanResponse(f"{date} 韭研公社异动采集失败：{last_error}") from last_error


def 页面需要人工验证(page):
    验证提示 = ("拖动下方滑块完成拼图", "拖动左边滑块完成上方拼图")
    for text in 验证提示:
        try:
            if page.ele(f"text={text}", timeout=0.1):
                return True
        except Exception:
            continue
    try:
        html = str(page.html or "")
        return any(text in html for text in 验证提示)
    except Exception:
        return False
