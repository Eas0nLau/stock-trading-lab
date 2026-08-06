import importlib

import pytest


class Source:
    def fetch_5m_bars(self, start_date, end_date, ts_code):
        return [{
            "date": "2026-08-06", "time": "20260806093500000", "code": "sz.000001",
            "open": "10", "high": "11", "low": "9", "close": "10.5",
            "volume": "100", "amount": "1050", "adjustflag": "3",
        }]


def test_missing_chinese_task_import_returns_historical_list_shape():
    module = importlib.import_module("task._2_分时数据获取_5分k")

    rows = module.get_data(20260806, 20260806, "000001.SZ", source=Source())

    assert rows == [["10", "10.5", "2026-08-06", "20260806093500000", "sz.000001", "11", "9", "100", "1050", "3"]]


def test_active_stock_keyword_consumer_uses_historical_signature():
    module = importlib.import_module("task._2_分时数据获取_5分k")

    rows = module.get_data(
        start_date=20260806,
        end_date=20260806,
        stock="430001.BJ",
        source=Source(),
    )

    assert rows[0][4] == "bj.430001"


def test_wrapper_rejects_ambiguous_code_and_stock_arguments():
    module = importlib.import_module("task._2_分时数据获取_5分k")

    with pytest.raises(TypeError, match="code or stock"):
        module.get_data(20260806, 20260806, "000001.SZ", stock="600000.SH", source=Source())
