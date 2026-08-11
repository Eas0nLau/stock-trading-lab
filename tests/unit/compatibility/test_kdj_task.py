import importlib

import pytest

from stock_lab.modules.market_data.indicators import calculate_ths_kdj
from stock_lab.shared.errors import DataValidationError


def test_kdj_task_forwards_upstream_save_names(monkeypatch):
    module = importlib.import_module("task._3_kdj")
    calls = []
    monkeypatch.setattr(
        module,
        "_save_code_kdj",
        lambda ts_code, start_date=None, end_date=None, period=9: calls.append(
            ("code", ts_code, start_date, end_date, period)
        ) or 1,
    )
    monkeypatch.setattr(
        module,
        "_save_daily_kdj",
        lambda start_date=None, end_date=None, period=9: calls.append(
            ("daily", start_date, end_date, period)
        ) or 2,
    )

    assert module.save_code_kdj("000001.SZ") == 1
    assert module.save_daily_kdj(20260801, 20260807) == 2
    assert calls == [
        ("code", "000001.SZ", None, None, 9),
        ("daily", 20260801, 20260807, 9),
    ]
    assert module.calculate_ths_kdj is calculate_ths_kdj


def test_kdj_compatibility_cli_parses_range_codes_and_period(monkeypatch, capsys):
    compatibility = importlib.import_module("stock_lab.jobs.kdj_compatibility")
    calls = []

    exit_code = compatibility.run_cli(
        [
            "--start-date", "20260801",
            "--end-date", "20260807",
            "--stock-code", "000001.SZ",
            "--stock-code", "600000.SH",
            "--period", "5",
        ],
        runner=lambda start, end, stock_codes=None, period=9: calls.append(
            (start, end, stock_codes, period)
        ) or 4,
    )

    assert exit_code == 0
    assert calls == [(
        20260801,
        20260807,
        ["000001.SZ", "600000.SH"],
        5,
    )]
    assert '"updated": 4' in capsys.readouterr().out


def test_kdj_compatibility_cli_uses_latest_date_without_range(monkeypatch):
    compatibility = importlib.import_module("stock_lab.jobs.kdj_compatibility")
    calls = []

    compatibility.run_cli(
        [],
        runner=lambda start, end, stock_codes=None, period=9: calls.append(
            (start, end, stock_codes, period)
        ) or 1,
    )

    assert calls == [(None, None, None, 9)]


def test_kdj_task_cli_delegates_to_official_parser(monkeypatch):
    module = importlib.import_module("task._3_kdj")
    calls = []
    monkeypatch.setattr(
        module,
        "_run_cli",
        lambda argv=None: calls.append(argv) or 0,
    )

    assert module._cli(["--period", "5"]) == 0
    assert calls == [["--period", "5"]]


def test_kdj_save_range_rejects_reversed_dates():
    compatibility = importlib.import_module("stock_lab.jobs.kdj_compatibility")

    with pytest.raises(DataValidationError, match="range"):
        compatibility.save_daily_kdj(20260807, 20260806)
