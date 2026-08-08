import pytest

from task import _5_韭研公社异动 as legacy_jiuyan
from stock_lab.modules.market_data import jiuyan


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

    rows = jiuyan.parse_response(response, 20260805)

    assert len(rows) == 1
    assert rows[0]["data_id"] == "20260805_机器人_600000"


def test_parse_empty_response_returns_incomplete_error():
    with pytest.raises(jiuyan.IncompleteJiuyanResponse):
        jiuyan.parse_response({"data": []}, 20260805)


def test_request_rate_limiter_waits_between_page_requests(monkeypatch):
    clock = iter([100.0, 100.0])
    sleeps = []
    monkeypatch.setattr(jiuyan.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(jiuyan.time, "sleep", sleeps.append)
    monkeypatch.setattr(jiuyan, "MIN_REQUEST_INTERVAL_SECONDS", 60)
    monkeypatch.setattr(jiuyan.random, "uniform", lambda low, high: 60.0)
    jiuyan._last_request_time = 70.0

    jiuyan.wait_for_request_slot()

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

    rows = jiuyan.parse_response(response, 20260805)

    assert rows[0]["股票代码"] == 1
    assert rows[0]["涨幅"] == 10.01
    assert rows[0]["板块个股数量"] == 12


def test_page_date_uses_hyphenated_route():
    assert jiuyan.format_page_date(20260701) == "2026-07-01"


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
        jiuyan.parse_response(response, 20260701)


def test_collector_writes_english_action_table():
    class Repository:
        def __init__(self):
            self.rows = None

        def upsert_jiuyan_actions(self, rows):
            self.rows = rows
            return len(rows)

    repository = Repository()
    collector = jiuyan.JiuyanCollector(
        repository,
        response_source=lambda _date: {"data": []},
        parser=lambda _response, date: [{
            "data_id": "id-1",
            "date": date,
            "板块": "机器人",
            "板块个股数量": 20,
            "股票代码": 1,
            "股票名称": "平安银行",
            "code": "000001",
        }],
    )

    assert collector.collect(20260806) == 1
    assert repository.rows[0]["stock_code"] == "000001"
    assert all(column.isascii() for column in repository.rows[0])


def test_legacy_jiuyan_names_forward_to_official_parser(monkeypatch):
    monkeypatch.setattr(legacy_jiuyan, "parse_response", lambda response, date: (response, date))

    assert legacy_jiuyan.解析异动响应("payload", 20260806) == ("payload", 20260806)
