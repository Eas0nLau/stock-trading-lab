from __future__ import annotations

import importlib

import pytest

from stock_lab.jobs import emotion_compatibility


@pytest.mark.parametrize(
    ("module_name", "delegate_name"),
    [
        ("task._8_指数情绪周期每日更新", "_backfill_index_emotion"),
        ("task._9_热门板块情绪每日更新", "_backfill_hot_board_emotion"),
    ],
)
def test_emotion_task_names_forward_exact_dates(
    monkeypatch, module_name, delegate_name
) -> None:
    module = importlib.import_module(module_name)
    calls = []
    monkeypatch.setattr(
        module,
        delegate_name,
        lambda start_date=None, end_date=None: calls.append((start_date, end_date))
        or {"status": "success"},
    )

    assert module.更新(20260806, 20260804)["status"] == "success"
    assert module.update()["status"] == "success"
    assert module.main(20260805, None)["status"] == "success"
    assert calls == [(20260806, 20260804), (None, None), (20260805, None)]


@pytest.mark.parametrize(
    ("runner", "argv", "expected_exit"),
    [
        (emotion_compatibility.run_index_cli, [], 0),
        (
            emotion_compatibility.run_index_cli,
            ["--start-date", "20260806", "--end-date", "20260804"],
            1,
        ),
        (emotion_compatibility.run_hot_board_cli, ["--start-date", "20260805"], 0),
    ],
)
def test_emotion_cli_forwards_dates_prints_json_and_maps_status(
    runner, argv, expected_exit, capsys
) -> None:
    calls = []

    def backfill(start_date=None, end_date=None):
        calls.append((start_date, end_date))
        return {
            "status": "failed" if expected_exit else "success",
            "updated": 0,
        }

    assert runner(argv, backfill=backfill) == expected_exit
    expected = (
        int(argv[1]) if "--start-date" in argv else None,
        int(argv[3]) if "--end-date" in argv else None,
    )
    assert calls == [expected]
    assert '"status"' in capsys.readouterr().out


def test_emotion_task_imports_have_no_runtime_side_effects(monkeypatch) -> None:
    monkeypatch.setattr(
        "stock_lab.infrastructure.database.create_database_client",
        lambda: (_ for _ in ()).throw(AssertionError("database opened during import")),
    )

    importlib.reload(importlib.import_module("task._8_指数情绪周期每日更新"))
    importlib.reload(importlib.import_module("task._9_热门板块情绪每日更新"))
