from task import 每日更新 as daily


def test_tasks_delegates_to_official_daily_update(monkeypatch):
    monkeypatch.setattr(
        daily,
        "run_daily_update",
        lambda date, **kwargs: {"status": "success", "trade_date": int(date), "options": kwargs},
    )

    result = daily.tasks("20260805", state="state")

    assert result == {"status": "success", "trade_date": 20260805, "options": {"state": "state"}}


def test_backfill_delegates_to_official_daily_update(monkeypatch):
    monkeypatch.setattr(
        daily,
        "backfill_daily_updates",
        lambda days, **kwargs: {"status": "success", "days": days, "options": kwargs},
    )

    assert daily.backfill(5, collector="collector") == {
        "status": "success",
        "days": 5,
        "options": {"collector": "collector"},
    }
