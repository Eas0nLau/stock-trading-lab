from __future__ import annotations

import pytest

from stock_lab.jobs import jiuyan_compatibility
from task import _5_韭研公社异动 as legacy


@pytest.mark.parametrize(
    ("public_name", "delegate_name", "args", "expected"),
    [
        ("等待请求频率", "_wait_for_request_slot", (), "waited"),
        ("格式化页面日期", "_format_page_date", (20260805,), "formatted"),
        ("解析异动响应", "_parse_response", ({}, 20260805), "parsed"),
        ("韭研公社异动采集", "_collect_jiuyan_actions", (20260805,), "collected"),
        ("导出韭研公社异动板块", "_export_jiuyan_actions", (20260805,), "exported"),
        ("日内前排", "_front_rank_summary", (20260805,), "ranked"),
    ],
)
def test_legacy_names_are_pure_forwards(
    monkeypatch, public_name, delegate_name, args, expected
) -> None:
    monkeypatch.setattr(legacy, delegate_name, lambda *call_args: expected)

    assert getattr(legacy, public_name)(*args) == expected


def test_cli_requires_explicit_date() -> None:
    with pytest.raises(SystemExit):
        jiuyan_compatibility.run_cli([])


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (["--date", "20260805"], "collect"),
        (["--date", "20260805", "--export-only"], "export"),
        (["--date", "20260805", "--front-rank"], "rank"),
    ],
)
def test_cli_selects_exactly_one_mode(argv, expected, capsys) -> None:
    calls = []

    result = jiuyan_compatibility.run_cli(
        argv,
        collector=lambda date: calls.append(("collect", date)) or {"status": "success"},
        exporter=lambda date: calls.append(("export", date)) or [],
        front_rank=lambda date: calls.append(("rank", date)) or {"trade_date": date},
    )

    assert result == 0
    assert calls == [(expected, 20260805)]
    assert capsys.readouterr().out


def test_cli_modes_are_mutually_exclusive() -> None:
    with pytest.raises(SystemExit):
        jiuyan_compatibility.run_cli(
            ["--date", "20260805", "--export-only", "--front-rank"]
        )
