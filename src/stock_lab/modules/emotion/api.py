from collections.abc import Callable

from fastapi import FastAPI

from .contracts import translate_legacy_payload


def load_current_index_emotion():
    from stock_lab.infrastructure.database import create_database_client

    from .repository import EmotionRepository
    from .service import EmotionService

    return EmotionService(EmotionRepository(create_database_client().query)).current_index_emotion()


def load_current_hot_board_emotion(days: int):
    from stock_lab.infrastructure.database import create_database_client

    from .repository import EmotionRepository
    from .service import EmotionService

    return EmotionService(EmotionRepository(create_database_client().query)).hot_board_emotion(days=days)


def register_emotion_routes(
    app: FastAPI,
    *,
    index_loader: Callable[[], dict] = load_current_index_emotion,
    hot_board_loader: Callable[[int], dict] = load_current_hot_board_emotion,
) -> None:
    @app.get("/api/v1/emotion/current")
    def get_current_emotion():
        return translate_legacy_payload(index_loader())

    @app.get("/api/v1/emotion/hot-boards")
    def get_hot_board_emotion(days: int = 30):
        return translate_legacy_payload(hot_board_loader(max(5, min(60, days))))
