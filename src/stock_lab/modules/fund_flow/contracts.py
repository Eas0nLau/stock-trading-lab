from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from stock_lab.shared.errors import DataValidationError


KEYS = {
    "类型": "type", "采集日期": "trade_date", "采集时间": "collected_at",
    "记录数量": "record_count", "名称": "name", "板块名称": "board_name",
    "板块代码": "board_code", "资金净流入(亿)": "net_inflow_100m",
    "资金净流入亿": "net_inflow_100m", "龙头": "leader", "时间": "time",
}

_SIX_PLACES = Decimal("0.000001")


def normalize_net_inflow_100m(value: object, source_unit: str = "wan") -> Decimal:
    """Convert source amounts to canonical 亿元 values exactly once."""
    if value is None or isinstance(value, bool):
        raise DataValidationError("Fund-flow amount is required")
    try:
        amount = Decimal(str(value).strip())
    except (InvalidOperation, AttributeError, ValueError) as error:
        raise DataValidationError(f"Invalid fund-flow amount: {value!r}") from error
    if not amount.is_finite():
        raise DataValidationError(f"Invalid fund-flow amount: {value!r}")
    if source_unit.lower() in {"yuan", "元"}:
        amount /= Decimal("100000000")
    elif source_unit.lower() in {"wan", "万元"}:
        amount /= Decimal("10000")
    elif source_unit.lower() not in {"100m", "yi", "亿元"}:
        raise DataValidationError(f"Unsupported fund-flow amount unit: {source_unit}")
    return amount.quantize(_SIX_PLACES, rounding=ROUND_HALF_UP)


def translate_legacy_fund_flow(value):
    if isinstance(value, list):
        return [translate_legacy_fund_flow(item) for item in value]
    if not isinstance(value, dict):
        return value
    result = {}
    for key, nested in value.items():
        target = KEYS.get(key, key)
        if not target.isascii():
            raise DataValidationError(f"Unmapped fund-flow key: {key}")
        result[target] = translate_legacy_fund_flow(nested)
    return result
