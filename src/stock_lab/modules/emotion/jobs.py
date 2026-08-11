import json

from sqlalchemy import text

from stock_lab.modules.market_data.helpers import validated_trade_date
from stock_lab.shared.errors import DataValidationError

def run_index_emotion_job(trade_date, repository=None, calculator=None, writer=None):
    repository, writer = _dependencies(repository, writer)
    if calculator is None:
        from .index_cycle import calculate_index_cycle

        calculator = calculate_index_cycle

    trade_date = int(trade_date)
    index_rows = repository.index_daily_rows_through(trade_date, 180)
    market_rows = repository.market_breadth_rows_through(trade_date, 80)
    if (
        not index_rows
        or not market_rows
        or int(index_rows[-1]["trade_date"]) != trade_date
        or int(market_rows[-1]["trade_date"]) != trade_date
    ):
        raise DataValidationError(f"Missing index or market-breadth data for {trade_date}")

    result = calculator(index_rows, market_rows)
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
        from .hot_board import analyze_hot_board_day

        analyzer = analyze_hot_board_day

    trade_date = int(trade_date)
    sample_trade_date = int(sample_trade_date)
    expected_previous = repository.previous_trading_date(trade_date)
    if expected_previous != sample_trade_date:
        raise DataValidationError(
            f"Previous trading date mismatch: expected {expected_previous}, got {sample_trade_date}"
        )
    if not repository.jiuyan_date_complete(sample_trade_date):
        raise DataValidationError(f"Unverified Jiuyan actions for {sample_trade_date}")
    if not repository.jiuyan_date_complete(trade_date):
        raise DataValidationError(f"Unverified Jiuyan actions for {trade_date}")
    current_rows = repository.board_action_rows(trade_date)
    previous_rows = repository.board_action_rows(sample_trade_date)
    current = _group_board_actions(current_rows)
    previous = _group_board_actions(previous_rows)
    if not current or not previous:
        raise DataValidationError(f"Missing board actions for {sample_trade_date} or {trade_date}")

    stock_codes = {item["stock_code"] for rows in previous.values() for item in rows}
    raw_quotes = repository.daily_quote_rows(trade_date, stock_codes)

    rows = []
    for board_name in sorted(set(current) | set(previous)):
        row = analyzer(
            trade_date=trade_date,
            board_name=board_name,
            sample_trade_date=sample_trade_date,
            previous_stocks=previous.get(board_name, []),
            current_stocks=current.get(board_name, []),
            current_quotes=raw_quotes,
            previous_board_count=_board_count(previous_rows, board_name),
            current_board_count=_board_count(current_rows, board_name),
            previous_list_complete=True,
            current_list_complete=True,
        )
        row["decision_reasons_json"] = json.dumps(row.pop("decision_reasons", {}), ensure_ascii=False)
        rows.append(row)

    writer([("hot_board_emotion_daily", ("trade_date", "board_name"), rows)])
    return len(rows)


def backfill_index_emotion(
    start_date=None,
    end_date=None,
    *,
    repository=None,
    runner=run_index_emotion_job,
):
    repository = repository or _create_repository()
    dates = _range_dates(repository, start_date, end_date)
    result = _range_result()
    for trade_date in dates:
        try:
            result["updated"] += int(runner(trade_date, repository=repository))
            result["processed_dates"].append(trade_date)
        except Exception as error:
            result["status"] = "failed"
            result["failed_dates"].append(trade_date)
            result["errors"].append({"trade_date": trade_date, "error": str(error)})
    return result


def backfill_hot_board_emotion(
    start_date=None,
    end_date=None,
    *,
    repository=None,
    runner=run_hot_board_emotion_job,
):
    repository = repository or _create_repository()
    dates = _range_dates(repository, start_date, end_date)
    result = _range_result()
    for trade_date in dates:
        previous_trade_date = repository.previous_trading_date(trade_date)
        if previous_trade_date is None:
            continue
        try:
            result["updated"] += int(
                runner(
                    trade_date,
                    previous_trade_date,
                    repository=repository,
                )
            )
            result["processed_dates"].append(trade_date)
        except Exception as error:
            result["status"] = "failed"
            result["failed_dates"].append(trade_date)
            result["errors"].append({"trade_date": trade_date, "error": str(error)})
    return result


