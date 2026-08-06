import pytest

from task import emotion_analysis


def test_index_result_maps_all_json_columns():
    result = {
        "交易日期": 20260805,
        "周期状态": "发酵",
        "周期分数": 64.5,
        "指数": {"收盘": 100},
        "市场宽度": {"上涨家数": 2000},
        "分项得分": {"趋势": 20},
        "信号": [],
        "最近走势": [],
        "波动图": [],
    }

    row = emotion_analysis.指数结果转数据库行(result)

    assert row["日期"] == 20260805
    assert row["完整结果JSON"]["周期状态"] == "发酵"
    assert row["市场宽度JSON"]["上涨家数"] == 2000


def test_hot_board_analysis_requires_both_board_dates(monkeypatch):
    monkeypatch.setattr(
        emotion_analysis,
        "读取板块股票池",
        lambda date: [] if date == 20260804 else [{"股票代码": 1}],
    )

    with pytest.raises(emotion_analysis.MissingEmotionSource):
        emotion_analysis.落库热门板块情绪(20260805, 20260804)


def test_index_api_selects_and_restores_complete_result(monkeypatch):
    captured = {}

    def fake_mysql(sql, **kwargs):
        captured["sql"] = sql
        return [{"完整结果JSON": '{"状态": "success", "周期状态": "发酵"}'}]

    monkeypatch.setattr(emotion_analysis.情绪周期.db, "mysql_localhost", fake_mysql)

    result = emotion_analysis.情绪周期.读取最新指数周期落库结果()

    assert "完整结果JSON" in captured["sql"]
    assert result["周期状态"] == "发酵"


def test_board_count_uses_source_board_total_instead_of_filtered_rows():
    rows = [
        {"板块": "机器人", "板块个股数量": 20, "股票代码": 1},
        {"板块": "机器人", "板块个股数量": 20, "股票代码": 2},
    ]

    assert emotion_analysis.读取板块数量(rows, "机器人") == 20
