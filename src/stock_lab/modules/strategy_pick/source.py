import datetime
import json
import re
import threading
import time

from loguru import logger

from stock_lab.config import get_settings


def decode_response(body):
    if isinstance(body, (dict, list)):
        return body
    if isinstance(body, bytes):
        try:
            body = body.decode("utf-8")
        except UnicodeDecodeError:
            return None
    text = str(body or "").strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        left, right = text.find("("), text.rfind(")")
        try:
            return json.loads(text[left + 1:right]) if left >= 0 and right > left else None
        except json.JSONDecodeError:
            return None


def _stock_code(value):
    match = re.search(r"\d{6}", str(value or ""))
    return match.group(0) if match else ""


def _market(value, code):
    text = str(value or "").upper()
    if "SH" in text or "上交" in text or text == "1" or code.startswith("6"):
        return "SH"
    if "BJ" in text or "北交" in text or text == "2" or code.startswith(("4", "8")):
        return "BJ"
    return "SZ"


def _normalize_concept(value):
    return re.sub(r"[\s_＿\-]+", "", str(value or "").strip().strip("【】[]")).upper()


def _clean_concepts(value, excluded_concepts):
    text = str(value or "").strip()
    bracketed = re.findall(r"【([^】]+)】", text)
    items = bracketed or re.split(r"[、,，;；\s]+", text)
    excluded = {_normalize_concept(item) for item in excluded_concepts}
    result = []
    for item in items:
        name = str(item or "").strip().strip("【】[]")
        normalized = _normalize_concept(name)
        if not normalized or normalized in excluded:
            continue
        if re.match(r"^20\d{2}(年报|一季报|半年报|三季报)(预增|扭亏|预亏|预减|高增长)$", normalized):
            continue
        if name not in result:
            result.append(name)
    return "、".join(result)


def parse_strategy_response(payload, excluded_concepts=()):
    if not isinstance(payload, dict):
        return None
    data = payload.get("data")
    if not isinstance(data, dict):
        return None
    result = data.get("result") or {}
    if not isinstance(result, dict):
        return None
    rows = result.get("dataList")
    if not isinstance(rows, list):
        return None
    columns = {
        column.get("key"): column
        for column in result.get("columns") or []
        if isinstance(column, dict) and column.get("key")
    }
    ignored = {"SERIAL", "SECURITY_CODE", "SECURITY_SHORT_NAME", "MARKET_SHORT_NAME", "MARKET_NUM"}
    stocks = []
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        code = _stock_code(row.get("SECURITY_CODE"))
        name = str(row.get("SECURITY_SHORT_NAME") or "").strip()
        if not code or not name or code in seen:
            continue
        fields = {}
        used_labels = set()
        for key, column in columns.items():
            value = row.get(key)
            if key in ignored or value in (None, ""):
                continue
            label = str(column.get("title") or key)
            if label in used_labels:
                label = f"{label}({key})"
            used_labels.add(label)
            if "概念" in label or "CONCEPT" in label.upper():
                value = _clean_concepts(value, excluded_concepts)
                if not value:
                    continue
            fields[label] = value
        for key, value in row.items():
            if key not in ignored and key not in columns and value not in (None, ""):
                fields[str(key)] = value
        stocks.append({
            "code": code,
            "name": name,
            "market": _market(
                row.get("MARKET_SHORT_NAME") or row.get("TRADEMARKET") or row.get("MARKET_NUM"),
                code,
            ),
            "fields": fields,
        })
        seen.add(code)
    return stocks


def _parse_time(value):
    for format_text in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.datetime.strptime(str(value), format_text).time()
        except ValueError:
            continue
    return None


def is_monitor_time(strategy, now):
    periods = strategy.get("monitorPeriods") or [["09:00", "15:00"]]
    return any(
        start is not None and end is not None and start <= now.time() <= end
        for start, end in ((_parse_time(period[0]), _parse_time(period[1])) for period in periods)
    )


def execution_slot(strategy, now):
    interval = max(int(strategy.get("monitorIntervalSeconds") or 60), 1)
    seconds = now.hour * 3600 + now.minute * 60 + now.second
    return f"{now:%Y%m%d}:{seconds // interval}"


class HumanVerificationRequired(RuntimeError):
    """The source page requires a user to complete an anti-bot challenge."""


def page_requires_human_verification(page) -> bool:
    prompts = ("拖动下方滑块完成拼图", "拖动左边滑块完成上方拼图")
    for prompt in prompts:
        try:
            if page.ele(f"text={prompt}", timeout=0.1):
                return True
        except Exception:
            continue
    try:
        html = str(getattr(page, "html", "") or "")
    except Exception:
        return False
    return any(prompt in html for prompt in prompts)


