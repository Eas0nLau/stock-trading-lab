import json

import pytest

from stock_lab.modules.dragon_tiger.jobs import DragonTigerCollectionJobManager


class FakeRedis:
    def __init__(self):
        self.values = {}

    def set(self, key, value, nx=False, ex=None):
        if nx and key in self.values:
            return False
        self.values[key] = value
        return True

    def get(self, key):
        return self.values.get(key)

    def delete(self, key):
        self.values.pop(key, None)

    def eval(self, _script, _keys, key, token):
        if self.values.get(key) == token:
            self.values.pop(key, None)
            return 1
        return 0


class ImmediateExecutor:
    def submit(self, function, *args):
        function(*args)


class FailingExecutor:
    def submit(self, *_args):
        raise RuntimeError("executor closed")


def test_collection_job_runs_all_stages_and_persists_result():
    redis = FakeRedis()
    stages = []

    def stage(name):
        def run(*_dates):
            stages.append(name)
            return {"selectedCodes": ["000001.SZ"]} if name == "analysis" else {"rows": 1}
        return run

    manager = DragonTigerCollectionJobManager(
        redis,
        run_listings=stage("listings"),
        run_broker_directory=stage("broker_directory"),
        run_broker_history=stage("broker_history"),
        run_analysis=stage("analysis"),
        executor=ImmediateExecutor(),
    )

    created = manager.start(20260404, 20260806)
    state = manager.get(created["jobId"])

    assert stages == ["listings", "broker_directory", "broker_history", "analysis"]
    assert state["status"] == "succeeded"
    assert state["selectedCodes"] == ["000001.SZ"]
    assert state["sourceTables"] == ["dragon_tiger", "broker_listing_history", "daily_quotes"]


def test_collection_job_rejects_a_second_active_job():
    redis = FakeRedis()
    redis.set("stock_lab:dragon_tiger:active", "existing", nx=True)
    manager = DragonTigerCollectionJobManager(
        redis,
        run_listings=lambda *_dates: None,
        run_broker_directory=lambda *_dates: None,
        run_broker_history=lambda *_dates: None,
        run_analysis=lambda *_dates: {"selectedCodes": []},
        executor=ImmediateExecutor(),
    )

    with pytest.raises(RuntimeError, match="active"):
        manager.start(20260404, 20260806)


def test_collection_job_records_a_failed_stage_without_leaking_exception():
    redis = FakeRedis()

    def fail(*_dates):
        raise RuntimeError("source unavailable")

    manager = DragonTigerCollectionJobManager(
        redis,
        run_listings=fail,
        run_broker_directory=lambda: None,
        run_broker_history=lambda: None,
        run_analysis=lambda: {"selectedCodes": []},
        executor=ImmediateExecutor(),
    )

    created = manager.start(20260404, 20260806)
    state = manager.get(created["jobId"])

    assert state["status"] == "failed"
    assert state["stage"] == "listings"
    assert state["error"] == "source unavailable"


def test_collection_job_releases_lock_when_submission_fails():
    redis = FakeRedis()
    manager = DragonTigerCollectionJobManager(
        redis,
        run_listings=lambda *_dates: None,
        run_broker_directory=lambda *_dates: None,
        run_broker_history=lambda *_dates: None,
        run_analysis=lambda *_dates: {"selectedCodes": []},
        executor=FailingExecutor(),
    )

    with pytest.raises(RuntimeError, match="executor closed"):
        manager.start(20260404, 20260806)

    assert redis.get("stock_lab:dragon_tiger:active") is None
