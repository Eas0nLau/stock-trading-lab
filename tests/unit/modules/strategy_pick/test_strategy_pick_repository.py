import json

from stock_lab.modules.strategy_pick.repository import StrategyPickRepository


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.lists = {}
        self.sets = {}

    def get(self, key): return self.values.get(key)
    def set(self, key, value): self.values[key] = value
    def delete(self, key): self.values.pop(key, None); self.sets.pop(key, None)
    def rpush(self, key, value): self.lists.setdefault(key, []).append(value)
    def lrange(self, key, start, end): return self.lists.get(key, [])[start:(None if end == -1 else end + 1)]
    def sadd(self, key, *values): self.sets.setdefault(key, set()).update(values)
    def smembers(self, key): return self.sets.get(key, set())
    def keys(self, pattern):
        prefix = pattern.removesuffix("*")
        return [key for key in [*self.values, *self.lists, *self.sets] if key.startswith(prefix)]


def test_repository_writes_and_reads_v1_strategy_data_using_ascii_keys():
    redis = FakeRedis()
    repository = StrategyPickRepository(redis)
    strategy = {"id": "eastmoney_1", "name": "新高监控", "enabled": True}
    snapshot = {"strategyId": "eastmoney_1", "collectedDate": "20260806", "stocks": []}

    repository.save_strategies([strategy])
    repository.save_snapshot("eastmoney_1", snapshot, update_latest=True)
    repository.save_events("eastmoney_1", "20260806", [{"eventId": "evt-1", "code": "600000"}])

    assert repository.strategies() == [strategy]
    assert repository.latest("eastmoney_1") == snapshot
    assert repository.events("eastmoney_1", "20260806") == [{"eventId": "evt-1", "code": "600000"}]
    assert repository.dates("eastmoney_1") == ["20260806"]
    v1_keys = [key for key in [*redis.values, *redis.lists, *redis.sets] if key.startswith("strategy_pick:v1:")]
    assert v1_keys and all(key.isascii() for key in v1_keys)


def test_repository_does_not_read_retired_latest_when_v1_value_is_missing():
    redis = FakeRedis()
    redis.values["retired:latest"] = json.dumps({"strategyId": "eastmoney_1"})
    repository = StrategyPickRepository(redis)

    assert repository.latest("eastmoney_1") == {}


def test_repository_does_not_scan_keys_for_missing_strategy():
    redis = FakeRedis()
    redis.keys = lambda _pattern: (_ for _ in ()).throw(AssertionError("key scan is forbidden"))
    repository = StrategyPickRepository(redis)

    assert repository.latest("eastmoney_2") == {}
    assert repository.dates("eastmoney_2") == []


def test_repository_writes_only_v1_strategy_config_for_fresh_collector():
    redis = FakeRedis()
    repository = StrategyPickRepository(redis)
    repository.save_strategies([{
        "id": "eastmoney_1",
        "name": "新高监控",
        "pageUrl": "https://example.test/strategy",
        "listenTargets": ["/api/search"],
        "monitorPeriods": [["09:20", "11:31"], ["13:00", "15:01"]],
        "monitorIntervalSeconds": 30,
        "enabled": True,
        "createdAt": "2026-08-06 09:00:00",
        "updatedAt": "2026-08-06 09:01:00",
    }])

    assert json.loads(redis.values["strategy_pick:v1:strategies"]) == [{
        "id": "eastmoney_1",
        "name": "新高监控",
        "pageUrl": "https://example.test/strategy",
        "listenTargets": ["/api/search"],
        "monitorPeriods": [["09:20", "11:31"], ["13:00", "15:01"]],
        "monitorIntervalSeconds": 30,
        "enabled": True,
        "createdAt": "2026-08-06 09:00:00",
        "updatedAt": "2026-08-06 09:01:00",
    }]
    assert all(key.isascii() for key in redis.values)


def test_stream_generator_removes_subscriber_when_closed():
    repository = StrategyPickRepository(FakeRedis())
    baseline = repository.stream_subscriber_count()
    stream = repository.stream_events()
    assert next(stream).startswith('data: {"type": "ready"}')
    assert repository.stream_subscriber_count() == baseline + 1
    stream.close()
    assert repository.stream_subscriber_count() == baseline


def test_repository_owns_selected_state_and_global_event_v1_keys():
    redis = FakeRedis()
    repository = StrategyPickRepository(redis)
    repository.save_selected_state("eastmoney_1", ["600000"], {"600000": {"name": "浦发银行"}})
    repository.save_events("eastmoney_1", "20260806", [{"eventId": "evt-1"}])

    assert repository.selected_state("eastmoney_1") == {"codes": ["600000"], "stockInfo": {"600000": {"name": "浦发银行"}}}
    assert repository.global_events("20260806") == [{"eventId": "evt-1"}]
    assert all(key.isascii() for key in redis.values if key.startswith("strategy_pick:v1:"))
