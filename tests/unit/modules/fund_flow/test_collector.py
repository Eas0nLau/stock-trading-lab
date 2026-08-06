import threading
from types import SimpleNamespace

from stock_lab.modules.fund_flow import collector
from stock_lab.modules.fund_flow.collector import save_snapshot
from stock_lab.modules.fund_flow.source import FundFlowSource


class Repository:
    def __init__(self):
        self.saved = None
        self.published = None

    def save_history(self, flow_type, trade_date, records):
        self.saved = (flow_type, trade_date, records)

    def publish_snapshot(self, flow_type, trade_date, collected_at, record_count):
        self.published = (flow_type, trade_date, collected_at, record_count)


def test_collector_writes_and_publishes_english_v1_snapshot():
    repository = Repository()
    records = [{"时间": "10:00:00", "板块名称": "机器人", "资金净流入(亿)": 3}]
    save_snapshot(
        repository,
        "concept",
        "20260806",
        "10:00:00",
        records,
    )

    assert repository.saved == (
        "concept",
        "20260806",
        [{"time": "10:00:00", "board_name": "机器人", "net_inflow_100m": 3}],
    )
    assert repository.published == ("concept", "20260806", "10:00:00", 1)


def test_monitor_uses_injected_source_contract_and_logs_startup(monkeypatch):
    calls = []

    class Source:
        def collection_interval_seconds(self): return 30
        def initialize(self): calls.append("initialize")
        def warm_history(self): calls.append("warm_history")

    class Logger:
        def info(self, message, interval): calls.append((message, interval))

    stop_event = threading.Event()
    stop_event.set()
    monkeypatch.setattr(collector, "logger", Logger())

    collector.run_fund_flow_monitor(stop_event, source=Source())

    assert calls == [
        ("Fund-flow scheduler started with a {} second interval", 30),
        "initialize",
        "warm_history",
    ]


def test_source_warms_latest_history_for_both_flow_types():
    calls = []

    class HistoryService:
        def dates(self, flow_type):
            return {"dates": ["20260805", "20260806"] if flow_type == "industry" else ["20260804"]}

        def history(self, flow_type, trade_date, top_n=None):
            calls.append((flow_type, trade_date, top_n))

    source = FundFlowSource(
        lambda *_args, **_kwargs: None,
        object(),
        settings=SimpleNamespace(fund_flow_interval_seconds=30, fund_flow_history_top_n=5),
        history_service=HistoryService(),
    )

    source.warm_history()

    assert calls == [
        ("industry", "20260806", 5),
        ("concept", "20260804", 5),
    ]


def test_monitor_stop_interrupts_long_wait_and_closes_page():
    stop_event = threading.Event()
    waiting = threading.Event()
    closed = []

    class Page:
        def close(self):
            closed.append(True)

    class Source:
        def collection_interval_seconds(self): return 3600
        def initialize(self): self.page = Page()
        def warm_history(self): pass
        def wait_until_next_run(self, stop_event=None):
            waiting.set()
            stop_event.wait(timeout=3600)
        def close(self): self.page.close()

    source = Source()
    thread = threading.Thread(
        target=collector.run_fund_flow_monitor,
        args=(stop_event,),
        kwargs={"source": source},
    )
    thread.start()
    assert waiting.wait(timeout=1)
    stop_event.set()
    thread.join(timeout=1)

    assert not thread.is_alive()
    assert closed == [True]
