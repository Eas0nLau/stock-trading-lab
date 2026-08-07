import json
import queue
import threading
from datetime import date


# The API and collector run as threads in one application process, so one broker owns all subscribers.
_subscribers = set()
_subscriber_lock = threading.Lock()


class FundFlowRepository:
    def __init__(self, redis, *, cache_ttl_seconds=86400):
        self.redis = redis
        self.cache_ttl_seconds = int(cache_ttl_seconds)

    @staticmethod
    def history_key(flow_type, trade_date):
        return f"fund_flow:v1:{flow_type}:history:{trade_date}"

    @staticmethod
    def dates_key(flow_type):
        return f"fund_flow:v1:{flow_type}:dates"

    @staticmethod
    def chart_cache_key(flow_type, trade_date, top_n):
        return f"fund_flow:v1:{flow_type}:chart:{trade_date}:top:{int(top_n)}"

    @staticmethod
    def chart_cache_index_key(flow_type, trade_date):
        return f"fund_flow:v1:{flow_type}:chart-index:{trade_date}"

    @staticmethod
    def canonical_history_key(flow_type, trade_date):
        return f"fund_flow:v1:{flow_type}:canonical:{trade_date}"

    def save_history(self, flow_type, trade_date, payload, *, cache=True):
        if not cache:
            return
        key = self.history_key(flow_type, trade_date)
        existing = self.history(flow_type, trade_date)
        if isinstance(payload, list):
            snapshots = existing if isinstance(existing, list) else []
            snapshot_time = next((item.get("time") for item in payload if item.get("time")), "")
            previous_time = next((item.get("time") for item in snapshots[-1] if item.get("time")), "") if snapshots else ""
            if snapshot_time and snapshot_time == previous_time:
                snapshots[-1] = payload
            else:
                snapshots.append(payload)
            payload = snapshots
        self._set(key, payload)
        self.redis.sadd(self.dates_key(flow_type), trade_date)
        if _is_today(trade_date):
            self._set(self.canonical_history_key(flow_type, trade_date), "1")
            self._expire(self.dates_key(flow_type))
        self.clear_chart_cache(flow_type, trade_date)

    def replace_history(self, flow_type, trade_date, snapshots, *, cache=True):
        if not cache:
            return
        self._set(self.history_key(flow_type, trade_date), snapshots)
        self.redis.sadd(self.dates_key(flow_type), trade_date)
        if _is_today(trade_date):
            self._set(self.canonical_history_key(flow_type, trade_date), "1")
            self._expire(self.dates_key(flow_type))
        self.clear_chart_cache(flow_type, trade_date)

    def is_canonical_history(self, flow_type, trade_date):
        return bool(self.redis.get(self.canonical_history_key(flow_type, trade_date)))

    def history(self, flow_type, trade_date):
        value = self.redis.get(self.history_key(flow_type, trade_date))
        if value:
            return json.loads(value)
        return None

    def dates(self, flow_type):
        current = {
            value.decode() if isinstance(value, bytes) else value
            for value in self.redis.smembers(self.dates_key(flow_type))
        }
        return sorted(current)

    def cached_chart(self, flow_type, trade_date, top_n):
        key = self.chart_cache_key(flow_type, trade_date, top_n)
        value = self.redis.get(key)
        if not value:
            return None
        try:
            return json.loads(value)
        except (TypeError, ValueError, json.JSONDecodeError):
            self.redis.delete(key)
            return None

    def save_chart(self, flow_type, trade_date, top_n, payload):
        key = self.chart_cache_key(flow_type, trade_date, top_n)
        self._set(key, payload, compact=True)
        self.redis.sadd(self.chart_cache_index_key(flow_type, trade_date), key)
        if _is_today(trade_date):
            self._expire(self.chart_cache_index_key(flow_type, trade_date))

    def clear_chart_cache(self, flow_type, trade_date):
        index_key = self.chart_cache_index_key(flow_type, trade_date)
        keys = [value.decode() if isinstance(value, bytes) else value for value in self.redis.smembers(index_key)]
        if keys:
            self.redis.delete(*keys)
        self.redis.delete(index_key)

    def publish_snapshot(self, flow_type, trade_date, collected_at, record_count):
        event = {
            "type": "snapshot",
            "flow_type": flow_type,
            "trade_date": trade_date,
            "collected_at": collected_at,
            "record_count": record_count,
        }
        with _subscriber_lock:
            subscribers = list(_subscribers)
        for subscriber in subscribers:
            try:
                subscriber.put_nowait(event)
            except queue.Full:
                try:
                    subscriber.get_nowait()
                    subscriber.put_nowait(event)
                except queue.Empty:
                    pass

    @staticmethod
    def stream_events():
        subscriber = queue.Queue(maxsize=100)
        with _subscriber_lock:
            _subscribers.add(subscriber)
        try:
            yield 'data: {"type": "ready"}\n\n'
            while True:
                try:
                    event = subscriber.get(timeout=15)
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                except queue.Empty:
                    yield ": ping\n\n"
        finally:
            with _subscriber_lock:
                _subscribers.discard(subscriber)

    @staticmethod
    def stream_subscriber_count():
        with _subscriber_lock:
            return len(_subscribers)

    def _set(self, key, payload, *, compact=False):
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":") if compact else None)
        try:
            self.redis.set(key, encoded, ex=self.cache_ttl_seconds if _is_current_cache_key(key) else None)
        except TypeError:
            self.redis.set(key, encoded)

    def _expire(self, key):
        expire = getattr(self.redis, "expire", None)
        if callable(expire):
            expire(key, self.cache_ttl_seconds)


def _is_today(value):
    return str(value or "") == date.today().strftime("%Y%m%d")


def _is_current_cache_key(key):
    return date.today().strftime("%Y%m%d") in str(key)
