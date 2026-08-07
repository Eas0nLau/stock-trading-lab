from decimal import Decimal

from stock_lab.modules.fund_flow.mysql_repository import FundFlowMySQLRepository


class Cursor:
    def __init__(self):
        self.calls = []
        self.lastrowid = 17
        self.rowcount = 1
        self.rows = []

    def execute(self, statement, params=None):
        self.calls.append((statement, params))

    def executemany(self, statement, params):
        self.calls.append((statement, list(params)))

    def fetchone(self):
        return self.rows.pop(0) if self.rows else None

    def fetchall(self):
        return self.rows

    def close(self):
        pass


class Connection:
    def __init__(self):
        self.cursor_instance = Cursor()
        self.commits = 0

    def cursor(self, **kwargs):
        return self.cursor_instance

    def commit(self):
        self.commits += 1

    def rollback(self):
        pass

    def close(self):
        pass


def test_save_snapshot_uses_bound_parameters_and_commits():
    connection = Connection()
    repository = FundFlowMySQLRepository(lambda: connection)

    snapshot_id = repository.save_snapshot(
        "industry", 20260807, "10:00:00", [{"board_code": "A", "board_name": "机器人", "leader": "甲", "net_inflow_100m": "4.111302"}]
    )

    assert snapshot_id == 17
    assert connection.commits == 1
    assert len(connection.cursor_instance.calls) == 3
    assert all(params for _statement, params in connection.cursor_instance.calls)
    insert_params = connection.cursor_instance.calls[2][1][0]
    assert Decimal("4.111302") in insert_params


def test_save_snapshot_reuses_existing_snapshot_id():
    connection = Connection()
    connection.cursor_instance.rows = [{"snapshot_id": 9}]
    repository = FundFlowMySQLRepository(lambda: connection)

    assert repository.save_snapshot("industry", 20260807, "10:00:00", []) == 9
    assert len(connection.cursor_instance.calls) == 1
