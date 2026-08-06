import json
import threading

from stock_lab.modules.strategy_pick.collector import LegacyStrategyPickCollectorAdapter, StrategyPickCollector, create_strategy_pick_collector, run_strategy_pick_monitor
from stock_lab.modules.strategy_pick.repository import StrategyPickRepository


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


def test_collector_normalizes_and_persists_legacy_collection_result():
    adapter = Adapter()
    repository = StrategyPickRepository(Redis())
    collector = StrategyPickCollector(repository, adapter=adapter)

    result = collector.refresh("eastmoney_1")

    assert result["strategyId"] == "eastmoney_1"
    assert repository.latest("eastmoney_1")["status"] == "success"
    assert adapter.calls == ["eastmoney_1"]


def test_official_worker_delegates_loop_to_injected_adapter():
    adapter = Adapter()
    repository = StrategyPickRepository(Redis())
    stop_event = threading.Event()
    collector = StrategyPickCollector(repository, adapter=adapter)

    run_strategy_pick_monitor(stop_event, collector=collector, adapter=adapter)

    assert adapter.calls == ["run", "eastmoney_1"]
    assert stop_event.is_set()


def test_legacy_worker_adapter_persists_due_results_through_official_collector():
    class Module:
        def 初始化策略配置(self): pass
        def 采集到期策略(self, now, slots, log_slots):
            stop_event.set()
            return [{"策略ID": "eastmoney_1", "采集日期": "20260806", "状态": "success", "股票列表": [], "新增股票": [], "移除股票": []}]

    stop_event = threading.Event()
    repository = StrategyPickRepository(Redis())
    adapter = LegacyStrategyPickCollectorAdapter(Module())
    collector = StrategyPickCollector(repository, adapter=adapter)

    adapter.run(stop_event, collector)

    assert repository.latest("eastmoney_1")["status"] == "success"


def test_fresh_official_collector_projects_default_config_for_legacy_collector():
    redis = Redis()

    create_strategy_pick_collector(redis, adapter=Adapter())

    strategies = json.loads(redis.values["策略选股:strategies"])
    first = strategies[0]
    assert first["id"] == "eastmoney_1"
    assert first["名称"] == "新高监控"
    assert first["页面URL"]
    assert first["监听目标"] == ["/api/smart-tag/stock/v3/pw/search-code"]
    assert first["监控时间段"] == [["09:20", "11:31"], ["13:00", "15:01"]]
    assert first["监控频率秒"] == 30
    assert first["启用"] is True
