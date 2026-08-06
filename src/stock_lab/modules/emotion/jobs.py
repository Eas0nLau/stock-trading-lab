import json

from sqlalchemy import text

from stock_lab.shared.errors import DataValidationError

from .contracts import translate_legacy_payload


def run_index_emotion_job(trade_date, repository=None, calculator=None, writer=None):
    repository, writer = _dependencies(repository, writer)
    if calculator is None:
        from 实时监控 import 情绪周期

        calculator = 情绪周期.计算指数周期结果

    trade_date = int(trade_date)
    index_rows = [row for row in repository.index_daily_rows(160) if int(row["trade_date"]) <= trade_date]
    market_rows = [row for row in repository.market_breadth_rows(80) if int(row["trade_date"]) <= trade_date]
    if (
        not index_rows
        or not market_rows
        or int(index_rows[-1]["trade_date"]) != trade_date
        or int(market_rows[-1]["trade_date"]) != trade_date
    ):
        raise DataValidationError(f"Missing index or market-breadth data for {trade_date}")

    legacy_index_rows = [
        {
            "日期": row.get("trade_date"),
            "开盘": row.get("open_price"),
            "收盘": row.get("close_price"),
            "最高": row.get("high_price"),
            "最低": row.get("low_price"),
            "成交额": row.get("turnover"),
            "涨跌幅": row.get("change_pct"),
        }
        for row in index_rows
    ]
    legacy_result = calculator(legacy_index_rows, market_rows)
    result = translate_legacy_payload(legacy_result)
    result.pop("status", None)
    latest_market = market_rows[-1]

    breadth_row = {
        "trade_date": trade_date,
        "stock_count": latest_market.get("total_count"),
        "advancing_count": latest_market.get("up_count"),
        "declining_count": latest_market.get("down_count"),
        "advance_over_5_count": latest_market.get("up_gt5_count"),
        "decline_over_5_count": latest_market.get("down_lt5_count"),
        "limit_up_count": latest_market.get("limit_up_count"),
        "limit_down_count": latest_market.get("limit_down_count"),
        "market_turnover": latest_market.get("amount"),
        "average_change_pct": latest_market.get("avg_pct_chg"),
    }
    index_row = _index_database_row(result)
    writer([
        ("index_market_breadth", ("trade_date",), [breadth_row]),
        ("index_emotion_daily", ("trade_date",), [index_row]),
    ])
    return 1


def run_hot_board_emotion_job(trade_date, sample_trade_date, repository=None, analyzer=None, writer=None):
    repository, writer = _dependencies(repository, writer)
    if analyzer is None:
        from utils import 热门板块情绪算法

        analyzer = 热门板块情绪算法.生成每日分析

    trade_date = int(trade_date)
    sample_trade_date = int(sample_trade_date)
    current_rows = repository.board_action_rows(trade_date)
    previous_rows = repository.board_action_rows(sample_trade_date)
    current = _group_board_actions(current_rows)
    previous = _group_board_actions(previous_rows)
    if not current or not previous:
        raise DataValidationError(f"Missing board actions for {sample_trade_date} or {trade_date}")

    stock_codes = {item["股票代码"] for rows in previous.values() for item in rows}
    raw_quotes = repository.daily_quote_rows(trade_date, stock_codes)
    legacy_quotes = {
        int(code): {
            "ts_code": int(code),
            "pre_close": row.get("previous_close"),
            "high": row.get("high_price"),
            "low": row.get("low_price"),
            "pct_chg": row.get("change_pct"),
        }
        for code, row in raw_quotes.items()
        if str(code).isdigit()
    }

    rows = []
    for board_name in sorted(set(current) | set(previous)):
        legacy_result = analyzer(
            日期=trade_date,
            板块=board_name,
            样本来源日期=sample_trade_date,
            前日股票=previous.get(board_name, []),
            当日股票=current.get(board_name, []),
            当日行情=legacy_quotes,
            前日板块数量=_board_count(previous_rows, board_name),
            当日板块数量=_board_count(current_rows, board_name),
            前日榜单数据完整=True,
            当日榜单数据完整=True,
        )
        row = translate_legacy_payload(legacy_result)
        row["decision_reasons_json"] = json.dumps(row.pop("decision_reasons", {}), ensure_ascii=False)
        rows.append(row)

    writer([("hot_board_emotion_daily", ("trade_date", "board_name"), rows)])
    return len(rows)


