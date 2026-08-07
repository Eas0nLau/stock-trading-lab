from stock_lab.modules.strategy_pick.collector import StrategyPickCollector
from stock_lab.modules.strategy_pick.repository import StrategyPickRepository


class Redis:
    def __init__(self):
        self.values = {}
        self.lists = {}
        self.sets = {}
        self.expirations = {}

    def get(self, key): return self.values.get(key)
    def set(self, key, value, ex=None):
        self.values[key] = value
        self.expirations[key] = ex
    def rpush(self, key, value): self.lists.setdefault(key, []).append(value)
    def lrange(self, key, start, end): return self.lists.get(key, [])[start:(None if end == -1 else end + 1)]
    def sadd(self, key, *values): self.sets.setdefault(key, set()).update(values)
    def smembers(self, key): return self.sets.get(key, set())
    def expire(self, key, seconds): self.expirations[key] = seconds


class MySQL:
    def __init__(self, *, failure=None):
        self.failure = failure
        self.saved = []
        self._strategies = [{"id": "eastmoney_1", "name": "MySQL", "pageUrl": "https://db"}]

    def strategies(self): return self._strategies
    def save_strategies(self, strategies): self._strategies = strategies
    def latest(self, strategy_id):
        if self.failure == "latest": raise RuntimeError("mysql unavailable")
        return {"strategyId": strategy_id, "collectedDate": "20260807", "stocks": []}
    def history(self, strategy_id, date): return [{"strategyId": strategy_id, "collectedDate": date, "stocks": []}]
    def dates(self, strategy_id=None): return ["20260807"]
    def events(self, strategy_id, date): return [{"eventId": "db-event", "strategyId": strategy_id}]
    def global_events(self, date): return [{"eventId": "db-event"}]
    def save_collection(self, snapshot, events):
        if self.failure == "save": raise RuntimeError("mysql write failed")
        self.saved.append((snapshot, events))


def test_mysql_is_authoritative_and_cache_miss_is_backfilled_with_same_day_ttl():
    redis = Redis()
    repository = StrategyPickRepository(redis, MySQL(), cache_ttl_seconds=3600)

    result = repository.latest("eastmoney_1")

    assert result["strategyId"] == "eastmoney_1"
    assert redis.values["strategy_pick:v1:eastmoney_1:latest"]
    assert redis.expirations["strategy_pick:v1:eastmoney_1:latest"] == 3600
    assert redis.expirations["strategy_pick:v1:eastmoney_1:dates"] == 3600
    assert redis.expirations["strategy_pick:v1:dates"] == 3600


def test_mysql_reads_ignore_stale_redis_values():
    redis = Redis()
    redis.values["strategy_pick:v1:eastmoney_1:latest"] = '{"status":"stale"}'
    repository = StrategyPickRepository(redis, MySQL())

    assert repository.latest("eastmoney_1")["collectedDate"] == "20260807"


def test_mysql_write_failure_does_not_touch_cache_or_publish_success():
    redis = Redis()
    mysql = MySQL(failure="save")
    repository = StrategyPickRepository(redis, mysql)
    collector = StrategyPickCollector(repository, adapter=None)
    collector.adapter = type("Adapter", (), {
        "collect": lambda _self, strategy_id: {
            "strategyId": strategy_id,
            "collectedDate": "20260807",
            "collectedTime": "10:00:00",
            "status": "success",
            "stocks": [],
            "addedStocks": [],
            "removedStocks": [],
        }
    })()

    try:
        collector.refresh("eastmoney_1")
    except RuntimeError as error:
        assert str(error) == "mysql write failed"
    else:
        raise AssertionError("collector unexpectedly published a failed MySQL write")

    assert redis.values == {}
    assert redis.lists == {}
