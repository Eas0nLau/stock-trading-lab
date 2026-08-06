from stock_lab.modules.emotion.contracts import translate_legacy_payload


def collect_keys(value):
    if isinstance(value, dict):
        for key, nested in value.items():
            yield key
            yield from collect_keys(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from collect_keys(nested)


def test_translate_legacy_index_payload_recursively():
    payload = {
        "状态": "success",
        "指数周期": {
            "交易日期": 20260806,
            "周期状态": "发酵",
            "周期分数": 72.5,
            "指数": {"收盘": 3560.1, "涨跌幅": 1.2},
            "市场宽度": {"上涨家数": 3200, "下跌家数": 1800},
            "最近走势": [{"日期": 20260806, "涨停家数": 88}],
        },
    }

    result = translate_legacy_payload(payload)

    assert result["status"] == "success"
    assert result["index_cycle"]["trade_date"] == 20260806
    assert result["index_cycle"]["cycle_state"] == "发酵"
    assert result["index_cycle"]["index_quote"]["close_price"] == 3560.1
    assert result["index_cycle"]["recent_trend"][0]["limit_up_count"] == 88
    assert all(key.isascii() for key in collect_keys(result))


def test_translate_legacy_hot_board_payload_preserves_nulls_and_values():
    payload = {
        "状态": "success",
        "最新交易日": 20260806,
        "板块列表": [{
            "板块": "机器人",
            "近期走势": [{"日期": 20260806, "综合状态": "强势延续", "情绪分": None}],
        }],
    }

    result = translate_legacy_payload(payload)

    assert result["latest_trade_date"] == 20260806
    assert result["boards"][0]["board_name"] == "机器人"
    assert result["boards"][0]["recent_trend"][0]["overall_status"] == "强势延续"
    assert result["boards"][0]["recent_trend"][0]["emotion_score"] is None
    assert all(key.isascii() for key in collect_keys(result))