def _dependencies(repository, writer):
    if repository is not None and writer is not None:
        return repository, writer

    from utils import db

    from .repository import EmotionRepository

    return repository or EmotionRepository(db.mysql_localhost), writer or (lambda tables: write_tables(db.engine, tables))


def write_tables(engine, tables):
    with engine.begin() as connection:
        for table, keys, rows in tables:
            if not rows:
                continue
            columns = list(rows[0])
            updates = ", ".join(
                f"`{column}` = VALUES(`{column}`)" for column in columns if column not in keys
            )
            statement = text(
                f"INSERT INTO `{table}` ({', '.join(f'`{column}`' for column in columns)}) "
                f"VALUES ({', '.join(f':{column}' for column in columns)}) "
                f"ON DUPLICATE KEY UPDATE {updates}"
            )
            connection.execute(statement, rows)


def _index_database_row(result):
    quote = result.get("index_quote") or {}
    breadth = result.get("market_breadth") or {}
    scores = result.get("score_components") or {}
    averages = result.get("moving_averages") or {}
    slopes = result.get("moving_average_slopes") or {}
    return {
        "trade_date": result.get("trade_date"),
        "index_name": result.get("index_name", "上证指数"),
        "cycle_state": result.get("cycle_state"),
        "cycle_score": result.get("cycle_score"),
        "summary": result.get("summary"),
        "open_price": quote.get("open_price"),
        "close_price": quote.get("close_price"),
        "high_price": quote.get("high_price"),
        "low_price": quote.get("low_price"),
        "change_pct": quote.get("change_pct"),
        "index_turnover": quote.get("turnover"),
        "index_turnover_ratio": quote.get("index_turnover_ratio"),
        "market_turnover_ratio": breadth.get("turnover_ratio"),
        "ma5": averages.get("ma5"),
        "ma10": averages.get("ma10"),
        "ma20": averages.get("ma20"),
        "ma60": averages.get("ma60"),
        "ma5_slope": slopes.get("ma5"),
        "ma10_slope": slopes.get("ma10"),
        "ma20_slope": slopes.get("ma20"),
        "trend_score": scores.get("trend"),
        "breadth_score": scores.get("breadth"),
        "limit_structure_score": scores.get("limit_structure"),
        "volume_score": scores.get("volume"),
        "risk_appetite_score": scores.get("risk_appetite"),
        "market_breadth_json": json.dumps(breadth, ensure_ascii=False),
        "signals_json": json.dumps(result.get("signals") or [], ensure_ascii=False),
        "recent_trend_json": json.dumps(result.get("recent_trend") or [], ensure_ascii=False),
        "volatility_chart_json": json.dumps(result.get("volatility_chart") or [], ensure_ascii=False),
        "full_result_json": json.dumps(result, ensure_ascii=False),
    }


def _group_board_actions(rows):
    grouped = {}
    for row in rows:
        board_name = str(row.get("board_name") or "").strip()
        stock_code = str(row.get("stock_code") or "").zfill(6)
        if board_name and stock_code.isdigit():
            grouped.setdefault(board_name, {})[stock_code] = {
                "股票代码": int(stock_code),
                "股票名称": row.get("stock_name"),
            }
    return {name: list(items.values()) for name, items in grouped.items()}


def _board_count(rows, board_name):
    return max(
        [int(row.get("board_stock_count") or 0) for row in rows if row.get("board_name") == board_name]
        or [0]
    )
