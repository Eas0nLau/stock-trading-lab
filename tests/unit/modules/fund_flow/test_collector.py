import importlib
import json
import threading

from stock_lab.modules.fund_flow import collector
from stock_lab.modules.fund_flow.collector import save_legacy_snapshot


class Repository:
    def __init__(self):
        self.saved = None
        self.published = None

    def save_history(self, flow_type, trade_date, records):
        self.saved = (flow_type, trade_date, records)

    def publish_snapshot(self, flow_type, trade_date, collected_at, record_count):
        self.published = (flow_type, trade_date, collected_at, record_count)


class LegacyWriter:
    def __init__(self):
        self.saved = None

    def save_snapshot(self, flow_type, trade_date, collected_at, records):
        self.saved = (flow_type, trade_date, collected_at, records)


def test_collector_adapter_writes_and_publishes_english_v1_snapshot():
    repository = Repository()
    legacy_writer = LegacyWriter()
    records = [{"时间": "10:00:00", "板块名称": "机器人", "资金净流入(亿)": 3}]
    save_legacy_snapshot(
        repository,
        "concept",
        "20260806",
        "10:00:00",
        records,
        legacy_writer=legacy_writer,
    )

    assert repository.saved == (
        "concept",
        "20260806",
        [{"time": "10:00:00", "board_name": "机器人", "net_inflow_100m": 3}],
    )
    assert repository.published == ("concept", "20260806", "10:00:00", 1)
    assert legacy_writer.saved == ("concept", "20260806", "10:00:00", records)


def test_monitor_uses_english_legacy_adapter_contract_and_logs_startup(monkeypatch):
    calls = []

    class LegacyAdapter:
        def collection_interval_seconds(self): return 30
        def initialize(self): calls.append("initialize")
        def warm_history(self): calls.append("warm_history")

    class Logger:
        def info(self, message, interval): calls.append((message, interval))

    stop_event = threading.Event()
    stop_event.set()
    monkeypatch.setattr(collector, "logger", Logger())

    collector.run_fund_flow_monitor(stop_event, legacy_adapter=LegacyAdapter())

    assert calls == [
        ("Fund-flow scheduler started with a {} second interval", 30),
        "initialize",
        "warm_history",
    ]


def test_legacy_collector_keeps_direct_history_current_without_duplicate_v1_snapshots(monkeypatch):
    legacy_module = importlib.import_module("实时监控.资金流向")

    class Redis:
        def __init__(self):
            self.values = {}
            self.sets = {}
            self.lists = {}

        def get(self, key): return self.values.get(key)
        def set(self, key, value): self.values[key] = value
        def sadd(self, key, value): self.sets.setdefault(key, set()).add(value)
        def smembers(self, key): return self.sets.get(key, set())
        def lrange(self, key, start, end): return []
        def keys(self, pattern): return []
        def lindex(self, key, index):
            values = self.lists.get(key, [])
            return values[index] if values else None
        def lset(self, key, index, value): self.lists[key][index] = value
        def rpush(self, key, value): self.lists.setdefault(key, []).append(value)

    redis = Redis()
    monkeypatch.setattr(legacy_module.db, "redis_con_localhost", redis)

    legacy_module._写入资金流向redis(
        "fund_flow",
        "20260806",
        "10:00:00",
        [{"时间": "10:00:00", "板块名称": "机器人", "资金净流入(亿)": 3}],
    )
    legacy_module._写入资金流向redis(
        "fund_flow",
        "20260806",
        "10:00:00",
        [{"时间": "10:00:00", "板块名称": "算力", "资金净流入(亿)": 4}],
    )

    legacy_history = redis.lists["fund_flow:history:20260806"]
    assert len(legacy_history) == 1
    assert json.loads(legacy_history[0])[0]["板块名称"] == "算力"
    assert "fund_flow:latest" in redis.values

    v1_history = json.loads(redis.values["fund_flow:v1:industry:history:20260806"])
    assert v1_history == [[{
        "time": "10:00:00",
        "board_name": "算力",
        "net_inflow_100m": 4,
    }]]
