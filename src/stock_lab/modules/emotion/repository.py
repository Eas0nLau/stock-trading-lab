class EmotionRepository:
    def __init__(self, query):
        self._query = query

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
