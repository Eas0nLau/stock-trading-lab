from stock_lab.modules.emotion.contracts import LEGACY_KEY_MAP
from stock_lab.modules.emotion.repository import EmotionRepository
from stock_lab.modules.emotion.service import EmotionService
from stock_lab.modules.market_data.repository import MarketDataRepository


def _legacy_value(value):
    reverse = {target: source for source, target in LEGACY_KEY_MAP.items()}
    if isinstance(value, list):
        return [_legacy_value(item) for item in value]
    if isinstance(value, dict):
        return {reverse.get(key, key): _legacy_value(nested) for key, nested in value.items()}
    return value


def 读取热门板块情绪(days=30):
    from utils import db

    market_data = MarketDataRepository(db.mysql_localhost, db.engine)
    repository = EmotionRepository(db.mysql_localhost, market_data=market_data)
    return _legacy_value(EmotionService(repository).hot_board_emotion(days))
