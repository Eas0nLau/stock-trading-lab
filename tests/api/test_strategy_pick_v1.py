from fastapi import FastAPI
from fastapi.testclient import TestClient

from stock_lab.modules.strategy_pick.api import register_strategy_pick_routes
from stock_lab.modules.strategy_pick.repository import StrategyPickRepository


class Redis:
    def __init__(self): self.values = {}; self.lists = {}; self.sets = {}
    def get(self, key): return self.values.get(key)
    def set(self, key, value): self.values[key] = value
    def delete(self, key): self.values.pop(key, None); self.sets.pop(key, None)
    def rpush(self, key, value): self.lists.setdefault(key, []).append(value)
    def lrange(self, key, start, end): return self.lists.get(key, [])
    def sadd(self, key, *values): self.sets.setdefault(key, set()).update(values)
    def smembers(self, key): return self.sets.get(key, set())
    def keys(self, pattern): return []


class Collector:
    def __init__(self): self.calls = []
    def refresh(self, strategy_id):
        self.calls.append(strategy_id)
        return {"strategyId": strategy_id, "collectedDate": "20260806", "status": "success", "stocks": []}
    def refresh_all(self): self.calls.append("all"); return []


def create_client():
    repository = StrategyPickRepository(Redis())
    repository.save_strategies([{
        "id": "eastmoney_1", "name": "新高监控", "pageUrl": "https://example.test",
        "listenTargets": ["/api/search"], "monitorPeriods": [["09:20", "11:31"]],
        "monitorIntervalSeconds": 30, "enabled": True, "createdAt": "", "updatedAt": "",
    }])
    collector = Collector()
    app = FastAPI()
    register_strategy_pick_routes(app, repository=repository, collector=collector)
    return TestClient(app), repository, collector, app


def test_strategy_pick_v1_supports_crud_with_camel_case_fields():
    client, _, _, _ = create_client()
    created = client.post("/api/v1/strategy-pick/strategies", json={
        "name": "跳空高开", "pageUrl": "https://example.test/gap", "enabled": True,
        "monitorPeriods": [["09:20", "11:31"]], "monitorIntervalSeconds": 30,
    })
    assert created.status_code == 200
    strategy_id = created.json()["id"]
    assert created.json()["name"] == "跳空高开"

    updated = client.put(f"/api/v1/strategy-pick/strategies/{strategy_id}", json={"enabled": False})
    assert updated.json()["enabled"] is False
    assert client.delete(f"/api/v1/strategy-pick/strategies/{strategy_id}").json() == {"deleted": strategy_id}


def test_strategy_pick_v1_exposes_scoped_reads_and_refreshes():
    client, repository, collector, _ = create_client()
    snapshot = {"strategyId": "eastmoney_1", "collectedDate": "20260806", "collectedTime": "10:00:00", "status": "success", "stocks": []}
    repository.save_snapshot("eastmoney_1", snapshot, update_latest=True)
    repository.save_events("eastmoney_1", "20260806", [{"eventId": "evt-1", "code": "600000"}])

    assert client.get("/api/v1/strategy-pick/strategies/eastmoney_1/latest").json() == snapshot
    assert client.get("/api/v1/strategy-pick/strategies/eastmoney_1/history/20260806").json() == [snapshot]
    assert client.get("/api/v1/strategy-pick/strategies/eastmoney_1/events/20260806").json()[0]["eventId"] == "evt-1"
    assert client.get("/api/v1/strategy-pick/strategies/eastmoney_1/dates").json() == ["20260806"]
    assert client.post("/api/v1/strategy-pick/strategies/eastmoney_1/refresh").json()["strategyId"] == "eastmoney_1"
    assert client.post("/api/v1/strategy-pick/refresh-all").json() == []
    assert collector.calls == ["eastmoney_1", "all"]


def test_strategy_pick_v1_stream_uses_english_events_and_cleans_up():
    _, repository, _, _ = create_client()
    stream = repository.stream_events()
    next(stream)
    repository.publish_snapshot({"strategyId": "eastmoney_1", "addedStocks": [{"eventId": "evt-1"}]})
    event = next(stream)
    assert '"type": "snapshot"' in event
    assert '"strategyId": "eastmoney_1"' in event
    assert "策略ID" not in event
    stream.close()


def test_strategy_pick_registration_does_not_include_legacy_paths():
    _, _, _, app = create_client()
    paths = {route.path for route in app.routes}
    assert "/api/v1/strategy-pick/stream" in paths
    assert not any(path.startswith("/api/strategy-pick") for path in paths)
