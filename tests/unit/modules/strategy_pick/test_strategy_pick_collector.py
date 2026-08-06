import json
import threading
from datetime import datetime

from stock_lab.modules.strategy_pick import collector as collector_module
from stock_lab.modules.strategy_pick.collector import StrategyPickCollector, create_strategy_pick_collector, run_strategy_pick_monitor
from stock_lab.modules.strategy_pick.repository import StrategyPickRepository
from stock_lab.modules.strategy_pick.source import parse_strategy_response


class Redis:
    def __init__(self): self.values = {}; self.lists = {}; self.sets = {}
    def get(self, key): return self.values.get(key)
    def set(self, key, value): self.values[key] = value
    def rpush(self, key, value): self.lists.setdefault(key, []).append(value)
    def sadd(self, key, *values): self.sets.setdefault(key, set()).update(values)
    def smembers(self, key): return self.sets.get(key, set())
    def lrange(self, key, start, end): return self.lists.get(key, [])
    def keys(self, pattern): return []


class Adapter:
    def __init__(self): self.calls = []
    def collect(self, strategy_id):
        self.calls.append(strategy_id)
        return {"策略ID": strategy_id, "策略名称": "新高监控", "采集日期": "20260806", "采集时间": "10:00:00", "状态": "success", "股票列表": [], "新增股票": [], "移除股票": []}
    def run(self, stop_event, collector):
        self.calls.append("run")
        collector.refresh("eastmoney_1")
        stop_event.set()


def test_eastmoney_response_normalizes_stock_code_market_and_fields():
    payload = {
        "data": {
            "result": {
                "columns": [{"key": "NEW_PRICE", "title": "最新价"}],
                "dataList": [{
                    "SECURITY_CODE": "1.600000",
                    "SECURITY_SHORT_NAME": "浦发银行",
                    "MARKET_SHORT_NAME": "上交所",
                    "NEW_PRICE": 12.3,
                }],
            }
        }
    }

    assert parse_strategy_response(payload) == [{
        "code": "600000",
        "name": "浦发银行",
        "market": "SH",
        "fields": {"最新价": 12.3},
    }]


def test_eastmoney_response_filters_configured_concept_labels():
    payload = {"data": {"result": {
        "columns": [{"key": "CONCEPT", "title": "所属概念"}],
        "dataList": [{
            "SECURITY_CODE": "000001",
            "SECURITY_SHORT_NAME": "平安银行",
            "CONCEPT": "【融资融券】【机器人】【2026年报预增】",
        }],
    }}}

    stocks = parse_strategy_response(payload, excluded_concepts=("融资融券",))

    assert stocks[0]["fields"] == {"所属概念": "机器人"}


def test_collector_normalizes_and_persists_legacy_collection_result():
    adapter = Adapter()
    repository = StrategyPickRepository(Redis())
    collector = StrategyPickCollector(repository, adapter=adapter)

    result = collector.refresh("eastmoney_1")

    assert result["strategyId"] == "eastmoney_1"
    assert repository.latest("eastmoney_1")["status"] == "success"
    assert adapter.calls == ["eastmoney_1"]


def test_collector_defaults_missing_collection_date_from_clock(monkeypatch):
    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 8, 8, 10, 0, 0)

    assert hasattr(collector_module, "datetime")
    monkeypatch.setattr(collector_module.datetime, "datetime", FixedDateTime)
    repository = StrategyPickRepository(Redis())
    collector = StrategyPickCollector(repository, adapter=Adapter())

    result = collector.persist_legacy_snapshot({
        "strategyId": "eastmoney_1",
        "status": "failed",
        "stocks": [],
        "addedStocks": [],
    })

    assert result["collectedDate"] == "20260808"
    assert repository.history("eastmoney_1", "20260808") == [result]


def test_official_worker_delegates_loop_to_injected_adapter():
    adapter = Adapter()
    repository = StrategyPickRepository(Redis())
    stop_event = threading.Event()
    collector = StrategyPickCollector(repository, adapter=adapter)

    run_strategy_pick_monitor(stop_event, collector=collector, adapter=adapter)

    assert adapter.calls == ["run", "eastmoney_1"]
    assert stop_event.is_set()


def test_fresh_official_collector_persists_default_config_to_v1():
    redis = Redis()

    create_strategy_pick_collector(redis, adapter=Adapter())

    strategies = json.loads(redis.values["strategy_pick:v1:strategies"])
    first = strategies[0]
    assert first["id"] == "eastmoney_1"
    assert first["name"] == "新高监控"
    assert first["pageUrl"]
    assert first["listenTargets"] == ["/api/smart-tag/stock/v3/pw/search-code"]
    assert first["monitorPeriods"] == [["09:20", "11:31"], ["13:00", "15:01"]]
    assert first["monitorIntervalSeconds"] == 30
    assert first["enabled"] is True
