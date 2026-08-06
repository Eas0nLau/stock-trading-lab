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
            return list(reversed(self._market_data.index_daily(limit=limit)))
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

    def board_action_rows(self, trade_date: int):
        return self._query(
            """
            SELECT `board_name`, `board_stock_count`, `stock_code`, `stock_name`
            FROM `jiuyan_actions`
            WHERE `trade_date` = %s
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
