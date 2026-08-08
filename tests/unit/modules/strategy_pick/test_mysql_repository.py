import json

import pytest

from stock_lab.modules.strategy_pick.mysql_repository import StrategyPickMySQLRepository


class Cursor:
    def __init__(self, result_sets=None, fail_on=None):
        self.result_sets = list(result_sets or [])
        self.rows = []
        self.calls = []
        self.lastrowid = 41
        self.fail_on = fail_on

    def execute(self, statement, params=None):
        self.calls.append((statement, params))
        if self.fail_on and self.fail_on in statement:
            raise RuntimeError("database write failed")
        self.rows = list(self.result_sets.pop(0)) if self.result_sets else []

    def executemany(self, statement, params):
        values = list(params)
        self.calls.append((statement, values))
        if self.fail_on and self.fail_on in statement:
            raise RuntimeError("database write failed")

    def fetchone(self):
        return self.rows.pop(0) if self.rows else None

    def fetchall(self):
        return self.rows

    def close(self):
        pass


class Connection:
    def __init__(self, result_sets=None, fail_on=None):
        self.cursor_instance = Cursor(result_sets, fail_on)
        self.commits = 0
        self.rollbacks = 0
        self.closed = 0

    def cursor(self, **_kwargs):
        return self.cursor_instance

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed += 1


def test_save_strategies_upserts_json_definitions_and_removes_only_definitions():
    connection = Connection()
    repository = StrategyPickMySQLRepository(lambda: connection)
    strategies = [{
        "id": "eastmoney_1",
        "name": "New highs",
        "pageUrl": "https://example.test",
        "listenTargets": ["/api/search"],
        "enabled": True,
    }]

    repository.save_strategies(strategies)

    statements = [call[0] for call in connection.cursor_instance.calls]
    assert connection.commits == 1
    assert "ON DUPLICATE KEY UPDATE" in statements[0]
    assert "DELETE FROM strategy_definitions" in statements[1]
    assert json.loads(connection.cursor_instance.calls[0][1][-1])["listenTargets"] == ["/api/search"]


def test_save_collection_upserts_snapshot_stocks_and_events_in_one_transaction():
    connection = Connection(result_sets=[[], [{"snapshot_id": 41}]])
    repository = StrategyPickMySQLRepository(lambda: connection)
    snapshot = {
        "strategyId": "eastmoney_1",
        "collectedDate": "20260807",
        "collectedTime": "10:05:00",
        "status": "success",
        "stocks": [{"code": "600000", "name": "Pudong Bank"}],
    }

    snapshot_id = repository.save_collection(snapshot, [{"eventId": "evt-1", "code": "600000"}])

    statements = [call[0] for call in connection.cursor_instance.calls]
    assert snapshot_id == 41
    assert connection.commits == 1
    assert any("ON DUPLICATE KEY UPDATE" in statement and "strategy_pick_snapshots" in statement for statement in statements)
    assert any("strategy_pick_stocks" in statement for statement in statements)
    assert any("strategy_pick_events" in statement for statement in statements)


def test_save_collection_rolls_back_every_fact_when_an_event_write_fails():
    connection = Connection(result_sets=[[], [{"snapshot_id": 41}]], fail_on="strategy_pick_events")
    repository = StrategyPickMySQLRepository(lambda: connection)
    snapshot = {
        "strategyId": "eastmoney_1",
        "collectedDate": "20260807",
        "collectedTime": "10:05:00",
        "status": "success",
        "stocks": [],
    }

    with pytest.raises(RuntimeError, match="database write failed"):
        repository.save_collection(snapshot, [{"eventId": "evt-1", "code": "600000"}])

    assert connection.commits == 0
    assert connection.rollbacks == 1


def test_reads_reconstruct_strategy_snapshots_dates_and_events():
    strategy_json = json.dumps({"id": "eastmoney_1", "name": "New highs"})
    snapshot_json = json.dumps({
        "strategyId": "eastmoney_1",
        "collectedDate": "20260807",
        "collectedTime": "10:05:00",
        "stocks": [],
    })
    event_json = json.dumps({"eventId": "evt-1", "strategyId": "eastmoney_1"})
    connection = Connection(result_sets=[
        [{"definition_json": strategy_json}],
        [{"snapshot_json": snapshot_json}],
        [{"snapshot_json": snapshot_json}],
        [{"collected_date": 20260807}],
        [{"event_json": event_json}],
        [{"event_json": event_json}],
    ])
    repository = StrategyPickMySQLRepository(lambda: connection)

    assert repository.strategies() == [{"id": "eastmoney_1", "name": "New highs"}]
    assert repository.latest("eastmoney_1")["collectedTime"] == "10:05:00"
    assert len(repository.history("eastmoney_1", "20260807")) == 1
    assert repository.dates("eastmoney_1") == ["20260807"]
    assert repository.events("eastmoney_1", "20260807")[0]["eventId"] == "evt-1"
    assert repository.global_events("20260807")[0]["strategyId"] == "eastmoney_1"
