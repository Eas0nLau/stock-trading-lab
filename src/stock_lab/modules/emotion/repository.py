class EmotionRepository:
    def __init__(self, query, market_data=None):
        self._query = query
        self._market_data = market_data

    def latest_index_emotion(self):
        rows = self._query(
            """
            SELECT
                `trade_date`, `index_name`, `cycle_state`, `cycle_score`, `summary`,
                `open_price`, `close_price`, `high_price`, `low_price`, `change_pct`,
                `index_turnover`, `index_turnover_ratio`, `market_turnover_ratio`,
                `ma5`, `ma10`, `ma20`, `ma60`, `ma5_slope`, `ma10_slope`, `ma20_slope`,
                `trend_score`, `breadth_score`, `limit_structure_score`, `volume_score`,
                `risk_appetite_score`, `market_breadth_json`, `signals_json`,
                `recent_trend_json`, `volatility_chart_json`, `full_result_json`
            FROM `index_emotion_daily`
            ORDER BY `trade_date` DESC
            LIMIT 1
            """,
            fetch=True,
        ) or []
        return rows[0] if rows else None

    def recent_hot_board_dates(self, days: int):
        return self._query(
            f"""
            SELECT DISTINCT `trade_date`
            FROM `hot_board_emotion_daily`
            ORDER BY `trade_date` DESC
            LIMIT {int(days)}
            """,
            fetch=True,
        ) or []

    def hot_board_rows(self, dates):
        if not dates:
            return []
        placeholders = ",".join(["%s"] * len(dates))
        return self._query(
            f"""
            SELECT
                `trade_date`, `board_name`, `sample_trade_date`, `previous_list_complete`,
                `current_list_complete`, `previous_board_count`, `previous_stock_pool_count`,
                `previous_detail_coverage`, `current_board_count`, `current_stock_detail_count`,
                `valid_sample_count`, `quote_coverage`, `average_change_pct`, `median_change_pct`,
                `average_amplitude_pct`, `change_stddev`, `promotion_count`, `promotion_rate`,
                `new_promotion_count`, `new_promotion_rate`, `positive_count`, `positive_rate`,
                `large_gain_count`, `large_gain_rate`, `large_loss_count`, `large_loss_rate`,
                `failed_limit_count`, `failed_limit_rate`, `retained_count`, `retained_rate`,
                `heat_stage`, `continuation_state`, `overall_status`, `emotion_score`,
                `decision_summary`, `decision_reasons_json`
            FROM `hot_board_emotion_daily`
            WHERE `trade_date` IN ({placeholders})
            ORDER BY `board_name`, `trade_date`
            """,
            params=tuple(dates),
            fetch=True,
        ) or []

    def index_daily_rows(self, limit: int):
        if self._market_data is not None:
            return list(self._market_data.index_daily(limit=limit))
        rows = self._query(
            f"""
            SELECT `trade_date`, `open_price`, `close_price`, `high_price`, `low_price`, `turnover`, `change_pct`
            FROM `index_daily`
            ORDER BY `trade_date` DESC
            LIMIT {int(limit)}
            """,
            fetch=True,
        ) or []
        return list(reversed(rows))

    def trading_dates(self, start_date=None, end_date=None):
        if self._market_data is not None:
            rows = self._market_data.index_daily(
                start_date=start_date,
                end_date=end_date,
            )
            return sorted({int(row["trade_date"]) for row in rows})
        conditions = []
        params = []
        if start_date is not None:
            conditions.append("`trade_date` >= %s")
            params.append(int(start_date))
        if end_date is not None:
            conditions.append("`trade_date` <= %s")
            params.append(int(end_date))
        sql = "SELECT DISTINCT `trade_date` FROM `index_daily`"
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += " ORDER BY `trade_date`"
        rows = self._query(
            sql,
            params=tuple(params) if params else None,
            fetch=True,
        ) or []
        return [int(row["trade_date"]) for row in rows]

    def previous_trading_date(self, trade_date):
        trade_date = int(trade_date)
        if self._market_data is not None:
            dates = self.trading_dates(end_date=trade_date)
            previous = [date for date in dates if date < trade_date]
            return previous[-1] if previous else None
        rows = self._query(
            "SELECT MAX(`trade_date`) AS `trade_date` FROM `index_daily` "
            "WHERE `trade_date` < %s",
            params=(trade_date,),
            fetch=True,
        ) or []
        value = rows[0].get("trade_date") if rows else None
        return int(value) if value is not None else None

    def index_daily_rows_through(self, end_date, limit=180):
        end_date = int(end_date)
        if self._market_data is not None:
            return list(self._market_data.index_daily(end_date=end_date, limit=limit))
        columns = "`trade_date`, `open_price`, `close_price`, `high_price`, `low_price`, `turnover`, `change_pct`"
        return self._query(
            f"SELECT {columns} FROM ("
            f"SELECT {columns} FROM `index_daily` WHERE `trade_date` <= %s "
            f"ORDER BY `trade_date` DESC LIMIT {int(limit)}"
            ") AS `recent_index_daily` ORDER BY `trade_date`",
            params=(end_date,),
            fetch=True,
        ) or []

    def market_breadth_rows(self, limit: int):
        return self._query(
            f"""
            SELECT
                `trade_date`,
                COUNT(*) AS `total_count`,
                SUM(CASE WHEN `change_pct` > 0 THEN 1 ELSE 0 END) AS `up_count`,
                SUM(CASE WHEN `change_pct` < 0 THEN 1 ELSE 0 END) AS `down_count`,
                SUM(CASE WHEN `change_pct` >= 5 THEN 1 ELSE 0 END) AS `up_gt5_count`,
                SUM(CASE WHEN `change_pct` <= -5 THEN 1 ELSE 0 END) AS `down_lt5_count`,
                SUM(CASE WHEN `previous_close` > 0 AND `close_price` >= ROUND(`previous_close` * 1.10, 2) THEN 1 ELSE 0 END) AS `limit_up_count`,
                SUM(CASE WHEN `previous_close` > 0 AND `close_price` <= ROUND(`previous_close` * 0.90, 2) THEN 1 ELSE 0 END) AS `limit_down_count`,
                SUM(`turnover`) AS `amount`,
                AVG(`change_pct`) AS `avg_pct_chg`
            FROM `daily_quotes`
            WHERE `trade_date` IN (
                SELECT `trade_date` FROM (
                    SELECT DISTINCT `trade_date`
                    FROM `daily_quotes`
                    ORDER BY `trade_date` DESC
                    LIMIT {int(limit)}
                ) AS `recent_dates`
            )
              AND (CAST(SUBSTRING_INDEX(`ts_code`, '.', 1) AS UNSIGNED) BETWEEN 1 AND 3999
                   OR CAST(SUBSTRING_INDEX(`ts_code`, '.', 1) AS UNSIGNED) BETWEEN 600000 AND 609999)
              AND (`stock_name` IS NULL OR `stock_name` NOT LIKE '%ST%')
            GROUP BY `trade_date`
            ORDER BY `trade_date`
            """,
            fetch=True,
        ) or []

    def market_breadth_rows_through(self, end_date, limit=80):
        return self._query(
            f"""
            SELECT
                `trade_date`,
                COUNT(*) AS `total_count`,
                SUM(CASE WHEN `change_pct` > 0 THEN 1 ELSE 0 END) AS `up_count`,
                SUM(CASE WHEN `change_pct` < 0 THEN 1 ELSE 0 END) AS `down_count`,
                SUM(CASE WHEN `change_pct` >= 5 THEN 1 ELSE 0 END) AS `up_gt5_count`,
                SUM(CASE WHEN `change_pct` <= -5 THEN 1 ELSE 0 END) AS `down_lt5_count`,
                SUM(CASE WHEN `previous_close` > 0 AND `close_price` >= ROUND(`previous_close` * 1.10, 2) THEN 1 ELSE 0 END) AS `limit_up_count`,
                SUM(CASE WHEN `previous_close` > 0 AND `close_price` <= ROUND(`previous_close` * 0.90, 2) THEN 1 ELSE 0 END) AS `limit_down_count`,
                SUM(`turnover`) AS `amount`,
                AVG(`change_pct`) AS `avg_pct_chg`
            FROM `daily_quotes`
            WHERE `trade_date` IN (
                SELECT `trade_date` FROM (
                    SELECT DISTINCT `trade_date`
                    FROM `daily_quotes`
                    WHERE `trade_date` <= %s
                    ORDER BY `trade_date` DESC
                    LIMIT {int(limit)}
                ) AS `recent_dates`
            )
              AND (CAST(SUBSTRING_INDEX(`ts_code`, '.', 1) AS UNSIGNED) BETWEEN 1 AND 3999
                   OR CAST(SUBSTRING_INDEX(`ts_code`, '.', 1) AS UNSIGNED) BETWEEN 600000 AND 609999)
              AND (`stock_name` IS NULL OR `stock_name` NOT LIKE '%ST%')
            GROUP BY `trade_date`
            ORDER BY `trade_date`
            """,
            params=(int(end_date),),
            fetch=True,
        ) or []

    def jiuyan_date_complete(self, trade_date):
        rows = self._query(
            """
            SELECT CASE
                WHEN `days`.`status` = 'complete'
                 AND `days`.`accepted_stock_count` = COUNT(`actions`.`data_id`)
                THEN 1 ELSE 0
            END AS `is_complete`
            FROM `jiuyan_collection_days` AS `days`
            LEFT JOIN `jiuyan_actions` AS `actions`
              ON `actions`.`trade_date` = `days`.`trade_date`
            WHERE `days`.`trade_date` = %s
            GROUP BY `days`.`trade_date`, `days`.`status`, `days`.`accepted_stock_count`
            """,
            params=(int(trade_date),),
            fetch=True,
        ) or []
        return bool(rows and rows[0].get("is_complete"))

    def board_action_rows(self, trade_date: int):
        return self._query(
            """
            SELECT `board_name`, `board_stock_count`, `stock_code`, `stock_name`
            FROM `jiuyan_actions`
            WHERE `trade_date` = %s
              AND (`stock_code` BETWEEN '000001' AND '003999'
                   OR `stock_code` BETWEEN '600000' AND '609999')
              AND (`stock_name` IS NULL OR `stock_name` NOT LIKE '%ST%')
            ORDER BY `board_name`, `stock_code`
            """,
            params=(int(trade_date),),
            fetch=True,
        ) or []

    def daily_quote_rows(self, trade_date: int, stock_codes):
        if self._market_data is not None:
            from stock_lab.modules.market_data.helpers import normalize_symbol

            rows = self._market_data.daily_quotes_for_date(trade_date, stock_codes)
            return {normalize_symbol(row.get("ts_code")): row for row in rows}
        codes = sorted({str(code).zfill(6) for code in stock_codes if code})
        if not codes:
            return {}
        placeholders = ",".join(["%s"] * len(codes))
        rows = self._query(
            f"""
            SELECT
                LPAD(SUBSTRING_INDEX(`ts_code`, '.', 1), 6, '0') AS `stock_code`,
                `previous_close`, `high_price`, `low_price`, `change_pct`
            FROM `daily_quotes`
            WHERE `trade_date` = %s
              AND LPAD(SUBSTRING_INDEX(`ts_code`, '.', 1), 6, '0') IN ({placeholders})
            """,
            params=(int(trade_date), *codes),
            fetch=True,
        ) or []
        return {row["stock_code"]: row for row in rows}
