import hashlib
import json


class StrategyPickMySQLRepository:
    """DB-API repository for authoritative strategy-pick facts."""

    def __init__(self, connection_factory):
        self.connection_factory = connection_factory

    def _connection(self):
        return self.connection_factory() if callable(self.connection_factory) else self.connection_factory

    def strategies(self):
        return self._json_rows(
            "SELECT definition_json FROM strategy_definitions ORDER BY strategy_id",
            (),
            "definition_json",
        )

    def save_strategies(self, strategies, *, replace=True):
        strategies = list(strategies)
        connection = self._connection()
        cursor = connection.cursor(dictionary=True)
        try:
            for strategy in strategies:
                payload = _json_object(strategy, "strategy definition")
                cursor.execute(
                    "INSERT INTO strategy_definitions "
                    "(strategy_id, name, page_url, enabled, definition_json) VALUES (%s, %s, %s, %s, %s) "
                    "ON DUPLICATE KEY UPDATE name=VALUES(name), page_url=VALUES(page_url), "
                    "enabled=VALUES(enabled), definition_json=VALUES(definition_json), updated_at=CURRENT_TIMESTAMP",
                    (
                        str(strategy.get("id") or ""),
                        str(strategy.get("name") or ""),
                        str(strategy.get("pageUrl") or ""),
                        bool(strategy.get("enabled", True)),
                        payload,
                    ),
                )
            ids = [str(strategy.get("id") or "") for strategy in strategies]
            if replace and ids:
                placeholders = ", ".join(["%s"] * len(ids))
                cursor.execute(
                    f"DELETE FROM strategy_definitions WHERE strategy_id NOT IN ({placeholders})",
                    tuple(ids),
                )
            elif replace:
                cursor.execute("DELETE FROM strategy_definitions", ())
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
            connection.close()

    def save_collection(self, snapshot, events):
        snapshot = dict(snapshot)
        strategy_id = str(snapshot.get("strategyId") or "")
        collected_date = int(snapshot.get("collectedDate") or 0)
        collected_time = str(snapshot.get("collectedTime") or "00:00:00")
        connection = self._connection()
        cursor = connection.cursor(dictionary=True)
        try:
            cursor.execute(
                "INSERT INTO strategy_pick_snapshots "
                "(strategy_id, collected_date, collected_time, status, snapshot_json) VALUES (%s, %s, %s, %s, %s) "
                "ON DUPLICATE KEY UPDATE status=VALUES(status), snapshot_json=VALUES(snapshot_json), "
                "updated_at=CURRENT_TIMESTAMP",
                (
                    strategy_id,
                    collected_date,
                    collected_time,
                    str(snapshot.get("status") or ""),
                    _json_object(snapshot, "strategy snapshot"),
                ),
            )
            cursor.execute(
                "SELECT snapshot_id FROM strategy_pick_snapshots "
                "WHERE strategy_id=%s AND collected_date=%s AND collected_time=%s",
                (strategy_id, collected_date, collected_time),
            )
            row = cursor.fetchone()
            if not row:
                raise RuntimeError("strategy snapshot upsert did not return an id")
            snapshot_id = row["snapshot_id"]
            cursor.execute("DELETE FROM strategy_pick_stocks WHERE snapshot_id=%s", (snapshot_id,))
            stocks = [stock for stock in snapshot.get("stocks") or [] if stock.get("code")]
            if stocks:
                cursor.executemany(
                    "INSERT INTO strategy_pick_stocks (snapshot_id, stock_code, stock_json) VALUES (%s, %s, %s) "
                    "ON DUPLICATE KEY UPDATE stock_json=VALUES(stock_json)",
                    [
                        (snapshot_id, str(stock["code"]), _json_object(stock, "strategy stock"))
                        for stock in stocks
                    ],
                )
            event_rows = []
            for event in events or []:
                event = dict(event)
                event_rows.append((
                    _event_id(event, strategy_id, collected_date),
                    strategy_id,
                    collected_date,
                    str(event.get("collectedTime") or event.get("time") or collected_time),
                    str(event.get("code") or ""),
                    snapshot_id,
                    _json_object(event, "strategy event"),
                ))
            if event_rows:
                cursor.executemany(
                    "INSERT INTO strategy_pick_events "
                    "(event_id, strategy_id, event_date, event_time, stock_code, snapshot_id, event_json) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s) "
                    "ON DUPLICATE KEY UPDATE event_json=VALUES(event_json), snapshot_id=VALUES(snapshot_id)",
                    event_rows,
                )
            connection.commit()
            return snapshot_id
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
            connection.close()

    def latest(self, strategy_id):
        rows = self._json_rows(
            "SELECT snapshot_json FROM strategy_pick_snapshots WHERE strategy_id=%s "
            "ORDER BY collected_date DESC, collected_time DESC LIMIT 1",
            (strategy_id,),
            "snapshot_json",
        )
        return rows[0] if rows else {}

    def history(self, strategy_id, date):
        return self._json_rows(
            "SELECT snapshot_json FROM strategy_pick_snapshots WHERE strategy_id=%s AND collected_date=%s "
            "ORDER BY collected_time",
            (strategy_id, int(date)),
            "snapshot_json",
        )

    def dates(self, strategy_id=None):
        if strategy_id:
            statement = (
                "SELECT DISTINCT collected_date FROM strategy_pick_snapshots "
                "WHERE strategy_id=%s ORDER BY collected_date DESC"
            )
            params = (strategy_id,)
        else:
            statement = "SELECT DISTINCT collected_date FROM strategy_pick_snapshots ORDER BY collected_date DESC"
            params = ()
        return [str(row["collected_date"]) for row in self._rows(statement, params)]

    def events(self, strategy_id, date):
        return self._json_rows(
            "SELECT event_json FROM strategy_pick_events WHERE strategy_id=%s AND event_date=%s "
            "ORDER BY event_time, event_id",
            (strategy_id, int(date)),
            "event_json",
        )

    def global_events(self, date):
        return self._json_rows(
            "SELECT event_json FROM strategy_pick_events WHERE event_date=%s "
            "ORDER BY event_time, event_id",
            (int(date),),
            "event_json",
        )

    def inventory(self):
        connection = self._connection()
        cursor = connection.cursor(dictionary=True)
        try:
            cursor.execute(
                "SELECT "
                "(SELECT COUNT(*) FROM strategy_definitions) AS strategies, "
                "(SELECT COUNT(*) FROM strategy_pick_snapshots) AS snapshots, "
                "(SELECT COUNT(*) FROM strategy_pick_stocks) AS stocks, "
                "(SELECT COUNT(*) FROM strategy_pick_events) AS events"
            )
            row = cursor.fetchone() or {}
            return {name: int(row.get(name) or 0) for name in ("strategies", "snapshots", "stocks", "events")}
        finally:
            cursor.close()
            connection.close()

    def _json_rows(self, statement, params, column):
        return [_load_json(row[column], column) for row in self._rows(statement, params)]

    def _rows(self, statement, params):
        connection = self._connection()
        cursor = connection.cursor(dictionary=True)
        try:
            cursor.execute(statement, params)
            return cursor.fetchall()
        finally:
            cursor.close()
            connection.close()


def _json_object(value, label):
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    try:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{label} is not JSON serializable") from error


def _load_json(value, label):
    if isinstance(value, dict):
        return value
    try:
        payload = json.loads(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"invalid {label}") from error
    if not isinstance(payload, dict):
        raise ValueError(f"invalid {label}")
    return payload


def _event_id(event, strategy_id, event_date):
    explicit = str(event.get("eventId") or "").strip()
    if explicit:
        return explicit[:128]
    canonical = json.dumps(event, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    digest = hashlib.sha256(f"{strategy_id}|{event_date}|{canonical}".encode("utf-8")).hexdigest()
    return f"fallback:{digest}"
