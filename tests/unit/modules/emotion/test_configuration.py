from types import SimpleNamespace

from stock_lab.modules.emotion.api import load_current_hot_board_emotion
from stock_lab.modules.emotion import hot_board


def custom_settings():
    return SimpleNamespace(
        hot_board_emotion_selection_threshold=3,
        hot_board_emotion_climax_threshold=7,
        hot_board_emotion_strong_continuation_ratio=0.75,
        hot_board_emotion_excluded_boards=("排除板块", "另一个排除板块"),
    )


class Repository:
    def recent_hot_board_dates(self, _days):
        return [{"trade_date": 20260807}]

    def hot_board_rows(self, _dates):
        return [
            {
                "trade_date": 20260807,
                "board_name": "排除板块",
                "current_board_count": 9,
                "overall_status": "高潮",
                "emotion_score": 100,
            },
            {
                "trade_date": 20260807,
                "board_name": "保留板块",
                "current_board_count": 3,
                "overall_status": "活跃",
                "emotion_score": 50,
            },
        ]


def test_production_hot_board_loader_applies_custom_settings():
    result = load_current_hot_board_emotion(
        30,
        repository=Repository(),
        settings=custom_settings(),
    )

    assert [board["board_name"] for board in result["boards"]] == ["保留板块"]
    assert result["config"] == {
        "selection_threshold": 3,
        "climax_threshold": 7,
        "strong_continuation_ratio": 0.75,
        "excluded_boards": ["另一个排除板块", "排除板块"],
    }


def test_legacy_config_preserves_custom_thresholds_and_exclusions(monkeypatch):
    monkeypatch.setattr(hot_board, "get_settings", custom_settings)
    monkeypatch.setattr(hot_board, "_legacy_config", None)

    result = hot_board.refresh_legacy_config()

    assert result == {
        "热门板块入选数量阈值": 3,
        "高潮数量阈值": 7,
        "强势延续晋级比例": 0.75,
        "排除板块": ["另一个排除板块", "排除板块"],
    }
    assert hot_board.legacy_config_value("热门板块入选数量阈值") == 3
    assert hot_board.legacy_config_value("高潮数量阈值") == 7
    assert hot_board.legacy_config_value("强势延续晋级比例") == 0.75
    assert hot_board.legacy_config_value("热门板块排除集合") == {"排除板块", "另一个排除板块"}
