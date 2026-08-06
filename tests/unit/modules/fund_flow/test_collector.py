import threading

from stock_lab.modules.fund_flow import collector
from stock_lab.modules.fund_flow.collector import save_snapshot


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
