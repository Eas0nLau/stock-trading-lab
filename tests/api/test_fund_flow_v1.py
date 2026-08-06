from fastapi import FastAPI
from fastapi.testclient import TestClient

from stock_lab.modules.fund_flow.api import register_fund_flow_routes
from stock_lab.modules.fund_flow.service import FundFlowService
from stock_lab.modules.fund_flow.repository import FundFlowRepository


class Redis:
    def __init__(self): self.values = {}; self.sets = {}
    def get(self, key): return self.values.get(key)
    def set(self, key, value): self.values[key] = value
    def sadd(self, key, value): self.sets.setdefault(key, set()).add(value)
    def smembers(self, key): return self.sets.get(key, set())
    def delete(self, *keys):
        for key in keys:
            self.values.pop(key, None)
            self.sets.pop(key, None)


def test_fund_flow_v1_exposes_english_history_contract():
    redis = Redis()
    repository = FundFlowRepository(redis)
    repository.save_history("industry", "20260806", {"format": "matrix-v2", "boards": []})
    app = FastAPI()
    register_fund_flow_routes(app, repository=repository)

    response = TestClient(app).get("/api/v1/fund-flow/industry/history/20260806")

    assert response.status_code == 200
    assert response.json()["format"] == "matrix-v2"
    assert response.json()["boards"] == []


def test_fund_flow_v1_forwards_top_n_to_matrix_shaping():
    redis = Redis()
    repository = FundFlowRepository(redis)
    repository.save_history("industry", "20260806", [
        {"time": "10:00", "board_name": "A", "net_inflow_100m": 5},
        {"time": "10:00", "board_name": "B", "net_inflow_100m": 3},
    ])
    app = FastAPI()
    register_fund_flow_routes(app, repository=repository)

    response = TestClient(app).get("/api/v1/fund-flow/industry/history/20260806?top_n=1")

    assert response.json()["top_n"] == 1
    assert [board["name"] for board in response.json()["boards"]] == ["A"]


def test_fund_flow_v1_stream_emits_english_snapshot_event():
    redis = Redis()
    repository = FundFlowRepository(redis)
    app = FastAPI()
    register_fund_flow_routes(app, repository=repository)
    service = FundFlowService(repository)

    events = service.stream_events()
    first = next(events)
    assert first.startswith("data: ")
    repository.publish_snapshot("industry", "20260806", "10:00:00", 2)
    snapshot = next(events)
    assert '"type": "snapshot"' in snapshot
    assert '"trade_date": "20260806"' in snapshot
    events.close()


def test_register_routes_does_not_register_legacy_fund_flow_paths():
    redis = Redis()
    app = FastAPI()
    register_fund_flow_routes(app, repository=FundFlowRepository(redis))
    paths = {route.path for route in app.routes}
    assert "/api/v1/fund-flow/stream" in paths
    assert not any(path.startswith("/api/zijin") for path in paths)
