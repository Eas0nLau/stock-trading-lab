from stock_lab.shared.errors import DataValidationError


LEGACY_KEY_MAP = {
    "策略ID": "strategyId", "策略名称": "strategyName", "策略配置": "strategies",
    "名称": "name", "代码": "code", "市场": "market", "字段": "fields",
    "状态": "status", "错误信息": "errorMessage", "启用": "enabled",
    "页面URL": "pageUrl", "监听目标": "listenTargets", "监控时间段": "monitorPeriods",
    "监控频率秒": "monitorIntervalSeconds", "创建时间": "createdAt", "更新时间": "updatedAt",
    "采集日期": "collectedDate", "采集时间": "collectedTime", "最新采集时间": "lastCollectedAt",
    "股票列表": "stocks", "新增股票": "addedStocks", "移除股票": "removedStocks",
    "名单数量": "stockCount", "新增数量": "addedCount", "移除数量": "removedCount",
    "入选日期": "selectedDate", "入选时间": "selectedAt", "入选时分秒": "selectedClock",
    "移除日期": "removedDate", "移除时间": "removedTime", "最后事件ID": "lastEventId",
    "event_id": "eventId",
}


def translate_legacy_strategy_pick(value, *, parent_key=None):
    if isinstance(value, list):
        return [translate_legacy_strategy_pick(item, parent_key=parent_key) for item in value]
    if not isinstance(value, dict):
        return value
    result = {}
    for key, nested in value.items():
        target = key if parent_key == "fields" else LEGACY_KEY_MAP.get(key, key)
        if parent_key != "fields" and not str(target).isascii():
            raise DataValidationError(f"Unmapped strategy-pick key: {key}")
        result[target] = translate_legacy_strategy_pick(nested, parent_key=target)
    return result


def translate(value):
    return translate_legacy_strategy_pick(value)
