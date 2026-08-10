import datetime
import json
import re
import time

from loguru import logger

from stock_lab.config import get_settings

from .collector import save_snapshot
from .contracts import normalize_net_inflow_100m


COLLECTION_WINDOWS = (
    (datetime.time(9, 27), datetime.time(11, 31)),
    (datetime.time(12, 58), datetime.time(15, 1)),
)
FLOW_CONFIG = {
    "industry": ("Industry fund flow", "https://data.eastmoney.com/bkzj/hy.html"),
    "concept": ("Concept fund flow", "https://data.eastmoney.com/bkzj/gn.html"),
}
LISTENER_POLL_SECONDS = 0.1
LISTENER_TOTAL_TIMEOUT_SECONDS = 5.0


def normalize_concept_name(value):
    return str(value or "").strip().strip("【】[]")


def normalize_concept_match(value):
    return re.sub(r"[\s_＿\-]+", "", normalize_concept_name(value)).upper()


def is_excluded_concept(value, excluded_names):
    name = normalize_concept_match(value)
    if not name:
        return False
    excluded = {normalize_concept_match(item) for item in excluded_names}
    return name in excluded or bool(
        re.match(r"^20\d{2}(年报|一季报|半年报|三季报)(预增|扭亏|预亏|预减|高增长)$", name)
    )


def parse_fund_flow_packets(packets, collected_at, flow_type, excluded_names=(), *, stop_event=None):
    flow_response = None
    leader_response = None
    for packet in packets:
        if stop_event is not None and stop_event.is_set():
            return []
        body = packet.response.body
        target = str(packet.target)
        if "/api/qt/clist/get" in target:
            if isinstance(body, dict):
                leader_response = body
            else:
                text = str(body)
                start, end = text.find("("), text.rfind(")")
                leader_response = json.loads(text[start + 1:end] if start >= 0 and end > start else text)
        elif isinstance(body, dict) and "/dataapi/bkzj/getbkzj" in target:
            flow_response = body
        if flow_response and leader_response:
            break
    if not flow_response or not leader_response:
        raise TimeoutError("EastMoney fund-flow responses were incomplete")
    leaders = {
        row.get("f12"): row.get("f204", "")
        for row in (leader_response.get("data") or {}).get("diff") or []
    }
    records = []
    for item in (flow_response.get("data") or {}).get("diff") or []:
        record = {
            "time": collected_at,
            "board_code": item.get("f12", ""),
            "board_name": str(item.get("f14", "")),
            "leader": str(leaders.get(item.get("f12"), "")),
            "net_inflow_100m": float(normalize_net_inflow_100m(item.get("f62") or 0, "yuan")),
        }
        if flow_type != "concept" or not is_excluded_concept(record["board_name"], excluded_names):
            records.append(record)
    if not records:
        raise RuntimeError("EastMoney returned no usable fund-flow records")
    return records


