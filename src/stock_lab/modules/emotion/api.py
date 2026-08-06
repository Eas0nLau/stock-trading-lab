from collections.abc import Callable

from fastapi import FastAPI

from .contracts import translate_legacy_payload


def load_legacy_index_emotion():
    from 实时监控 import 情绪周期

    return 情绪周期.计算当前情绪周期()


def load_legacy_hot_board_emotion(days: int):
    from 实时监控 import 热门板块情绪

    return 热门板块情绪.读取热门板块情绪(days=days)


def register_emotion_routes(
    app: FastAPI,
    *,
    index_loader: Callable[[], dict] = load_legacy_index_emotion,
    hot_board_loader: Callable[[int], dict] = load_legacy_hot_board_emotion,
) -> None:
    @app.get("/api/v1/emotion/current")
    def get_current_emotion():
        return translate_legacy_payload(index_loader())

    @app.get("/api/v1/emotion/hot-boards")
    def get_hot_board_emotion(days: int = 30):
        return translate_legacy_payload(hot_board_loader(max(5, min(60, days))))
