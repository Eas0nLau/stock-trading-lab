from stock_lab.shared.errors import DataValidationError


KEYS = {
    "类型": "type", "采集日期": "trade_date", "采集时间": "collected_at",
    "记录数量": "record_count", "名称": "name", "板块名称": "board_name",
    "板块代码": "board_code", "资金净流入(亿)": "net_inflow_100m",
    "资金净流入亿": "net_inflow_100m", "龙头": "leader", "时间": "time",
}


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
