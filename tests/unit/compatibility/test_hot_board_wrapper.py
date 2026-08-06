import importlib


def test_hot_board_wrapper_restores_legacy_strength_and_methodology(monkeypatch):
    wrapper = importlib.import_module("实时监控.热门板块情绪")
    monkeypatch.setattr(wrapper, "load_current_hot_board_emotion", lambda days: {
        "status": "success",
        "boards": [{"board_name": "机器人", "recent_strength": 23.0}],
        "methodology": {
            "continuation_methodology": "承接口径",
            "stock_universe": "股票范围口径",
        },
    })

    result = wrapper.读取热门板块情绪(30)

    assert result == {
        "状态": "success",
        "板块列表": [{"板块": "机器人", "近期强度": 23.0}],
        "数据口径": {"承接情绪": "承接口径", "股票范围": "股票范围口径"},
    }
