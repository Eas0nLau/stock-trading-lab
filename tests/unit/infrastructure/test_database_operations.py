import pandas as pd
import pytest
import ast
from pathlib import Path
from mysql.connector.errors import OperationalError

from stock_lab.infrastructure.database.operations import execute_mysql, smart_insert_to_mysql


class FailingConnection:
    def cursor(self, **_kwargs):
        raise OperationalError("disconnected")

    def rollback(self):
        pass

    def close(self):
        pass


class Pool:
    def __init__(self):
        self.attempts = 0

    def get_connection(self):
        self.attempts += 1
        return FailingConnection()


def test_execute_mysql_stops_after_finite_disconnect_retries():
    pool = Pool()

    with pytest.raises(OperationalError):
        execute_mysql(pool, "SELECT 1", max_attempts=3, retry_interval_seconds=0)

    assert pool.attempts == 3


def test_smart_insert_stops_after_finite_write_retries(monkeypatch):
    attempts = []

    def fail_write(self, *args, **kwargs):
        attempts.append(True)
        raise RuntimeError("write failed")

    monkeypatch.setattr(pd.DataFrame, "to_sql", fail_write)

    with pytest.raises(RuntimeError, match="write failed"):
        smart_insert_to_mysql(
            pd.DataFrame([{"id": 1}]),
            "sample",
            object(),
            ["id"],
            query_exists=False,
            max_attempts=2,
            retry_interval_seconds=0,
        )

    assert len(attempts) == 2


def test_legacy_database_module_is_a_thin_compatibility_projection():
    path = Path(__file__).resolve().parents[3] / "utils" / "db.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))

    functions = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]

    assert functions == {"mysql_localhost", "read_sql"}
    assert not any(isinstance(call.func, ast.Name) and call.func.id in functions for call in calls)