class StrategyPickSource:
    def __init__(self, page_factory, repository, *, settings=None, clock=datetime.datetime.now, sleeper=time.sleep):
        self.page_factory = page_factory
        self.repository = repository
        self.settings = get_settings() if settings is None else settings
        self.clock = clock
        self.sleeper = sleeper
        self._lock = threading.RLock()

    def _strategy(self, strategy_id):
        strategy = next((item for item in self.repository.strategies() if item.get("id") == strategy_id), None)
        if strategy is None:
            raise KeyError(f"Strategy does not exist: {strategy_id}")
        return strategy

    def _collect_stocks(self, strategy):
        page = self.page_factory(
            f"strategy-pick:{strategy['id']}",
            strategy["pageUrl"],
            background=True,
        )
        page.listen.start(strategy.get("listenTargets") or ["/api/smart-tag/stock/v3/pw/search-code"])
        page.get(strategy["pageUrl"], timeout=0)
        if page_requires_human_verification(page):
            raise HumanVerificationRequired("Eastmoney requires manual slider verification")
        for packet in page.listen.steps(timeout=self.settings.strategy_pick_timeout_seconds):
            payload = decode_response(packet.response.body)
            stocks = parse_strategy_response(payload, self.settings.concept_exclusions)
            if stocks is not None:
                return stocks
        raise TimeoutError("Strategy response did not contain a complete stock list")

    def collect(self, strategy_id):
        strategy = self._strategy(strategy_id)
        last_error = None
        with self._lock:
            for attempt in range(1, self.settings.strategy_pick_max_retries + 1):
                try:
                    return self._snapshot(strategy, self._collect_stocks(strategy))
                except HumanVerificationRequired as error:
                    last_error = error
                    break
                except Exception as error:
                    last_error = error
                    logger.warning("Strategy collection attempt {}/{} failed: {}", attempt, self.settings.strategy_pick_max_retries, error)
                    if attempt < self.settings.strategy_pick_max_retries:
                        self.sleeper(0.5)
        now = self.clock()
        return {
            "strategyId": strategy_id, "strategyName": strategy.get("name", strategy_id),
            "collectedDate": now.strftime("%Y%m%d"), "collectedTime": now.strftime("%H:%M:%S"),
            "status": "failed", "stocks": [], "addedStocks": [], "removedStocks": [],
            "errorMessage": str(last_error or "No complete stock list was returned"),
        }

    def _snapshot(self, strategy, stocks):
        now = self.clock()
        strategy_id = strategy["id"]
        state = self.repository.selected_state(strategy_id)
        old_codes = set(state.get("codes") or [])
        old_info = dict(state.get("stockInfo") or {})
        stock_map = {stock["code"]: dict(stock) for stock in stocks}
        current_codes = set(stock_map)
        added = []
        for code in sorted(current_codes - old_codes):
            stock = stock_map[code]
            event = {
                "eventId": f"{now:%Y%m%d-%H%M%S}-{strategy_id}-{code}",
                "strategyId": strategy_id, "strategyName": strategy.get("name", strategy_id),
                "selectedDate": now.strftime("%Y%m%d"), "selectedAt": now.strftime("%Y-%m-%d %H:%M:%S"),
                **stock,
            }
            added.append(event)
            old_info[code] = event
        removed = [
            {"strategyId": strategy_id, "strategyName": strategy.get("name", strategy_id),
             "code": code, "name": old_info.pop(code, {}).get("name", ""),
             "removedDate": now.strftime("%Y%m%d"), "removedTime": now.strftime("%H:%M:%S")}
            for code in sorted(old_codes - current_codes)
        ]
        for stock in stocks:
            stock.update({
                "strategyId": strategy_id,
                "strategyName": strategy.get("name", strategy_id),
                "selectedAt": (old_info.get(stock["code"]) or {}).get("selectedAt", ""),
                "lastCollectedAt": now.strftime("%Y-%m-%d %H:%M:%S"),
            })
        return {
            "strategyId": strategy_id, "strategyName": strategy.get("name", strategy_id),
            "collectedDate": now.strftime("%Y%m%d"), "collectedTime": now.strftime("%H:%M:%S"),
            "status": "success", "stocks": stocks, "addedStocks": added,
            "removedStocks": removed, "errorMessage": "",
        }

    def run(self, stop_event, collector):
        slots = {}
        while not stop_event.is_set():
            now = self.clock()
            for strategy in self.repository.strategies():
                if not strategy.get("enabled", True) or not is_monitor_time(strategy, now):
                    continue
                slot = execution_slot(strategy, now)
                if slots.get(strategy["id"]) == slot:
                    continue
                slots[strategy["id"]] = slot
                collector.refresh(strategy["id"])
            stop_event.wait(1)
