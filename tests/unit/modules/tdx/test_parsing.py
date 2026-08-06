import struct

from stock_lab.modules.tdx.models import StockCode, normalize_stock_code
from stock_lab.modules.tdx.parsing import parse_day_record, parse_minute_record


def test_normalize_stock_code_supports_exchange_suffix():
    assert normalize_stock_code("1.SZ") == StockCode("000001", "SZ")


def test_parse_day_record_preserves_tdx_price_and_volume_units():
    raw = struct.pack("<IIIIIfII", 20260806, 1000, 1100, 900, 1050, 123.5, 77, 0)

    result = parse_day_record(raw, StockCode("000001", "SZ"))

    assert result["stock"] == "000001.SZ"
    assert result["open"] == 10.0
    assert result["close"] == 10.5
    assert result["amount"] == 123.5


def test_parse_minute_record_decodes_date_and_time():
    raw = struct.pack("<HHfffffII", 22 * 2048 + 8 * 100 + 6, 570, 10, 11, 9, 10.5, 20, 30, 0)

    result = parse_minute_record(raw, StockCode("600000", "SH"))

    assert result["date"] == "20260806"
    assert result["time"] == "09:30"
