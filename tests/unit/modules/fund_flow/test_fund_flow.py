import json

from stock_lab.modules.fund_flow.contracts import translate_legacy_fund_flow
from stock_lab.modules.fund_flow.repository import FundFlowRepository


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.sets = {}

    def set(self, key, value): self.values[key] = value
    def get(self, key): return self.values.get(key)
    def sadd(self, key, value): self.sets.setdefault(key, set()).add(value)
    def smembers(self, key): return self.sets.get(key, set())


def test_translates_legacy_snapshot_fields():
    result = translate_legacy_fund_flow({"类型": "snapshot", "采集日期": "20260806", "记录数量": 2, "板块名称": "机器人", "资金净流入(亿)": 12.3, "龙头": "甲"})
    assert result == {"type": "snapshot", "trade_date": "20260806", "record_count": 2, "board_name": "机器人", "net_inflow_100m": 12.3, "leader": "甲"}


def test_repository_uses_v1_keys_and_round_trips_history():
    redis = FakeRedis()
    repository = FundFlowRepository(redis)
    repository.save_history("industry", "20260806", {"format": "matrix-v2", "boards": []})
    assert repository.history("industry", "20260806")["format"] == "matrix-v2"
    assert repository.dates("industry") == ["20260806"]
    assert all(key.isascii() for key in [*redis.values, *redis.sets])
