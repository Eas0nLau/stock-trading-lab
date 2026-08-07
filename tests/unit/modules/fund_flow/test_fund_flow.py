import json

import pytest

from stock_lab.modules.fund_flow.contracts import translate_legacy_fund_flow
from stock_lab.modules.fund_flow.repository import FundFlowRepository
from stock_lab.modules.fund_flow.service import FundFlowService


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.sets = {}
        self.lists = {}
        self.publish_calls = []
        self.get_calls = []

    def set(self, key, value): self.values[key] = value
    def get(self, key): self.get_calls.append(key); return self.values.get(key)
    def sadd(self, key, *values): self.sets.setdefault(key, set()).update(values)
    def smembers(self, key): return self.sets.get(key, set())
    def delete(self, *keys):
        for key in keys:
            self.values.pop(key, None)
            self.sets.pop(key, None)
    def lrange(self, key, start, end): return self.lists.get(key, [])
    def keys(self, pattern):
        prefix = pattern.removesuffix("*")
        return [key for key in self.lists if key.startswith(prefix)]
    def publish(self, channel, payload): self.publish_calls.append((channel, payload))


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


def test_repository_replaces_same_time_snapshot_without_duplicate():
    redis = FakeRedis()
    repository = FundFlowRepository(redis)
    repository.save_history("industry", "20260806", [{"time": "10:00:00", "board_name": "旧"}])
    repository.save_history("industry", "20260806", [{"time": "10:00:00", "board_name": "新"}])
    repository.save_history("industry", "20260806", [{"time": "10:01:00", "board_name": "后续"}])

    assert repository.history("industry", "20260806") == [
        [{"time": "10:00:00", "board_name": "新"}],
        [{"time": "10:01:00", "board_name": "后续"}],
    ]


def test_service_filters_top_inflow_and_outflow_and_replaces_duplicate_times():
    redis = FakeRedis()
    repository = FundFlowRepository(redis)
    repository.save_history("industry", "20260806", [
        {"time": "10:00", "board_name": "old", "net_inflow_100m": 99},
    ])
    repository.save_history("industry", "20260806", [
        {"time": "10:00", "board_name": "inflow", "board_code": "A", "net_inflow_100m": 5, "leader": "甲"},
        {"time": "10:00", "board_name": "second", "net_inflow_100m": 3},
        {"time": "10:00", "board_name": "outflow", "board_code": "B", "net_inflow_100m": -6, "leader": "乙"},
        {"time": "10:00", "board_name": "less-negative", "net_inflow_100m": -2},
        {"time": "10:00", "board_name": "zero", "net_inflow_100m": 0},
    ])

    result = FundFlowService(repository, default_top_n=1).history("industry", "20260806")

    assert result == {
        "format": "matrix-v2",
        "top_n": 1,
        "times": ["10:00"],
        "boards": [
            {"code": "A", "name": "inflow", "points": [[0, 5, "甲"]]},
            {"code": "B", "name": "outflow", "points": [[0, -6, "乙"]]},
        ],
    }


def test_service_shapes_unfiltered_history_as_sparse_matrix_v1():
    redis = FakeRedis()
    repository = FundFlowRepository(redis)
    repository.save_history("industry", "20260806", [
        {"time": "10:00", "board_name": "A", "net_inflow_100m": 1, "leader": "甲"},
    ])
    repository.save_history("industry", "20260806", [
        {"time": "10:01", "board_name": "B", "net_inflow_100m": 2, "leader": "乙"},
    ])

    result = FundFlowService(repository).history("industry", "20260806", top_n=0)

    assert result == {
        "format": "matrix-v1",
        "top_n": 0,
        "times": ["10:00", "10:01"],
        "boards": [
            {"code": "", "name": "A", "values": [1, None], "leaders": ["甲", ""]},
            {"code": "", "name": "B", "values": [None, 2], "leaders": ["", "乙"]},
        ],
    }


def test_chart_cache_recovers_from_invalid_json_and_is_invalidated_on_save():
    redis = FakeRedis()
    repository = FundFlowRepository(redis)
    repository.save_history("industry", "20260806", [
        {"time": "10:00", "board_name": "A", "net_inflow_100m": 1},
    ])
    service = FundFlowService(repository, default_top_n=1)
    expected = service.history("industry", "20260806")
    cache_key = repository.chart_cache_key("industry", "20260806", 1)
    assert json.loads(redis.values[cache_key]) == expected

    redis.values[cache_key] = "not-json"
    assert service.history("industry", "20260806") == expected
    assert json.loads(redis.values[cache_key]) == expected

    repository.save_history("industry", "20260806", [
        {"time": "10:01", "board_name": "B", "net_inflow_100m": 2},
    ])
    assert cache_key not in redis.values


def test_repository_does_not_fall_back_to_legacy_industry_history():
    redis = FakeRedis()
    redis.lists["old-industry-history"] = ["retired"]

    repository = FundFlowRepository(redis)

    assert repository.history("industry", "20260805") is None
    assert repository.dates("industry") == []


def test_service_falls_back_to_mysql_and_repopulates_redis():
    redis = FakeRedis()
    repository = FundFlowRepository(redis)

    class MySQL:
        def history(self, flow_type, trade_date):
            return [[{"time": "10:00", "board_name": "A", "net_inflow_100m": 1}]]

    result = FundFlowService(repository, MySQL()).history("industry", "20260806", top_n=0)

    assert result["times"] == ["10:00"]
    assert repository.history("industry", "20260806") is not None


def test_repository_does_not_scan_keys_for_missing_concept_history():
    redis = FakeRedis()
    redis.keys = lambda _pattern: (_ for _ in ()).throw(AssertionError("key scan is forbidden"))

    repository = FundFlowRepository(redis)

    assert repository.history("concept", "20260804") is None
    assert repository.dates("concept") == []


def test_stream_generator_removes_subscriber_when_closed():
    redis = FakeRedis()
    repository = FundFlowRepository(redis)
    baseline = repository.stream_subscriber_count()
    events = repository.stream_events()

    next(events)
    assert repository.stream_subscriber_count() == baseline + 1
    events.close()

    assert repository.stream_subscriber_count() == baseline


def test_snapshot_delivery_uses_only_the_in_process_broker():
    redis = FakeRedis()
    repository = FundFlowRepository(redis)
    events = repository.stream_events()
    next(events)

    repository.publish_snapshot("industry", "20260806", "10:00:00", 1)

    assert '"type": "snapshot"' in next(events)
    assert redis.publish_calls == []
    events.close()


def test_snapshot_delivery_reaches_multiple_subscribers():
    repository = FundFlowRepository(FakeRedis())
    baseline = repository.stream_subscriber_count()
    first = repository.stream_events()
    second = repository.stream_events()
    next(first)
    next(second)

    repository.publish_snapshot("concept", "20260806", "10:02:00", 2)

    assert '"flow_type": "concept"' in next(first)
    assert '"flow_type": "concept"' in next(second)
    first.close()
    second.close()
    assert repository.stream_subscriber_count() == baseline


def test_stream_removes_subscriber_when_event_encoding_raises():
    repository = FundFlowRepository(FakeRedis())
    baseline = repository.stream_subscriber_count()
    events = repository.stream_events()
    next(events)
    repository.publish_snapshot("industry", "20260806", object(), 1)

    with pytest.raises(TypeError):
        next(events)

    assert repository.stream_subscriber_count() == baseline
