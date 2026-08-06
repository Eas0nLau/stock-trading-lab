import json
import queue
import threading

from .legacy_adapter import LegacyStrategyPickReadAdapter, LegacyStrategyPickWriteAdapter


_subscribers = set()
_subscriber_lock = threading.Lock()


class StrategyPickRepository:
    def __init__(self, redis, legacy_reader=None, legacy_writer=None):
        self.redis = redis
        self.legacy_reader = legacy_reader or LegacyStrategyPickReadAdapter(redis)
        self.legacy_writer = legacy_writer or LegacyStrategyPickWriteAdapter(redis)

    @staticmethod
    def key(strategy_id, suffix): return f"strategy_pick:v1:{strategy_id}:{suffix}"
    @staticmethod
    def strategies_key(): return "strategy_pick:v1:strategies"
    @staticmethod
    def dates_key(strategy_id): return StrategyPickRepository.key(strategy_id, "dates")
    @staticmethod
    def global_dates_key(): return "strategy_pick:v1:dates"

    def strategies(self):
        value = self.redis.get(self.strategies_key())
        return _loads(value, self.legacy_reader.strategies())

    def save_strategies(self, strategies):
        self.redis.set(self.strategies_key(), json.dumps(strategies, ensure_ascii=False))
        self.legacy_writer.save_strategies(strategies)

    def latest(self, strategy_id):
        return _loads(self.redis.get(self.key(strategy_id, "latest")), self.legacy_reader.latest(strategy_id))

    def history(self, strategy_id, date):
        values = self.redis.lrange(self.key(strategy_id, f"history:{date}"), 0, -1)
        return [_loads(value, None) for value in values if _loads(value, None) is not None] or self.legacy_reader.history(strategy_id, date)

    def events(self, strategy_id, date):
        values = self.redis.lrange(self.key(strategy_id, f"events:{date}"), 0, -1)
        return [_loads(value, None) for value in values if _loads(value, None) is not None] or self.legacy_reader.events(strategy_id, date)

    def global_events(self, date):
        values = self.redis.lrange(f"strategy_pick:v1:events:{date}", 0, -1)
        return [_loads(value, None) for value in values if _loads(value, None) is not None] or self.legacy_reader.global_events(date)

    def dates(self, strategy_id=None):
        current = set()
        keys = [self.dates_key(strategy_id)] if strategy_id else [self.dates_key(item["id"]) for item in self.strategies()] + [self.global_dates_key()]
        for key in keys:
            current.update(_decode(value) for value in self.redis.smembers(key))
        return sorted(current | set(self.legacy_reader.dates(strategy_id)), reverse=True)

    def save_snapshot(self, strategy_id, snapshot, update_latest=False, write_legacy=True):
        date = snapshot.get("collectedDate")
        self.redis.rpush(self.key(strategy_id, f"history:{date}"), json.dumps(snapshot, ensure_ascii=False))
        self.redis.sadd(self.dates_key(strategy_id), date)
        if update_latest: self.redis.set(self.key(strategy_id, "latest"), json.dumps(snapshot, ensure_ascii=False))
        if write_legacy: self.legacy_writer.save_snapshot(strategy_id, snapshot, update_latest)

    def save_events(self, strategy_id, date, events, write_legacy=True):
        for event in events:
            self.redis.rpush(self.key(strategy_id, f"events:{date}"), json.dumps(event, ensure_ascii=False))
            self.redis.rpush(f"strategy_pick:v1:events:{date}", json.dumps(event, ensure_ascii=False))
        if events: self.redis.sadd(self.global_dates_key(), date)
        if events and write_legacy: self.legacy_writer.save_events(strategy_id, date, events)

    def save_selected_state(self, strategy_id, codes, stock_info, write_legacy=True):
        payload = {"codes": sorted(codes), "stockInfo": stock_info}
        self.redis.set(self.key(strategy_id, "selected_state"), json.dumps(payload, ensure_ascii=False))
        if write_legacy: self.legacy_writer.save_selected_state(strategy_id, codes, stock_info)

    def selected_state(self, strategy_id):
        return _loads(self.redis.get(self.key(strategy_id, "selected_state")), {"codes": [], "stockInfo": {}})

    def publish_snapshot(self, snapshot):
        event = {"type": "snapshot", "strategyId": snapshot.get("strategyId", ""), "strategyName": snapshot.get("strategyName", ""), "collectedDate": snapshot.get("collectedDate", ""), "collectedTime": snapshot.get("collectedTime", ""), "status": snapshot.get("status", ""), "stockCount": len(snapshot.get("stocks") or []), "addedCount": len(snapshot.get("addedStocks") or []), "addedStocks": snapshot.get("addedStocks") or [], "removedCount": len(snapshot.get("removedStocks") or []), "removedStocks": snapshot.get("removedStocks") or []}
        with _subscriber_lock: subscribers = list(_subscribers)
        for subscriber in subscribers:
            try: subscriber.put_nowait(event)
            except queue.Full:
                try: subscriber.get_nowait(); subscriber.put_nowait(event)
                except queue.Empty: pass

    def stream_events(self):
        subscriber = queue.Queue(maxsize=100)
        with _subscriber_lock: _subscribers.add(subscriber)
        try:
            yield 'data: {"type": "ready"}\n\n'
            while True:
                try: yield f"data: {json.dumps(subscriber.get(timeout=15), ensure_ascii=False)}\n\n"
                except queue.Empty: yield ": ping\n\n"
        finally:
            with _subscriber_lock: _subscribers.discard(subscriber)

    @staticmethod
    def stream_subscriber_count():
        with _subscriber_lock: return len(_subscribers)


def _decode(value): return value.decode() if isinstance(value, bytes) else value
def _loads(value, default):
    if not value: return default
    try: return json.loads(_decode(value)) if isinstance(value, (str, bytes)) else value
    except (TypeError, ValueError): return default
