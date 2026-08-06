import stock_lab.modules.research.cli as research_cli
from stock_lab.modules.research.cli import main
from stock_lab.modules.research.context import ResearchContext


def test_cli_list_uses_english_identifiers_and_chinese_display_names(capsys):
    assert main(["list"]) == 0
    output = capsys.readouterr().out
    assert "strategy_demo" in output
    assert "策略Demo" in output


def test_cli_run_requires_explicit_non_live_context():
    assert main(["run", "strategy_demo"]) != 0


def test_cli_returns_controlled_error_for_unsafe_legacy_strategy(capsys):
    assert main(["run", "strategy_demo", "--target-date", "20260102"], context=ResearchContext.test_context()) == 2
    assert "safety" in capsys.readouterr().err.lower()


def test_cli_returns_controlled_error_for_invalid_target_date(capsys):
    assert main(["run", "strategy_demo", "--target-date", "20260231"], context=ResearchContext.test_context()) == 2
    assert "target_date" in capsys.readouterr().err


def test_cli_preserves_target_date_already_in_context(monkeypatch):
    received = []
    entry = type("Entry", (), {"run": lambda self, context: received.append(context.parameters["target_date"])})()
    monkeypatch.setattr(research_cli, "get_strategy", lambda identifier: entry)

    context = ResearchContext.test_context(parameters={"target_date": 20260102})
    assert main(["run", "safe"], context=context) == 0
    assert received == [20260102]


def test_cli_catches_import_errors(monkeypatch, capsys):
    entry = type("Entry", (), {"run": lambda self, context: (_ for _ in ()).throw(ImportError("missing adapter"))})()
    monkeypatch.setattr(research_cli, "get_strategy", lambda identifier: entry)

    assert main(["run", "broken"], context=ResearchContext.test_context()) == 2
    assert "missing adapter" in capsys.readouterr().err
