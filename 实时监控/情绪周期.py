from stock_lab.modules.emotion.api import load_current_index_emotion
from stock_lab.modules.emotion.contracts import translate_canonical_payload
from stock_lab.modules.emotion.index_cycle import calculate_legacy_index_cycle


def 计算当前情绪周期():
    return translate_canonical_payload(load_current_index_emotion())


def 计算当前指数周期():
    return 计算当前情绪周期()


def 计算指数周期结果(index_rows, market_rows):
    return translate_canonical_payload(calculate_legacy_index_cycle(index_rows, market_rows))
