import re

from sqlalchemy import text

from stock_lab.shared.errors import DataValidationError

from .helpers import normalize_symbol, normalize_ts_code, stock_code_filter


DAILY_QUOTE_ENRICHMENT_FIELDS = frozenset({
    "total_market_value",
    "circulating_market_value",
    "free_float_shares",
    "free_float_market_value",
    "dde_net_amount",
})


class MarketDataRepository:
    def __init__(self, query, engine=None):
        self._query = query
        self._engine = engine

    def trading_dates(self, limit=160):
        rows = self._query(
            f"SELECT DISTINCT `trade_date` FROM `index_daily` ORDER BY `trade_date` DESC LIMIT {int(limit)}",
            fetch=True,
        ) or []
        return sorted({int(row["trade_date"]) for row in rows if row.get("trade_date")})

    def securities(self, market=None):
        sql = "SELECT `ts_code`, `symbol`, `name`, `area`, `industry`, `market`, `list_date`, `list_status` FROM `securities`"
        params = None
        if market:
            sql += " WHERE `market` = %s"
            params = (market,)
        sql += " ORDER BY `symbol`"
        rows = self._query(sql, params=params, fetch=True) or []
        return [self._normalize_code_row(row, include_symbol=True) for row in rows]

    def security_codes(self, market=None):
        return [row["ts_code"] for row in self.securities(market)]

    def symbol_ts_code_map(self):
        return {normalize_symbol(row["symbol"]): normalize_ts_code(row["ts_code"]) for row in self.securities()}

    def daily_quotes(self, stock_codes=None, start_date=None, end_date=None):
        conditions = []
        params = []
        if stock_codes:
            code_sql, code_params = stock_code_filter(stock_codes)
            conditions.append(code_sql)
            params.extend(code_params)
        if start_date is not None:
            conditions.append("`trade_date` >= %s")
            params.append(int(start_date))
        if end_date is not None:
            conditions.append("`trade_date` <= %s")
            params.append(int(end_date))
        sql = "SELECT `data_id`, `ts_code`, `trade_date`, `open_price`, `high_price`, `low_price`, `close_price`, `previous_close`, `change_amount`, `change_pct`, `volume`, `turnover`, `total_market_value`, `circulating_market_value`, `free_float_shares`, `free_float_market_value`, `stock_name`, `dde_net_amount` FROM `daily_quotes`"
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += " ORDER BY `trade_date`, `ts_code`"
        rows = self._query(sql, params=tuple(params) if params else None, fetch=True) or []
        return [self._normalize_code_row(row) for row in rows]

    def daily_quotes_for_date(self, trade_date, stock_codes):
        return self.daily_quotes(stock_codes, trade_date, trade_date)

    def daily_quote_dates(self, start_date=None, end_date=None):
        conditions = []
        params = []
        if start_date is not None:
            conditions.append("`trade_date` >= %s")
            params.append(int(start_date))
        if end_date is not None:
            conditions.append("`trade_date` <= %s")
            params.append(int(end_date))
        sql = "SELECT DISTINCT `trade_date` FROM `daily_quotes`"
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        rows = self._query(sql, params=tuple(params) if params else None, fetch=True) or []
        return sorted({int(row["trade_date"]) for row in rows if row.get("trade_date")})

    def index_daily(self, start_date=None, end_date=None, limit=None):
        conditions = []
        params = []
        if start_date is not None:
            conditions.append("`trade_date` >= %s")
            params.append(int(start_date))
        if end_date is not None:
            conditions.append("`trade_date` <= %s")
            params.append(int(end_date))
        columns = "`trade_date`, `open_price`, `close_price`, `high_price`, `low_price`, `volume`, `turnover`, `amplitude_pct`, `change_pct`, `change_amount`, `turnover_rate`"
        sql = f"SELECT {columns} FROM `index_daily`"
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        if limit is not None:
            sql = f"SELECT {columns} FROM (SELECT {columns} FROM `index_daily`"
            if conditions:
                sql += " WHERE " + " AND ".join(conditions)
            sql += f" ORDER BY `trade_date` DESC LIMIT {int(limit)}) AS `recent_index_daily` ORDER BY `trade_date` ASC"
        else:
            sql += " ORDER BY `trade_date` ASC"
        rows = self._query(sql, params=tuple(params) if params else None, fetch=True) or []
        return rows

    def intraday_bars_5m(self, trade_date=None, stock_code=None):
        conditions = []
        params = []
        if trade_date is not None:
            conditions.append("`trade_date` = %s")
            params.append(int(trade_date))
        if stock_code is not None:
            conditions.append("`stock_code` = %s")
            params.append(normalize_symbol(stock_code))
        sql = "SELECT `data_id`, `trade_date`, `trade_time`, `stock_code`, `open_price`, `high_price`, `low_price`, `close_price`, `volume`, `turnover`, `adjustment_flag` FROM `intraday_bars_5m`"
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += " ORDER BY `trade_time`"
        rows = self._query(sql, params=tuple(params) if params else None, fetch=True) or []
        return [self._normalize_symbol_row(row, "stock_code") for row in rows]

    @staticmethod
    def _normalize_code_row(row, include_symbol=False):
        row = dict(row)
        if row.get("ts_code") is not None:
            row["ts_code"] = normalize_ts_code(row["ts_code"])
            if include_symbol:
                row["symbol"] = normalize_symbol(row.get("symbol", row["ts_code"]))
        return row

    @staticmethod
    def _normalize_symbol_row(row, column):
        row = dict(row)
        if row.get(column) is not None:
            row[column] = normalize_symbol(row[column])
        return row

    def intraday_bars_5m_legacy(self, trade_date, stock_code):
        sql = "SELECT `trade_date` AS `date`, `trade_time` AS `time`, `stock_code` AS `code`, `open_price` AS `open`, `high_price` AS `high`, `low_price` AS `low`, `close_price` AS `close`, `volume`, `turnover` AS `amount`, `adjustment_flag` AS `adjustflag` FROM `intraday_bars_5m` WHERE `trade_date` = %s AND `stock_code` = %s ORDER BY `trade_time`"
        return self._query(
            sql, params=(int(trade_date), normalize_symbol(stock_code)), fetch=True
        ) or []

    def kdj_indicators(self, stock_codes=None, start_date=None, end_date=None):
        conditions = []
        params = []
        if stock_codes:
            code_sql, code_params = stock_code_filter(stock_codes)
            conditions.append(code_sql)
            params.extend(code_params)
        if start_date is not None:
            conditions.append("`trade_date` >= %s")
            params.append(int(start_date))
        if end_date is not None:
            conditions.append("`trade_date` <= %s")
            params.append(int(end_date))
        sql = "SELECT `data_id`, `ts_code`, `trade_date`, `k_value`, `d_value`, `j_value` FROM `kdj_indicators`"
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += " ORDER BY `trade_date`, `ts_code`"
        rows = self._query(sql, params=tuple(params) if params else None, fetch=True) or []
        return [self._normalize_code_row(row) for row in rows]

    def upsert_securities(self, rows):
        return self._write("securities", rows, ("ts_code",))

    def replace_securities(self, rows):
        rows = list(rows)
        if not rows:
            return 0
        with self._engine.begin() as connection:
            connection.execute(text("DELETE FROM `securities`"))
            self._execute_insert(connection, "securities", rows)
        return len(rows)

    def upsert_daily_quotes(self, rows):
        rows = list(rows)
        if not rows:
            return 0
        with self._engine.begin() as connection:
            self._execute_insert(
                connection,
                "daily_quotes",
                rows,
                ("data_id",),
                preserve_null_columns=DAILY_QUOTE_ENRICHMENT_FIELDS,
            )
        return len(rows)

    def update_daily_quote_enrichment(self, rows, fields, only_missing=False):
        rows = [dict(row) for row in rows]
        fields = tuple(fields)
        unsupported = set(fields) - DAILY_QUOTE_ENRICHMENT_FIELDS
        if unsupported:
            raise ValueError(
                "Unsupported daily quote enrichment fields: "
                + ", ".join(sorted(unsupported))
            )
        if not rows or not fields:
            return 0
        for row in rows:
            row["ts_code"] = normalize_ts_code(row.get("ts_code"))
            row["trade_date"] = int(row["trade_date"])
        if only_missing:
            assignments = ", ".join(
                f"`{field}` = CASE WHEN `{field}` IS NULL "
                f"THEN :{field} ELSE `{field}` END"
                for field in fields
            )
        else:
            assignments = ", ".join(
                f"`{field}` = COALESCE(:{field}, `{field}`)" for field in fields
            )
        sql = (
            f"UPDATE `daily_quotes` SET {assignments} "
            "WHERE `ts_code` = :ts_code AND `trade_date` = :trade_date"
        )
        with self._engine.begin() as connection:
            result = connection.execute(text(sql), rows)
        return max(int(result.rowcount or 0), 0)

    def upsert_index_daily(self, rows):
        return self._write("index_daily", rows, ("trade_date",))

    def upsert_intraday_bars_5m(self, rows):
        return self._write("intraday_bars_5m", rows, ("data_id",))

    def upsert_kdj_indicators(self, rows):
        return self._write("kdj_indicators", rows, ("data_id",))

    def upsert_jiuyan_actions(self, rows):
        return self._write("jiuyan_actions", rows, ("data_id",))

    def replace_jiuyan_actions(self, trade_date, rows, manifest):
        trade_date = int(trade_date)
        rows = [dict(row) for row in rows]
        manifest = dict(manifest)
        if int(manifest.get("trade_date", 0)) != trade_date:
            raise DataValidationError("Jiuyan manifest trade date does not match target")
        if manifest.get("status") != "complete":
            raise DataValidationError("Jiuyan manifest status must be complete")
        if not re.fullmatch(r"[0-9a-f]{64}", str(manifest.get("source_fingerprint", ""))):
            raise DataValidationError("Jiuyan source fingerprint must be lowercase SHA-256")
        expected_row_count = int(manifest.get("accepted_stock_count", -1))
        if expected_row_count != len(rows):
            raise DataValidationError(
                "Jiuyan expected row count does not match the validated batch"
            )
        if any(int(row.get("trade_date", 0)) != trade_date for row in rows):
            raise DataValidationError("Jiuyan batch contains a mismatched trade date")

        with self._engine.begin() as connection:
            connection.execute(
                text("DELETE FROM `jiuyan_actions` WHERE `trade_date` = :trade_date"),
                {"trade_date": trade_date},
            )
            if rows:
                self._execute_insert(connection, "jiuyan_actions", rows, ("data_id",))
            self._execute_insert(
                connection,
                "jiuyan_collection_days",
                [manifest],
                ("trade_date",),
            )
            persisted_count = int(
                connection.execute(
                    text(
                        "SELECT COUNT(*) FROM `jiuyan_actions` "
                        "WHERE `trade_date` = :trade_date"
                    ),
                    {"trade_date": trade_date},
                ).scalar_one()
            )
            if persisted_count != expected_row_count:
                raise DataValidationError(
                    f"Persisted Jiuyan count mismatch for {trade_date}"
                )
        return persisted_count

    def jiuyan_actions_for_date(self, trade_date):
        return self._query(
            "SELECT * FROM `jiuyan_actions` WHERE `trade_date` = %s "
            "ORDER BY `board_name`, `stock_code`",
            params=(int(trade_date),),
            fetch=True,
        ) or []

    def jiuyan_collection_day(self, trade_date):
        rows = self._query(
            "SELECT * FROM `jiuyan_collection_days` WHERE `trade_date` = %s",
            params=(int(trade_date),),
            fetch=True,
        ) or []
        return dict(rows[0]) if rows else None

    def latest_complete_jiuyan_date(self):
        rows = self._query(
            "SELECT MAX(`trade_date`) AS `trade_date` "
            "FROM `jiuyan_collection_days` WHERE `status` = %s",
            params=("complete",),
            fetch=True,
        ) or []
        value = rows[0].get("trade_date") if rows else None
        return int(value) if value is not None else None

    def _write(self, table, rows, keys):
        rows = list(rows)
        if not rows:
            return 0
        with self._engine.begin() as connection:
            self._execute_insert(connection, table, rows, keys)
        return len(rows)

    @staticmethod
    def _execute_insert(
        connection,
        table,
        rows,
        keys=(),
        preserve_null_columns=(),
    ):
        columns = list(rows[0])
        values = ", ".join(f":{column}" for column in columns)
        updates = ", ".join(
            (
                f"`{column}` = COALESCE(VALUES(`{column}`), `{column}`)"
                if column in preserve_null_columns
                else f"`{column}` = VALUES(`{column}`)"
            )
            for column in columns
            if column not in keys
        )
        suffix = f" ON DUPLICATE KEY UPDATE {updates}" if updates else ""
        connection.execute(
            text(f"INSERT INTO `{table}` ({', '.join(f'`{column}`' for column in columns)}) VALUES ({values}){suffix}"),
            rows,
        )
