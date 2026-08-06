import json


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
            snapshots.append(payload)
            payload = snapshots
        self.redis.set(key, json.dumps(payload, ensure_ascii=False))
        self.redis.sadd(self.dates_key(flow_type), trade_date)

    def history(self, flow_type, trade_date):
        value = self.redis.get(self.history_key(flow_type, trade_date))
        return json.loads(value) if value else None

    def dates(self, flow_type):
        return sorted(self.redis.smembers(self.dates_key(flow_type)))
