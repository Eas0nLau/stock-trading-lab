import re

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


def test_emotion_v1_preserves_empty_response_contracts():
    app = FastAPI()
    register_emotion_routes(
        app,
        index_loader=lambda: {"status": "empty", "message": "no index data"},
        hot_board_loader=lambda days: {
            "status": "empty",
            "available_dates": [],
            "boards": [],
        },
    )
    client = TestClient(app)

    assert client.get("/api/v1/emotion/current").json() == {
        "status": "empty",
        "message": "no index data",
    }
    assert client.get("/api/v1/emotion/hot-boards").json() == {
        "status": "empty",
        "available_dates": [],
        "boards": [],
    }


def test_emotion_v1_payload_keys_are_recursively_snake_case():
    app = FastAPI()
    register_emotion_routes(
        app,
        index_loader=lambda: {
            "状态": "success",
            "指数周期": {
                "交易日期": 20260805,
                "市场宽度": {"上涨家数": 3000},
                "信号": [{"名称": "trend", "数值": 1}],
            },
        },
        hot_board_loader=lambda days: {
            "状态": "success",
            "可选日期": [20260805],
            "板块列表": [{"板块": "Robotics", "最新记录": {"情绪分": 80}}],
        },
    )
    client = TestClient(app)
    payloads = [
        client.get("/api/v1/emotion/current").json(),
        client.get("/api/v1/emotion/hot-boards").json(),
    ]

    def assert_ascii_keys(value):
        if isinstance(value, dict):
            assert all(re.fullmatch(r"[a-z][a-z0-9_]*", key) for key in value)
            for nested in value.values():
                assert_ascii_keys(nested)
        elif isinstance(value, list):
            for nested in value:
                assert_ascii_keys(nested)

    for payload in payloads:
        assert_ascii_keys(payload)
    assert payloads[0]["index_cycle"]["market_breadth"]["advancing_count"] == 3000
    assert payloads[1]["boards"][0]["latest_record"]["emotion_score"] == 80
