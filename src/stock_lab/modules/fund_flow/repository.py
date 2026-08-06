import json
import queue
import threading


_subscribers = set()
_subscriber_lock = threading.Lock()


class FundFlowRepository:
    def __init__(self, redis):
        self.redis = redis

    @staticmethod
    def history_key(flow_type, trade_date):
        return f"fund_flow:v1:{flow_type}:history:{trade_date}"

    @staticmethod
    def dates_key(flow_type):
        return f"fund_flow:v1:{flow_type}:dates"

    def save_history(self, flow_type, trade_date, payload):
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
        self.redis.set(key, json.dumps(payload, ensure_ascii=False))
        self.redis.sadd(self.dates_key(flow_type), trade_date)

    def history(self, flow_type, trade_date):
        value = self.redis.get(self.history_key(flow_type, trade_date))
        return json.loads(value) if value else None

    def dates(self, flow_type):
        return sorted(self.redis.smembers(self.dates_key(flow_type)))

    def publish_snapshot(self, flow_type, trade_date, collected_at, record_count):
        event = {
            "type": "snapshot",
            "flow_type": flow_type,
            "trade_date": trade_date,
            "collected_at": collected_at,
            "record_count": record_count,
        }
        encoded = json.dumps(event, ensure_ascii=False)
        publish = getattr(self.redis, "publish", None)
        if publish:
            publish("fund_flow:v1:stream", encoded)
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
