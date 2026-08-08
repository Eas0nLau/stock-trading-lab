from stock_lab.modules.emotion.api import load_current_hot_board_emotion
from stock_lab.modules.emotion.contracts import translate_canonical_payload


def 读取热门板块情绪(days=30):
    return translate_canonical_payload(load_current_hot_board_emotion(days))
