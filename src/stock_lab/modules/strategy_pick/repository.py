import json
import queue
import threading
from datetime import date


_subscribers = set()
_subscriber_lock = threading.Lock()


class StrategyPickRepository:
    def __init__(self, redis, mysql_repository=None, *, cache_ttl_seconds=86400):
        self.redis = redis
        self.mysql_repository = mysql_repository
        self.cache_ttl_seconds = int(cache_ttl_seconds)

    @staticmethod
    def key(strategy_id, suffix): return f"strategy_pick:v1:{strategy_id}:{suffix}"
    @staticmethod
    def strategies_key(): return "strategy_pick:v1:strategies"
    @staticmethod
    def dates_key(strategy_id): return StrategyPickRepository.key(strategy_id, "dates")
    @staticmethod
    def global_dates_key(): return "strategy_pick:v1:dates"

    def strategies(self):
        if self.mysql_repository is not None:
            return self.mysql_repository.strategies()
        value = self.redis.get(self.strategies_key())
        return _loads(value, [])

    def save_strategies(self, strategies):
        if self.mysql_repository is not None:
            self.mysql_repository.save_strategies(strategies)
            return
        self.redis.set(self.strategies_key(), json.dumps(strategies, ensure_ascii=False))

    def latest(self, strategy_id):
        if self.mysql_repository is not None:
            snapshot = self.mysql_repository.latest(strategy_id)
            self._cache_snapshot(strategy_id, snapshot)
            return snapshot
        return _loads(self.redis.get(self.key(strategy_id, "latest")), {})

    def history(self, strategy_id, date):
        if self.mysql_repository is not None:
            snapshots = self.mysql_repository.history(strategy_id, date)
            if _is_today(date):
                self._set_cache(self.key(strategy_id, f"history:{date}"), snapshots)
            return snapshots
        values = self.redis.lrange(self.key(strategy_id, f"history:{date}"), 0, -1)
        return [_loads(value, None) for value in values if _loads(value, None) is not None]

    def events(self, strategy_id, date):
        if self.mysql_repository is not None:
            events = self.mysql_repository.events(strategy_id, date)
            if _is_today(date):
                self._set_cache(self.key(strategy_id, f"events:{date}"), events)
            return events
        values = self.redis.lrange(self.key(strategy_id, f"events:{date}"), 0, -1)
        return [_loads(value, None) for value in values if _loads(value, None) is not None]

    def global_events(self, date):
        if self.mysql_repository is not None:
            events = self.mysql_repository.global_events(date)
            if _is_today(date):
                self._set_cache(f"strategy_pick:v1:events:{date}", events)
            return events
        values = self.redis.lrange(f"strategy_pick:v1:events:{date}", 0, -1)
        return [_loads(value, None) for value in values if _loads(value, None) is not None]

    def dates(self, strategy_id=None):
        if self.mysql_repository is not None:
            return self.mysql_repository.dates(strategy_id)
        current = set()
        keys = [self.dates_key(strategy_id)] if strategy_id else [self.dates_key(item["id"]) for item in self.strategies()] + [self.global_dates_key()]
        for key in keys:
            current.update(_decode(value) for value in self.redis.smembers(key))
        return sorted(current, reverse=True)

    def save_snapshot(self, strategy_id, snapshot, update_latest=False):
        if self.mysql_repository is not None:
            snapshot = {**snapshot, "strategyId": strategy_id}
            self.mysql_repository.save_collection(snapshot, [])
            self._cache_snapshot(strategy_id, snapshot, update_latest=update_latest)
            return
        date = snapshot.get("collectedDate")
        self.redis.rpush(self.key(strategy_id, f"history:{date}"), json.dumps(snapshot, ensure_ascii=False))
        self.redis.sadd(self.dates_key(strategy_id), date)
        if update_latest: self.redis.set(self.key(strategy_id, "latest"), json.dumps(snapshot, ensure_ascii=False))

    def save_events(self, strategy_id, date, events):
        if self.mysql_repository is not None:
            snapshot = self.mysql_repository.latest(strategy_id)
            self.mysql_repository.save_collection({
                **snapshot,
                "strategyId": strategy_id,
                "collectedDate": date,
                "collectedTime": snapshot.get("collectedTime") or "00:00:00",
            }, events)
            self._cache_events(strategy_id, date, events)
            return
        for event in events:
            self.redis.rpush(self.key(strategy_id, f"events:{date}"), json.dumps(event, ensure_ascii=False))
            self.redis.rpush(f"strategy_pick:v1:events:{date}", json.dumps(event, ensure_ascii=False))
        if events: self.redis.sadd(self.global_dates_key(), date)

    def save_selected_state(self, strategy_id, codes, stock_info):
        payload = {"codes": sorted(codes), "stockInfo": stock_info}
        if self.mysql_repository is not None:
            if _is_today(date.today().strftime("%Y%m%d")):
                self._set_cache(self.key(strategy_id, "selected_state"), payload)
            return
        self.redis.set(self.key(strategy_id, "selected_state"), json.dumps(payload, ensure_ascii=False))

    def selected_state(self, strategy_id):
        if self.mysql_repository is not None:
            snapshot = self.mysql_repository.latest(strategy_id)
            stocks = snapshot.get("stocks") or []
            return {"codes": sorted(stock.get("code") for stock in stocks if stock.get("code")), "stockInfo": {stock.get("code"): stock for stock in stocks if stock.get("code")}}
        return _loads(self.redis.get(self.key(strategy_id, "selected_state")), {"codes": [], "stockInfo": {}})

    def save_collection(self, snapshot, events):
        if self.mysql_repository is None:
            strategy_id = snapshot.get("strategyId", "")
            date_value = snapshot.get("collectedDate")
            self.save_snapshot(strategy_id, snapshot, update_latest=snapshot.get("status") == "success")
            self.save_events(strategy_id, date_value, events)
            return None
        snapshot_id = self.mysql_repository.save_collection(snapshot, events)
        self._cache_snapshot(snapshot.get("strategyId", ""), snapshot, update_latest=snapshot.get("status") == "success")
        if _is_today(snapshot.get("collectedDate")):
            self._cache_events(snapshot.get("strategyId", ""), snapshot.get("collectedDate"), events)
        return snapshot_id

    def _cache_snapshot(self, strategy_id, snapshot, update_latest=True):
        date_value = snapshot.get("collectedDate") if isinstance(snapshot, dict) else None
        if not _is_today(date_value):
            return
        if update_latest:
            self._set_cache(self.key(strategy_id, "latest"), snapshot)
        self._set_cache(self.key(strategy_id, f"history:{date_value}"), [snapshot])
        self.redis.sadd(self.dates_key(strategy_id), date_value)
        self.redis.sadd(self.global_dates_key(), date_value)

    def _cache_events(self, strategy_id, date_value, events):
        if not _is_today(date_value):
            return
        self._set_cache(self.key(strategy_id, f"events:{date_value}"), events)
        self._set_cache(f"strategy_pick:v1:events:{date_value}", events)
        self.redis.sadd(self.global_dates_key(), date_value)

    def _set_cache(self, key, value):
        self.redis.set(key, json.dumps(value, ensure_ascii=False), ex=self.cache_ttl_seconds)

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


def _is_today(value):
    return str(value or "") == date.today().strftime("%Y%m%d")
