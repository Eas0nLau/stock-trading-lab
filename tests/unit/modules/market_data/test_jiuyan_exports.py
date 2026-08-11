from __future__ import annotations

from pathlib import Path

import pytest

from stock_lab.modules.market_data import jiuyan_exports
from stock_lab.modules.market_data.jiuyan_exports import (
    export_jiuyan_actions,
    front_rank_summary,
)


class _Repository:
    def __init__(self, rows, manifest=None) -> None:
        self.rows = rows
        self.manifest = manifest or {
            "trade_date": 20260805,
            "status": "complete",
            "accepted_stock_count": len(rows),
        }

    def jiuyan_collection_day(self, trade_date):
        return self.manifest

    def jiuyan_actions_for_date(self, trade_date):
        return list(self.rows)

    def latest_complete_jiuyan_date(self):
        return 20260805


def _row(board, count, code, name, streak, time, reason=""):
    return {
        "trade_date": 20260805,
        "board_name": board,
        "board_stock_count": count,
        "stock_code": code,
        "stock_name": name,
        "board_streak": streak,
        "limit_up_at": f"2026-08-05 {time}",
        "limit_up_reason": reason,
    }


def _rows():
    return [
        _row("Robotics", 10, "000001", "One", "2天2板", "09:35:00"),
        _row("Robotics", 10, "000002", "Two", "3天2板", "09:30:00"),
        _row("Robotics", 10, "600000", "Three", "3天3板", "10:00:00"),
        _row("AI:Core", 5, "000001", "One", "2天2板", "09:35:00"),
        _row("AI:Core", 5, "000003", "Four", "", "10:30:00"),
        _row("公告", 20, "000004", "Five", "", "11:00:00"),
        _row("其他", 30, "000005", "Six", "", "11:01:00"),
        _row("新股", 40, "000006", "Seven", "", "11:02:00"),
        _row("ST板块", 100, "000007", "Eight", "", "09:31:00"),
    ]


def test_export_jiuyan_actions_is_deterministic_and_deduplicated(tmp_path: Path) -> None:
    repository = _Repository(_rows())

    first_paths = export_jiuyan_actions(20260805, repository, tmp_path)
    first_bytes = {path.name: path.read_bytes() for path in first_paths}
    second_paths = export_jiuyan_actions(20260805, repository, tmp_path)

    assert [path.name for path in first_paths] == [
        "3_Robotics.ini",
        "1_AI_Core.ini",
        "1_公告.ini",
        "1_其他.ini",
        "1_新股.ini",
        "7_全部.ini",
    ]
    assert all(path.parent == tmp_path / "韭研公社异动板块" / "20260805" for path in first_paths)
    assert not any("ST板块" in path.name for path in first_paths)
    assert first_bytes == {path.name: path.read_bytes() for path in second_paths}
    robotics = first_bytes["3_Robotics.ini"].decode("utf-8").splitlines()
    assert robotics == [
        "1 = 600000,Three",
        "2 = 000001,One",
        "3 = 000002,Two",
    ]
    ai = first_bytes["1_AI_Core.ini"].decode("utf-8")
    assert "000001,One" not in ai
    assert "000003,Four" in ai


def test_export_keeps_stale_files_when_temporary_generation_fails(
    monkeypatch, tmp_path: Path
) -> None:
    target = tmp_path / "韭研公社异动板块" / "20260805"
    target.mkdir(parents=True)
    stale = target / "stale.ini"
    stale.write_text("old", encoding="utf-8")
    original = jiuyan_exports._write_ini
    calls = 0

    def fail_second(path, rows):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("write failed")
        return original(path, rows)

    monkeypatch.setattr(jiuyan_exports, "_write_ini", fail_second)

    with pytest.raises(OSError, match="write failed"):
        export_jiuyan_actions(20260805, _Repository(_rows()), tmp_path)

    assert stale.read_text(encoding="utf-8") == "old"


def test_export_requires_complete_manifest(tmp_path: Path) -> None:
    repository = _Repository(_rows(), {"trade_date": 20260805, "status": "partial"})

    with pytest.raises(Exception, match="complete"):
        export_jiuyan_actions(20260805, repository, tmp_path)


def test_front_rank_defaults_to_latest_complete_date_and_summarizes_reasons() -> None:
    rows = [
        _row("Robotics", 2, "000001", "One", "", "09:35:00", "Reducer+Motor (note)"),
        _row("Robotics", 2, "000002", "Two", "", "09:36:00", "Reducer+Motor"),
        _row("AI", 1, "000001", "One", "", "09:35:00", "Reducer"),
        _row("ST板块", 1, "000003", "Three", "", "09:37:00", "Ignored"),
    ]

    result = front_rank_summary(repository=_Repository(rows))

    assert result == {
        "trade_date": 20260805,
        "boards": [
            {"board_name": "Robotics", "stock_count": 2},
            {"board_name": "AI", "stock_count": 1},
        ],
        "reasons": [
            {"reason": "Motor", "stock_count": 2},
            {"reason": "Reducer", "stock_count": 2},
        ],
    }
