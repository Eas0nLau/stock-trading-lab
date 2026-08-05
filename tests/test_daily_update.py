import pytest

from task import 每日更新 as daily


class FakeRedis:
    def __init__(self):
        self.values = {}

    def exists(self, key):
        return key in self.values

    def get(self, key):
        return self.values.get(key)

    def set(self, key, value, nx=False, ex=None):
        if nx and key in self.values:
            return False
        self.values[key] = value
        return True

    def delete(self, key):
        self.values.pop(key, None)


def test_tasks_runs_sources_before_analysis(monkeypatch):
    calls = []
    fake_redis = FakeRedis()
    monkeypatch.setattr(daily.db, "redis_con_localhost", fake_redis)
    monkeypatch.setattr(daily, "交易日期列表", lambda limit=160: [20260804, 20260805])
    monkeypatch.setattr(daily, "更新股票基础信息", lambda: calls.append("basic") or 1)
    monkeypatch.setattr(daily, "更新股票日线", lambda start, end: calls.append("daily") or 2)
    monkeypatch.setattr(daily, "更新指数日线", lambda start, end: calls.append("index") or 1)
    monkeypatch.setattr(daily, "韭研公社异动采集", lambda date: calls.append("jiuyan") or 3)
    monkeypatch.setattr(daily, "落库热门板块情绪", lambda date, source: calls.append("hot") or 4)
    monkeypatch.setattr(daily, "落库指数周期", lambda date: calls.append("index_emotion") or 1)

    result = daily.tasks(20260805)

    assert calls == ["basic", "daily", "index", "jiuyan", "hot", "index_emotion"]
    assert result["状态"] == "success"
    assert fake_redis.exists("每日更新.py:20260805")


def test_failed_source_does_not_set_completion_key(monkeypatch):
    fake_redis = FakeRedis()
    monkeypatch.setattr(daily.db, "redis_con_localhost", fake_redis)
    monkeypatch.setattr(daily, "交易日期列表", lambda limit=160: [20260804, 20260805])
    monkeypatch.setattr(
        daily,
        "更新股票基础信息",
        lambda: (_ for _ in ()).throw(RuntimeError("source down")),
    )

    with pytest.raises(RuntimeError):
        daily.tasks(20260805)

    assert not fake_redis.exists("每日更新.py:20260805")


def test_tasks_seeds_index_dates_before_resolving_empty_database(monkeypatch):
    calls = []
    fake_redis = FakeRedis()
    monkeypatch.setattr(daily.db, "redis_con_localhost", fake_redis)
    dates = iter([[], [20260804, 20260805]])
    monkeypatch.setattr(daily, "交易日期列表", lambda limit=160: next(dates))
    monkeypatch.setattr(daily, "更新指数日线", lambda start, end: calls.append("seed_index") or 2)
    monkeypatch.setattr(daily, "更新股票基础信息", lambda: calls.append("basic") or 1)
    monkeypatch.setattr(daily, "更新股票日线", lambda start, end: calls.append("daily") or 2)
    monkeypatch.setattr(daily, "韭研公社异动采集", lambda date: calls.append("jiuyan") or 3)
    monkeypatch.setattr(daily, "落库热门板块情绪", lambda date, source: calls.append("hot") or 4)
    monkeypatch.setattr(daily, "落库指数周期", lambda date: calls.append("index_emotion") or 1)

    result = daily.tasks(20260805)

    assert result["状态"] == "success"
    assert calls[0] == "seed_index"
