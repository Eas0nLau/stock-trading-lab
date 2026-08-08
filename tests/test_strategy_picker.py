from 实时监控 import 策略选股


def test_string_data_response_is_ignored_without_attribute_error():
    response = {"data": "captcha verification required"}

    assert 策略选股.解析策略选股接口响应(response) is None


def test_strategy_collection_forwards_to_official_collector(monkeypatch):
    monkeypatch.setattr(
        策略选股,
        "refresh_strategy",
        lambda strategy_id, attempts: (strategy_id, attempts),
    )

    assert 策略选股.策略选股采集("gap", 最大重试次数=3) == ("gap", 3)
