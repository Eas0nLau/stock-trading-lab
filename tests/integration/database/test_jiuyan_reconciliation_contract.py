import json

from stock_lab.jobs import jiuyan_reconciliation


def test_cli_defaults_to_dry_run_and_prints_json(monkeypatch, capsys):
    calls = []
    report = jiuyan_reconciliation.JiuyanReconciliationReport(
        source_count=3,
        target_count=2,
        missing_count=1,
        written_count=0,
    )
    monkeypatch.setattr(jiuyan_reconciliation, "create_database_client", lambda: object(), raising=False)
    monkeypatch.setattr(
        jiuyan_reconciliation,
        "reconcile_jiuyan_data",
        lambda **kwargs: calls.append(kwargs) or report,
    )

    assert jiuyan_reconciliation.main([]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert calls == [{"database": calls[0]["database"], "write": False, "recalculate": False}]
    assert payload["missing_count"] == 1
    assert payload["written_count"] == 0


def test_cli_recalculate_requires_write_and_calls_emotion_recalculation(monkeypatch, capsys):
    database = object()
    report = jiuyan_reconciliation.JiuyanReconciliationReport(
        source_count=3,
        target_count=2,
        missing_count=1,
        written_count=1,
    )
    calls = []
    monkeypatch.setattr(jiuyan_reconciliation, "create_database_client", lambda: database, raising=False)
    monkeypatch.setattr(
        jiuyan_reconciliation,
        "reconcile_jiuyan_data",
        lambda **kwargs: calls.append(("reconcile", kwargs)) or report,
    )
    monkeypatch.setattr(
        jiuyan_reconciliation,
        "recalculate_complete_hot_board_emotion",
        lambda **kwargs: calls.append(("emotion", kwargs)) or report,
    )
    monkeypatch.setattr(jiuyan_reconciliation, "verify_jiuyan_parity", lambda _database: [])

    assert jiuyan_reconciliation.main(["--write", "--recalculate"]) == 0

    assert calls[0] == ("reconcile", {"database": database, "write": True, "recalculate": True})
    assert calls[1] == ("emotion", {"database": database, "report": report})
    assert json.loads(capsys.readouterr().out)["recalculated_dates"] == []
