import pytest

from stock_lab.modules.strategy_pick.contracts import translate_legacy_strategy_pick
from stock_lab.shared.errors import DataValidationError


def test_translates_strategy_snapshot_to_camel_case_without_translating_display_values():
    payload = {
        "策略ID": "eastmoney_1",
        "策略名称": "新高监控",
        "采集日期": "20260806",
        "采集时间": "10:00:00",
        "状态": "success",
        "股票列表": [{"代码": "600000", "名称": "浦发银行", "市场": "SH", "字段": {"涨跌幅": "3.2"}}],
        "新增股票": [{"event_id": "evt-1", "代码": "600000", "名称": "浦发银行", "入选时间": "2026-08-06 10:00:00"}],
    }

    assert translate_legacy_strategy_pick(payload) == {
        "strategyId": "eastmoney_1",
        "strategyName": "新高监控",
        "collectedDate": "20260806",
        "collectedTime": "10:00:00",
        "status": "success",
        "stocks": [{"code": "600000", "name": "浦发银行", "market": "SH", "fields": {"涨跌幅": "3.2"}}],
        "addedStocks": [{"eventId": "evt-1", "code": "600000", "name": "浦发银行", "selectedAt": "2026-08-06 10:00:00"}],
    }


def test_rejects_unmapped_top_level_chinese_contract_key():
    with pytest.raises(DataValidationError):
        translate_legacy_strategy_pick({"未知字段": 1})
