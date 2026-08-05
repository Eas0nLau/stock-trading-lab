from task import 每日更新 as daily


class RedisState:
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


def test_repeating_one_day_pipeline_is_idempotent(monkeypatch):
    redis = RedisState()
    calls = []
    monkeypatch.setattr(daily.db, "redis_con_localhost", redis)
    monkeypatch.setattr(daily, "交易日期列表", lambda limit=160: [20260804, 20260805])
    for name in ("更新股票基础信息", "更新股票日线", "更新指数日线", "韭研公社异动采集", "落库热门板块情绪", "落库指数周期"):
        monkeypatch.setattr(daily, name, lambda *args, _name=name, **kwargs: calls.append(_name) or 1)

    first = daily.tasks(20260805)
    second = daily.tasks(20260805)

    assert first["状态"] == "success"
    assert second["状态"] == "skipped"
    assert calls.count("落库指数周期") == 1
