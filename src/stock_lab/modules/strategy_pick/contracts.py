from stock_lab.shared.errors import DataValidationError


KEYS = {"状态": "status", "错误信息": "error_message", "名称": "name", "代码": "code", "策略名称": "strategy_name", "策略ID": "strategy_id", "启用": "enabled", "字段": "fields", "最新采集时间": "last_collected_at"}


def translate(value):
    if isinstance(value, list): return [translate(item) for item in value]
    if not isinstance(value, dict): return value
    result = {}
    for key, nested in value.items():
        target = KEYS.get(key, key)
        if not target.isascii(): raise DataValidationError(f"Unmapped strategy-pick key: {key}")
        result[target] = translate(nested)
    return result
