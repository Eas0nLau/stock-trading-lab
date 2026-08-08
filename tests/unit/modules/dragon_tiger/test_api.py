from fastapi import FastAPI
from fastapi.testclient import TestClient

from stock_lab.modules.dragon_tiger.api import register_dragon_tiger_routes


class FakeManager:
    def __init__(self, start_result=None, status=None):
        self.start_result = start_result or {"jobId": "job-1", "status": "queued"}
        self.status = status

    def start(self, start_date, latest_date):
        return self.start_result

    def get(self, job_id):
        return self.status


def client(manager, analysis=None):
    app = FastAPI()
    register_dragon_tiger_routes(app, manager=manager, analysis=analysis or (lambda *_: {"selectedCodes": []}))
    return TestClient(app)


def test_create_collection_job_returns_202():
    response = client(FakeManager()).post(
        "/api/v1/dragon-tiger/collection-jobs",
        json={"startDate": 20260404, "latestDate": 20260806},
    )

    assert response.status_code == 202
    assert response.json()["jobId"] == "job-1"


def test_create_collection_job_rejects_invalid_date_range():
    response = client(FakeManager()).post(
        "/api/v1/dragon-tiger/collection-jobs",
        json={"startDate": 20260806, "latestDate": 20260404},
    )

    assert response.status_code == 422


def test_create_collection_job_rejects_non_trading_day():
    class ValidatingManager(FakeManager):
        def start(self, start_date, latest_date):
            raise ValueError("start_date must be a trading day")

    response = client(ValidatingManager()).post(
        "/api/v1/dragon-tiger/collection-jobs",
        json={"startDate": 20260404, "latestDate": 20260404},
    )

    assert response.status_code == 422


def test_status_returns_job_state_or_not_found():
    response = client(FakeManager(status={"jobId": "job-1", "status": "succeeded"})).get(
        "/api/v1/dragon-tiger/collection-jobs/job-1"
    )
    assert response.status_code == 200
    assert response.json()["status"] == "succeeded"

    missing = client(FakeManager()).get("/api/v1/dragon-tiger/collection-jobs/missing")
    assert missing.status_code == 404


def test_premium_route_returns_analysis_result():
    response = client(FakeManager(), analysis=lambda start, latest: {
        "startDate": start,
        "latestDate": latest,
        "selectedCodes": ["000001.SZ"],
    }).get("/api/v1/dragon-tiger/premium?start_date=20260404&latest_date=20260806")

    assert response.status_code == 200
    assert response.json()["selectedCodes"] == ["000001.SZ"]
