import pytest

from stock_lab.infrastructure.cache.locks import RedisJobLock


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.set_calls = []

    def set(self, key, value, *, nx=False, ex=None):
        self.set_calls.append((key, value, nx, ex))
        if nx and key in self.values:
            return False
        self.values[key] = value
        return True

    def get(self, key):
        return self.values.get(key)

    def delete(self, key):
        return int(self.values.pop(key, None) is not None)

    def eval(self, _script, key_count, key, token):
        assert key_count == 1
        if self.values.get(key) != token:
            return 0
        return self.delete(key)


def test_lock_acquires_with_token_and_expiry():
    redis = FakeRedis()
    lock = RedisJobLock(redis, "job:lock", 30, token_factory=lambda: "owner-1")

    assert lock.acquire() is True
    assert redis.set_calls == [("job:lock", "owner-1", True, 30)]


def test_lock_reports_contention_without_replacing_owner():
    redis = FakeRedis()
    redis.values["job:lock"] = "owner-1"
    lock = RedisJobLock(redis, "job:lock", 30, token_factory=lambda: "owner-2")

    assert lock.acquire() is False
    assert redis.values["job:lock"] == "owner-1"


def test_release_deletes_only_the_callers_token():
    redis = FakeRedis()
    owned = RedisJobLock(redis, "job:lock", 30, token_factory=lambda: "owner-1")
    assert owned.acquire() is True
    assert owned.release() is True
    assert "job:lock" not in redis.values

    foreign = RedisJobLock(redis, "job:lock", 30, token_factory=lambda: "owner-2")
    assert foreign.acquire() is True
    redis.values["job:lock"] = "owner-3"
    assert foreign.release() is False
    assert redis.values["job:lock"] == "owner-3"


def test_lock_requires_positive_expiry():
    with pytest.raises(ValueError, match="positive"):
        RedisJobLock(FakeRedis(), "job:lock", 0)


def test_context_releases_lock_after_body_failure():
    redis = FakeRedis()
    lock = RedisJobLock(redis, "job:lock", 30, token_factory=lambda: "owner-1")

    with pytest.raises(RuntimeError, match="failed"):
        with lock as acquired:
            assert acquired is lock
            raise RuntimeError("failed")

    assert "job:lock" not in redis.values


def test_context_rejects_contended_lock():
    redis = FakeRedis()
    redis.values["job:lock"] = "owner-1"

    with pytest.raises(RuntimeError, match="already running"):
        with RedisJobLock(redis, "job:lock", 30, token_factory=lambda: "owner-2"):
            raise AssertionError("body must not run")
