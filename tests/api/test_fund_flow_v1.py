from fastapi import FastAPI
from fastapi.testclient import TestClient

from stock_lab.modules.fund_flow.api import register_fund_flow_routes
from stock_lab.modules.fund_flow.repository import FundFlowRepository


class Redis:
    def __init__(self): self.values = {}; self.sets = {}
    def get(self, key): return self.values.get(key)
    def set(self, key, value): self.values[key] = value
    def sadd(self, key, value): self.sets.setdefault(key, set()).add(value)
    def smembers(self, key): return self.sets.get(key, set())


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
