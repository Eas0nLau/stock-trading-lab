from task import emotion_analysis


def test_index_emotion_write_delegates_to_official_job(monkeypatch):
    monkeypatch.setattr(
        emotion_analysis,
        "run_index_emotion_job",
        lambda date, **kwargs: (int(date), kwargs),
    )

    assert emotion_analysis.落库指数周期("20260805", repository="repository") == (
        20260805,
        {"repository": "repository"},
    )


def test_hot_board_write_delegates_to_official_job(monkeypatch):
    monkeypatch.setattr(
        emotion_analysis,
        "run_hot_board_emotion_job",
        lambda date, source_date, **kwargs: (int(date), int(source_date), kwargs),
    )

    assert emotion_analysis.落库热门板块情绪(
        "20260805",
        "20260804",
        repository="repository",
    ) == (20260805, 20260804, {"repository": "repository"})
