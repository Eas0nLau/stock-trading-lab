import pytest

from task import _5_韭研公社异动 as jiuyan


def test_parse_jiuyan_response_filters_limit_up_range():
    response = {
        "data": [
            {
                "板块": "机器人",
                "板块个股数量": 12,
                "股票代码": "600000",
                "股票名称": "示例",
                "涨幅": 9.8,
                "涨停时间": "09:35:00",
                "几天几板": "2天2板",
            },
            {
                "板块": "机器人",
                "板块个股数量": 12,
                "股票代码": "000001",
                "涨幅": 8.2,
            },
        ]
    }

    rows = jiuyan.解析异动响应(response, 20260805)

    assert len(rows) == 1
    assert rows[0]["data_id"] == "20260805_机器人_600000"


def test_parse_empty_response_returns_incomplete_error():
    with pytest.raises(jiuyan.IncompleteJiuyanResponse):
        jiuyan.解析异动响应({"data": []}, 20260805)


def test_request_rate_limiter_waits_between_page_requests(monkeypatch):
    clock = iter([100.0, 100.0])
    sleeps = []
    monkeypatch.setattr(jiuyan.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(jiuyan.time, "sleep", sleeps.append)
    monkeypatch.setattr(jiuyan, "最小请求间隔秒", 60)
    jiuyan._上次请求时间 = 70.0

    jiuyan.等待请求频率()

    assert sleeps == [30.0]


def test_parse_grouped_action_fields_and_scaled_range():
    response = {
        "data": [
            {
                "name": "机器人",
                "count": 12,
                "list": [
                    {
                        "code": "sz000001",
                        "name": "示例",
                        "article": {
                            "action_info": {
                                "time": "09:35:00",
                                "num": "2天2板",
                                "shares_range": 1001,
                                "expound": "题材解析",
                            }
                        },
                    }
                ],
            }
        ]
    }

    rows = jiuyan.解析异动响应(response, 20260805)

    assert rows[0]["股票代码"] == 1
    assert rows[0]["涨幅"] == 10.01
    assert rows[0]["板块个股数量"] == 12


def test_page_date_uses_hyphenated_route():
    assert jiuyan.格式化页面日期(20260701) == "2026-07-01"


def test_response_date_must_match_requested_date():
    response = {
        "data": [
            {
                "date": "2026-08-06",
                "name": "机器人",
                "count": 12,
                "list": [{
                    "code": "sz000001",
                    "name": "示例",
                    "article": {"action_info": {"shares_range": 1001}},
                }],
            }
        ]
    }

    with pytest.raises(jiuyan.IncompleteJiuyanResponse, match="响应日期"):
        jiuyan.解析异动响应(response, 20260701)
def test_collector_writes_english_action_table(monkeypatch):
    captured = {}
    monkeypatch.setattr(jiuyan, "_采集响应", lambda _date: {"data": []})
    monkeypatch.setattr(
        jiuyan,
        "解析异动响应",
        lambda _response, date: [{
            "data_id": "id-1",
            "date": date,
            "板块": "机器人",
            "板块个股数量": 20,
            "股票代码": 1,
            "股票名称": "平安银行",
            "code": "000001",
        }],
    )
    monkeypatch.setattr(
        jiuyan,
        "_upsert_rows",
        lambda table, columns, rows, keys: captured.update(
            table=table, columns=columns, rows=rows, keys=keys
        ) or len(rows),
    )

    assert jiuyan.韭研公社异动采集(20260806) == 1
    assert captured["table"] == "jiuyan_actions"
    assert captured["rows"][0]["stock_code"] == "000001"
    assert all(column.isascii() for column in captured["columns"])

