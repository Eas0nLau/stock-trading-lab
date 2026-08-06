from stock_lab.modules.research.cli import main


def test_cli_list_uses_english_identifiers_and_chinese_display_names(capsys):
    assert main(["list"]) == 0
    output = capsys.readouterr().out
    assert "strategy_demo" in output
    assert "策略Demo" in output


def test_cli_run_requires_explicit_non_live_context():
    assert main(["run", "strategy_demo"]) != 0
