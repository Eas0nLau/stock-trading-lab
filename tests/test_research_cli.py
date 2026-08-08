import json

import stock_lab.modules.research.cli as research_cli
from stock_lab.modules.research.cli import main


def test_cli_list_uses_english_identifiers_and_chinese_display_names(capsys):
    assert main(["list"]) == 0
    output = capsys.readouterr().out
    assert "strategy_demo" in output
    assert "策略Demo" in output


def test_cli_runs_strategy_with_builtin_offline_provider(capsys):
    assert main(["run", "strategy_demo", "--target-date", "20260102", "--offline"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["strategy_id"] == "strategy_demo"
    assert payload["target_date"] == 20260102


def test_cli_runs_backtest_with_offline_provider(capsys):
    assert main([
        "backtest", "strategy_demo", "--start-date", "20260102",
        "--end-date", "20260102", "--offline",
    ]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["strategy_id"] == "strategy_demo"
    assert payload["summary"]["trade_count"] == 0


def test_cli_returns_controlled_local_provider_error(monkeypatch, capsys):
    monkeypatch.setattr(
        research_cli,
        "configured_local_context",
        lambda target_date: (_ for _ in ()).throw(ValueError("MYSQL_HOST is required")),
    )
    assert main(["run", "strategy_demo", "--target-date", "20260102", "--provider", "local"]) == 2
    assert "MYSQL_HOST is required" in capsys.readouterr().err


def test_cli_returns_controlled_error_for_invalid_target_date(capsys):
    assert main(["run", "strategy_demo", "--target-date", "20260231", "--offline"]) == 2
    assert "target_date" in capsys.readouterr().err
