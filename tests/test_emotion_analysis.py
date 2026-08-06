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


def test_board_appearance_and_disappearance_are_not_missing_data(monkeypatch):
    source_rows = {
        20260804: [{"板块": "旧板块", "板块个股数量": 8, "股票代码": 1}],
        20260805: [{"板块": "新板块", "板块个股数量": 8, "股票代码": 2}],
    }
    written = []
    monkeypatch.setattr(
        emotion_analysis,
        "读取板块股票池",
        lambda date: source_rows[date],
    )
    monkeypatch.setattr(emotion_analysis, "_行情", lambda codes, date: {})
    monkeypatch.setattr(
        emotion_analysis,
        "_upsert",
        lambda table, columns, rows, keys: written.extend(rows) or len(rows),
    )

    emotion_analysis.落库热门板块情绪(20260805, 20260804)

    status = {row["板块"]: row["综合状态"] for row in written}
    assert status == {"旧板块": "退潮", "新板块": "升温"}
