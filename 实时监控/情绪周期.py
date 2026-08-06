from stock_lab.modules.emotion.contracts import LEGACY_KEY_MAP
from stock_lab.modules.emotion.index_cycle import calculate_index_cycle
from stock_lab.modules.emotion.repository import EmotionRepository
from stock_lab.modules.emotion.service import EmotionService
from stock_lab.modules.market_data.repository import MarketDataRepository


def _service():
    from utils import db

    market_data = MarketDataRepository(db.mysql_localhost, db.engine)
    return EmotionService(EmotionRepository(db.mysql_localhost, market_data=market_data))


def _legacy_value(value):
    reverse = {target: source for source, target in LEGACY_KEY_MAP.items()}
    if isinstance(value, list):
        return [_legacy_value(item) for item in value]
    if isinstance(value, dict):
        return {reverse.get(key, key): _legacy_value(nested) for key, nested in value.items()}
    return value


def 计算当前情绪周期():
    return _legacy_value(_service().current_index_emotion())


def 计算当前指数周期():
    return 计算当前情绪周期()


def 计算指数周期结果(index_rows, market_rows):
    canonical_rows = [{
        "trade_date": row.get("日期"),
        "open_price": row.get("开盘"),
        "close_price": row.get("收盘"),
        "high_price": row.get("最高"),
        "low_price": row.get("最低"),
        "turnover": row.get("成交额"),
        "change_pct": row.get("涨跌幅"),
    } for row in index_rows]
    return _legacy_value(calculate_index_cycle(canonical_rows, market_rows))
