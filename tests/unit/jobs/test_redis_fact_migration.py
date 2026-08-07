import json

import pytest

from stock_lab.jobs.redis_fact_migration import cleanup_redis, migrate_strategy_pick, run_migration, verify_fund_flow_parity


class Redis:
    def __init__(self, values=None, lists=None, ttls=None):
        self.values = values or {}
        self.lists = lists or {}
        self.ttls = ttls or {}
        self.deleted = []

    def keys(self, pattern):
        prefix = pattern.removesuffix("*")
        return [key for key in [*self.values, *self.lists] if key.startswith(prefix)]

    def get(self, key): return self.values.get(key)
    def lrange(self, key, start, end): return self.lists.get(key, [])
    def ttl(self, key): return self.ttls.get(key, 3600)
    def delete(self, *keys):
        self.deleted.extend(keys)
        for key in keys:
            self.values.pop(key, None)
            self.lists.pop(key, None)


class MySQL:
    def __init__(self): self.definitions = []; self.collections = []
    def save_strategies(self, strategies): self.definitions.extend(strategies)
    def save_collection(self, snapshot, events): self.collections.append((snapshot, events))
    def history(self, flow_type, trade_date): return [[{"board_code": "A", "net_inflow_100m": 1.25, "time": "15:00:00"}]]
    def inventory(self):
        return {
            "strategies": len(self.definitions),
            "snapshots": len(self.collections),
            "stocks": sum(len(snapshot.get("stocks") or []) for snapshot, _events in self.collections),
            "events": sum(len(events) for _snapshot, events in self.collections),
        }


def encoded(value): return json.dumps(value, ensure_ascii=False)


def test_migration_merges_legacy_and_v1_snapshots_and_preserves_latest():
    redis = Redis(
        values={
            "策略选股:strategies": encoded([{"策略ID": "s1", "名称": "Legacy", "页面URL": "https://legacy"}]),
            "strategy_pick:v1:strategies": encoded([{"id": "s1", "name": "V1", "pageUrl": "https://v1"}]),
        },
        lists={
            "策略选股:s1:history:20260807": [encoded({"策略ID": "s1", "采集日期": "20260807", "采集时间": "09:00:00", "股票列表": [{"代码": "600000"}]})],
            "strategy_pick:v1:s1:history:20260807": [encoded({"strategyId": "s1", "collectedDate": "20260807", "collectedTime": "11:00:00", "stocks": [{"code": "600000"}]})],
            "strategy_pick:v1:s1:events:20260807": [encoded({"eventId": "evt-1", "code": "600000"}), encoded({"eventId": "evt-1", "code": "600000"})],
        },
    )
    mysql = MySQL()

    result = migrate_strategy_pick(redis, mysql)

    assert result["snapshots"] == 2
    assert result["stocks"] == 2
    assert result["events"] == 1
    assert mysql.definitions[-1]["name"] == "V1"
    assert {item[0]["collectedTime"] for item in mysql.collections} == {"09:00:00", "11:00:00"}
    assert result["latest"]["s1"]["collectedTime"] == "11:00:00"


def test_cleanup_refuses_to_delete_any_key_when_fund_flow_parity_fails():
    redis = Redis(values={"fund_flow:history:20240101": "old"})
    mysql = MySQL()

    with pytest.raises(RuntimeError, match="fund-flow parity"):
        cleanup_redis(redis, mysql, today="20260807", parity=lambda: False)

    assert redis.deleted == []


def test_cleanup_removes_history_but_retains_current_cache_and_ttl_state():
    redis = Redis(
        values={
            "策略选股:old": "legacy",
            "strategy_pick:v1:s1:history:20260806": "old",
            "strategy_pick:v1:s1:chart:20260806": "old",
            "strategy_pick:v1:s1:history:20260807": "today",
            "job:strategy_pick:lock": "locked",
            "job:strategy_pick:completion": "done",
        },
        ttls={"job:strategy_pick:lock": 300, "job:strategy_pick:completion": 300},
    )

    result = cleanup_redis(redis, MySQL(), today="20260807", parity=lambda: True)

    assert result["deleted"] == 3
    assert "strategy_pick:v1:s1:history:20260807" not in redis.deleted
    assert "job:strategy_pick:lock" not in redis.deleted
    assert "job:strategy_pick:completion" not in redis.deleted


def test_fund_flow_parity_compares_canonicalized_mysql_and_redis_snapshots():
    redis = Redis(values={"fund_flow:v1:industry:history:20260807": encoded([[{"board_code": "A", "net_inflow_100m": 1.25, "time": "15:00:00"}]])})

    assert verify_fund_flow_parity(redis, MySQL(), today="20260807") is True


def test_live_cleanup_requires_confirmation_and_existing_backups(tmp_path):
    redis = Redis()

    with pytest.raises(RuntimeError, match="confirmation"):
        run_migration(redis, MySQL(), cleanup=True, backup_paths=[], confirmation="")

    with pytest.raises(RuntimeError, match="backup"):
        run_migration(redis, MySQL(), cleanup=True, backup_paths=[tmp_path / "missing.sql"], confirmation="REDIS_CACHE_ONLY")
