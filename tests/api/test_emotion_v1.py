from fastapi import FastAPI
from fastapi.testclient import TestClient

from stock_lab.modules.emotion.api import register_emotion_routes


def test_emotion_v1_routes_translate_legacy_services():
    app = FastAPI()
    register_emotion_routes(
        app,
        index_loader=lambda: {"状态": "success", "指数周期": {"周期分数": 70}},
        hot_board_loader=lambda days: {"状态": "success", "统计交易日数": days, "板块列表": []},
    )
    client = TestClient(app)

    index_response = client.get("/api/v1/emotion/current")
    hot_response = client.get("/api/v1/emotion/hot-boards?days=20")

    assert index_response.json() == {"status": "success", "index_cycle": {"cycle_score": 70}}
    assert hot_response.json() == {"status": "success", "trading_day_count": 20, "boards": []}
