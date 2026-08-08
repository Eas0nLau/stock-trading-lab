"""Compatibility entry points for canonical emotion jobs."""

from stock_lab.modules.emotion.jobs import (
    run_hot_board_emotion_job,
    run_index_emotion_job,
)


def 落库指数周期(date, **kwargs):
    return run_index_emotion_job(date, **kwargs)


def 落库热门板块情绪(date, source_date, **kwargs):
    return run_hot_board_emotion_job(date, source_date, **kwargs)