class FundFlowSource:
    def __init__(self, page_factory, repository, *, mysql_repository=None, settings=None, history_service=None, sleeper=time.sleep, clock=datetime.datetime.now):
        self.page_factory = page_factory
        self.repository = repository
        self.mysql_repository = mysql_repository
        self.settings = get_settings() if settings is None else settings
        if history_service is None:
            from .service import FundFlowService

            history_service = FundFlowService(
                repository,
                mysql_repository,
                default_top_n=self.settings.fund_flow_history_top_n,
            )
        self.history_service = history_service
        self.sleeper = sleeper
        self.clock = clock
        self.page = None

    def collection_interval_seconds(self):
        return self.settings.fund_flow_interval_seconds

    def initialize(self, *, stop_event=None):
        if stop_event is not None and stop_event.is_set():
            return None
        self.page = self.page_factory(
            "fund-flow",
            use_main_tab=True,
            stop_event=stop_event,
        )
        if self.page is None or (stop_event is not None and stop_event.is_set()):
            self.close()
            return None
        try:
            self.page.get("https://data.eastmoney.com/bkzj/hy.html", timeout=0)
        except Exception:
            self.close()
            raise
        if stop_event is not None and stop_event.is_set():
            self.close()
            return None
        return self.page

    def warm_history(self):
        top_n = max(int(self.settings.fund_flow_history_top_n or 0), 0)
        if top_n <= 0:
            return []
        warmed = []
        for flow_type in FLOW_CONFIG:
            dates = self.history_service.dates(flow_type).get("dates") or []
            if not dates:
                continue
            trade_date = max(str(date) for date in dates)
            try:
                self.history_service.history(flow_type, trade_date, top_n=top_n)
                warmed.append((flow_type, trade_date))
            except Exception as error:
                logger.warning("Could not warm {} fund-flow history for {}: {}", flow_type, trade_date, error)
        return warmed

    def wait_until_next_run(self, interval_seconds=None, *, stop_event=None):
        interval = interval_seconds or self.collection_interval_seconds()
        now = self.clock()
        elapsed = now.hour * 3600 + now.minute * 60 + now.second + now.microsecond / 1_000_000
        wait_seconds = (interval - elapsed % interval) % interval
        if wait_seconds:
            if stop_event is None:
                self.sleeper(wait_seconds)
            else:
                stop_event.wait(wait_seconds)

    def close(self):
        page, self.page = self.page, None
        if page is None:
            return
        try:
            listener = getattr(page, "listen", None)
            stop = getattr(listener, "stop", None)
            if callable(stop):
                stop()
        except Exception as error:
            logger.warning("Could not stop fund-flow listener: {}", error)
        try:
            close = getattr(page, "close", None)
            if callable(close):
                close()
        except Exception as error:
            logger.warning("Could not close fund-flow page: {}", error)

    @staticmethod
    def is_collection_time(now):
        return now.weekday() < 5 and any(start <= now.time() <= end for start, end in COLLECTION_WINDOWS)

    def collect(self, flow_type, *, stop_event=None):
        if stop_event is not None and stop_event.is_set():
            return []
        if self.page is None:
            self.initialize(stop_event=stop_event)
        if self.page is None or (stop_event is not None and stop_event.is_set()):
            return []
        name, url = FLOW_CONFIG[flow_type]
        now = self.clock()
        self.page.listen.start(["/dataapi/bkzj/getbkzj", "/api/qt/clist/get"])
        if stop_event is not None and stop_event.is_set():
            return []
        self.page.get(url, timeout=0)
        if stop_event is not None and stop_event.is_set():
            return []
        deadline = time.monotonic() + LISTENER_TOTAL_TIMEOUT_SECONDS
        packets = []
        while True:
            if stop_event is not None and stop_event.is_set():
                return []
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return parse_fund_flow_packets(
                    packets,
                    now.strftime("%H:%M:%S"),
                    flow_type,
                    self.settings.concept_exclusions,
                )
            timeout = min(LISTENER_POLL_SECONDS, remaining)
            for packet in self.page.listen.steps(timeout=timeout) or ():
                if stop_event is not None and stop_event.is_set():
                    return []
                packets.append(packet)
            try:
                records = parse_fund_flow_packets(
                    packets,
                    now.strftime("%H:%M:%S"),
                    flow_type,
                    self.settings.concept_exclusions,
                )
                break
            except TimeoutError:
                continue
        if stop_event is not None and stop_event.is_set():
            return []
        save_snapshot(
            self.repository,
            flow_type,
            now.strftime("%Y%m%d"),
            now.strftime("%H:%M:%S"),
            records,
            mysql_repository=self.mysql_repository,
        )
        logger.info("Collected {} {} rows", name, len(records))
        return records

    def collect_all(self, *, stop_event=None):
        records = {}
        for flow_type in FLOW_CONFIG:
            if stop_event is not None and stop_event.is_set():
                break
            records[flow_type] = self.collect(flow_type, stop_event=stop_event)
        return records
