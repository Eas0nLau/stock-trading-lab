from collections import defaultdict
from datetime import date, datetime

from .contracts import normalize_net_inflow_100m


class FundFlowMySQLRepository:
    """DB-API repository for canonical fund-flow history."""

    def __init__(self, connection_factory):
        self.connection_factory = connection_factory

    def _connection(self):
        return self.connection_factory() if callable(self.connection_factory) else self.connection_factory

    def save_snapshot(self, flow_type, trade_date, collected_at, records):
        connection = self._connection()
        cursor = connection.cursor(dictionary=True)
        try:
            cursor.execute(
                "SELECT snapshot_id FROM fund_flow_snapshots WHERE flow_type=%s AND trade_date=%s AND collected_at=%s",
                (flow_type, int(trade_date), collected_at),
            )
            existing = cursor.fetchone()
            if existing:
                snapshot_id = existing["snapshot_id"]
            else:
                cursor.execute(
                    "INSERT INTO fund_flow_snapshots (flow_type, trade_date, collected_at, record_count) VALUES (%s, %s, %s, %s)",
                    (flow_type, int(trade_date), collected_at, len(records)),
                )
                snapshot_id = cursor.lastrowid
            values = []
            for record in records:
                values.append((
                    snapshot_id,
                    record.get("board_code", ""),
                    record.get("board_name", ""),
                    record.get("leader", ""),
                    normalize_net_inflow_100m(record.get("net_inflow_100m"), record.get("source_unit", "100m")),
                ))
            if values:
                cursor.executemany(
                    "INSERT INTO fund_flow_records (snapshot_id, board_code, board_name, leader, net_inflow_100m) VALUES (%s, %s, %s, %s, %s) ON DUPLICATE KEY UPDATE board_name=VALUES(board_name), leader=VALUES(leader), net_inflow_100m=VALUES(net_inflow_100m)",
                    values,
                )
            connection.commit()
            return snapshot_id
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
            connection.close()

    def has_snapshot(self, flow_type, trade_date):
        connection = self._connection()
        cursor = connection.cursor(dictionary=True)
        try:
            cursor.execute("SELECT snapshot_id FROM fund_flow_snapshots WHERE flow_type=%s AND trade_date=%s LIMIT 1", (flow_type, int(trade_date)))
            return cursor.fetchone() is not None
        finally:
            cursor.close()
            connection.close()

    def board_catalog(self, flow_type):
        connection = self._connection()
        cursor = connection.cursor(dictionary=True)
        try:
            cursor.execute(
                "SELECT DISTINCT r.board_code, r.board_name, r.leader "
                "FROM fund_flow_snapshots s "
                "JOIN fund_flow_records r ON r.snapshot_id=s.snapshot_id "
                "WHERE s.flow_type=%s "
                "ORDER BY r.board_code",
                (flow_type,),
            )
            boards = {}
            for row in cursor.fetchall():
                if row.get("board_code"):
                    board = {
                        "board_code": str(row.get("board_code") or ""),
                        "board_name": str(row.get("board_name") or ""),
                        "leader": str(row.get("leader") or ""),
                    }
                    boards[board["board_code"]] = board
            return list(boards.values())
        finally:
            cursor.close()
            connection.close()

    def history(self, flow_type, trade_date):
        connection = self._connection()
        cursor = connection.cursor(dictionary=True)
        try:
            cursor.execute(
                "SELECT s.collected_at, r.board_code, r.board_name, r.leader, r.net_inflow_100m FROM fund_flow_snapshots s JOIN fund_flow_records r ON r.snapshot_id=s.snapshot_id WHERE s.flow_type=%s AND s.trade_date=%s ORDER BY s.collected_at, r.board_code",
                (flow_type, int(trade_date)),
            )
            grouped = defaultdict(list)
            for row in cursor.fetchall():
                collected_at = row.pop("collected_at")
                time = collected_at.strftime("%H:%M:%S") if isinstance(collected_at, (datetime, date)) else str(collected_at)
                row["time"] = time
                if row.get("net_inflow_100m") is not None:
                    row["net_inflow_100m"] = float(row["net_inflow_100m"])
                grouped[time].append(row)
            return list(grouped.values()) or None
        finally:
            cursor.close()
            connection.close()

    def dates(self, flow_type):
        connection = self._connection()
        cursor = connection.cursor(dictionary=True)
        try:
            cursor.execute("SELECT DISTINCT trade_date FROM fund_flow_snapshots WHERE flow_type=%s ORDER BY trade_date", (flow_type,))
            return [str(row["trade_date"]) for row in cursor.fetchall()]
        finally:
            cursor.close()
            connection.close()
