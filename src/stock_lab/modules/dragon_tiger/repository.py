from dataclasses import asdict, is_dataclass

from sqlalchemy import text

from stock_lab.modules.market_data.helpers import normalize_ts_code, stock_code_filter

from .models import Broker, BrokerListingHistory, BrokerTopStats, DragonTigerListing


LISTING_COLUMNS = tuple(DragonTigerListing.__dataclass_fields__)
HISTORY_COLUMNS = tuple(BrokerListingHistory.__dataclass_fields__)
BROKER_COLUMNS = tuple(Broker.__dataclass_fields__)
TOP_STATS_COLUMNS = tuple(BrokerTopStats.__dataclass_fields__)


class DragonTigerRepository:
    def __init__(self, query, engine=None):
        self._query = query
        self._engine = engine

    def trading_dates(self, start_date, end_date=None):
        conditions = ["`trade_date` >= %s"]
        params = [int(start_date)]
        if end_date is not None:
            conditions.append("`trade_date` <= %s")
            params.append(int(end_date))
        rows = self._query(
            f"SELECT DISTINCT `trade_date` FROM `daily_quotes` WHERE {' AND '.join(conditions)} ORDER BY `trade_date`",
            params=tuple(params),
            fetch=True,
        ) or []
        return [
            int(row["trade_date"])
            for row in rows
            if int(start_date) <= int(row["trade_date"]) <= (int(end_date) if end_date is not None else int(row["trade_date"]))
        ]

    def listings(self, trade_date=None, start_date=None, end_date=None, stock_codes=None):
        conditions = []
        params = []
        if trade_date is not None:
            conditions.append("`trade_date` = %s")
            params.append(int(trade_date))
        if start_date is not None:
            conditions.append("`trade_date` >= %s")
            params.append(int(start_date))
        if end_date is not None:
            conditions.append("`trade_date` <= %s")
            params.append(int(end_date))
        if stock_codes:
            code_clause, code_params = stock_code_filter(stock_codes, "stock_code")
            conditions.append(code_clause)
            params.extend(code_params)
        return self._normalize_stock_codes(
            self._select("dragon_tiger", LISTING_COLUMNS, conditions, params, "`trade_date`, `stock_code`, `data_id`")
        )

    def brokers(self):
        rows = self._select("brokers", BROKER_COLUMNS, [], [], "`broker_id`")
        return [Broker(**row) for row in rows]

    def broker_history(self, start_date=None, end_date=None, broker_ids=None):
        conditions = []
        params = []
        if start_date is not None:
            conditions.append("`trade_date` >= %s")
            params.append(int(start_date))
        if end_date is not None:
            conditions.append("`trade_date` <= %s")
            params.append(int(end_date))
        ids = sorted({str(broker_id) for broker_id in broker_ids or []})
        if ids:
            conditions.append(f"`broker_id` IN ({','.join(['%s'] * len(ids))})")
            params.extend(ids)
        return self._normalize_stock_codes(
            self._select(
                "broker_listing_history", HISTORY_COLUMNS, conditions, params,
                "`trade_date`, `broker_id`, `data_id`",
            )
        )

    def broker_top_stats(self):
        return self._select("broker_top_stats", TOP_STATS_COLUMNS, [], [], "`broker_id`")

    def upsert_listings(self, rows):
        return self._write("dragon_tiger", rows, ("data_id",))

    def upsert_broker_history(self, rows):
        return self._write("broker_listing_history", rows, ("data_id",))

    def upsert_broker_top_stats(self, rows):
        return self._write("broker_top_stats", rows, ("broker_id",))

    def upsert_brokers(self, rows):
        return self._write("brokers", rows, ("broker_id",))

    def _select(self, table, columns, conditions, params, order_by):
        column_sql = ", ".join(f"`{column}`" for column in columns)
        sql = f"SELECT {column_sql} FROM `{table}`"
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += f" ORDER BY {order_by}"
        return self._query(sql, params=tuple(params) if params else None, fetch=True) or []

    @staticmethod
    def _normalize_stock_codes(rows):
        return [
            {**row, "stock_code": normalize_ts_code(row["stock_code"])}
            if row.get("stock_code") else dict(row)
            for row in rows
        ]

    def _write(self, table, rows, keys):
        rows = [asdict(row) if is_dataclass(row) else dict(row) for row in rows]
        if not rows:
            return 0
        if table in {"dragon_tiger", "broker_listing_history"}:
            for row in rows:
                if row.get("stock_code"):
                    row["stock_code"] = normalize_ts_code(row["stock_code"])
        columns = list(rows[0])
        values = ", ".join(f":{column}" for column in columns)
        updates = ", ".join(
            f"`{column}` = VALUES(`{column}`)" for column in columns if column not in keys
        )
        suffix = f" ON DUPLICATE KEY UPDATE {updates}" if updates else ""
        statement = text(
            f"INSERT INTO `{table}` ({', '.join(f'`{column}`' for column in columns)}) "
            f"VALUES ({values}){suffix}"
        )
        with self._engine.begin() as connection:
            connection.execute(statement, rows)
        return len(rows)