def _range_dates(repository, start_date, end_date):
    if start_date is None and end_date is None:
        dates = repository.trading_dates()
        if not dates:
            raise DataValidationError("No canonical trading dates are available")
        return [int(dates[-1])]
    if start_date is None:
        start_date = end_date
    if end_date is None:
        end_date = start_date
    start_date = validated_trade_date(start_date, "emotion start date")
    end_date = validated_trade_date(end_date, "emotion end date")
    if start_date > end_date:
        start_date, end_date = end_date, start_date
    dates = repository.trading_dates(start_date, end_date)
    if not dates:
        raise DataValidationError("No canonical trading dates are available")
    return sorted({int(date) for date in dates})


def _range_result():
    return {
        "status": "success",
        "updated": 0,
        "processed_dates": [],
        "failed_dates": [],
        "errors": [],
    }


def _dependencies(repository, writer):
    if repository is not None and writer is not None:
        return repository, writer

    database = None
    if repository is None:
        repository, database = _create_repository_dependencies()
    if writer is not None:
        return repository, writer

    from stock_lab.infrastructure.database import create_database_client

    database = database or create_database_client()
    return repository, lambda tables: write_tables(database.engine, tables)


def _create_repository():
    repository, _ = _create_repository_dependencies()
    return repository


def _create_repository_dependencies():
    from stock_lab.infrastructure.database import create_database_client
    from stock_lab.modules.market_data.repository import MarketDataRepository

    from .repository import EmotionRepository

    database = create_database_client()
    market_data = MarketDataRepository(database.query, database.engine)
    return EmotionRepository(database.query, market_data=market_data), database


def write_tables(engine, tables):
    with engine.begin() as connection:
        for table, keys, rows in tables:
            if not rows:
                continue
            if table == "hot_board_emotion_daily":
                trade_dates = {int(row["trade_date"]) for row in rows}
                if len(trade_dates) != 1:
                    raise DataValidationError(
                        "Hot-board replacement requires exactly one trade date"
                    )
                connection.execute(
                    text(
                        "DELETE FROM `hot_board_emotion_daily` "
                        "WHERE `trade_date` = :trade_date"
                    ),
                    {"trade_date": trade_dates.pop()},
                )
            columns = list(rows[0])
            updates = ", ".join(
                f"`{column}` = VALUES(`{column}`)" for column in columns if column not in keys
            )
            suffix = f" ON DUPLICATE KEY UPDATE {updates}" if updates else ""
            statement = text(
                f"INSERT INTO `{table}` ({', '.join(f'`{column}`' for column in columns)}) "
                f"VALUES ({', '.join(f':{column}' for column in columns)}) "
                f"{suffix}"
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
        if board_name and _is_main_board_action(row, stock_code):
            grouped.setdefault(board_name, {})[stock_code] = {
                "stock_code": stock_code,
                "stock_name": row.get("stock_name"),
            }
    return {name: list(items.values()) for name, items in grouped.items()}


def _board_count(rows, board_name):
    return max(
        [
            int(row.get("board_stock_count") or 0)
            for row in rows
            if row.get("board_name") == board_name
            and _is_main_board_action(
                row, str(row.get("stock_code") or "").zfill(6)
            )
        ]
        or [0]
    )


def _is_main_board_action(row, stock_code):
    if not stock_code.isdigit():
        return False
    numeric_code = int(stock_code)
    if not (1 <= numeric_code <= 3999 or 600000 <= numeric_code <= 609999):
        return False
    return "ST" not in str(row.get("stock_name") or "").upper()
