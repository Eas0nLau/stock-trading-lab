from collections.abc import Iterable
from math import prod

from stock_lab.modules.market_data.helpers import normalize_ts_code

from .results import BacktestResult


def next_trade_date(trading_dates: Iterable[int], date: int) -> int | None:
    """Return the first available trading date strictly after ``date``."""
    return next((int(candidate) for candidate in sorted(trading_dates) if int(candidate) > int(date)), None)


def summarize_returns(rows, entry_column: str, exit_column: str) -> dict:
    """Calculate per-row percentage returns and aggregate win statistics."""
    returns = ((rows[exit_column] - rows[entry_column]) / rows[entry_column] * 100).tolist()
    count = len(returns)
    return {
        "returns": returns,
        "win_rate": sum(value > 0 for value in returns) / count if count else 0.0,
        "average_return": sum(returns) / count if count else 0.0,
    }


def position_size(cash: float, price: float, lot_size: int = 100, max_allocation: float = 1.0) -> int:
    """Return the maximum whole-board-lot share count within an allocation."""
    if cash < 0:
        raise ValueError("cash cannot be negative")
    if price <= 0:
        raise ValueError("price must be positive")
    if lot_size <= 0:
        raise ValueError("lot_size must be positive")
    if not 0 < max_allocation <= 1:
        raise ValueError("max_allocation must be greater than zero and at most one")
    return int(cash * max_allocation // (price * lot_size)) * lot_size


def aggregate_results(results: Iterable[dict | None]) -> dict:
    """Aggregate strategy return lists while ignoring missing result records."""
    returns = [
        float(value)
        for result in results
        if result is not None
        for value in result.get("returns", [])
        if value is not None
    ]
    trade_count = len(returns)
    win_count = sum(value > 0 for value in returns)
    return {
        "trade_count": trade_count,
        "win_count": win_count,
        "win_rate": win_count / trade_count if trade_count else 0.0,
        "average_return": sum(returns) / trade_count if trade_count else 0.0,
        "compounded_return": (prod(1 + value / 100 for value in returns) - 1) * 100 if trade_count else 0.0,
    }


def run_backtest(entry, context_factory, start_date, end_date):
    start_date = int(start_date)
    end_date = int(end_date)
    seed_context = context_factory(start_date)
    all_dates = sorted({
        int(date)
        for date in seed_context.market_data.market_data.trading_dates(10000)
    })
    signal_dates = [date for date in all_dates if start_date <= date <= end_date]
    selections = []
    trades = []
    for signal_date in signal_dates:
        context = context_factory(signal_date)
        selection = entry.run(context)
        selections.append(selection)
        trade_date = next_trade_date(all_dates, signal_date)
        if trade_date is None:
            continue
        for row in selection.rows:
            ts_code = normalize_ts_code(row["ts_code"])
            quotes = context.market_data.daily_quotes([ts_code], trade_date, trade_date)
            if not quotes:
                continue
            quote = quotes[0]
            entry_price = quote.get("open_price")
            exit_price = quote.get("close_price")
            if entry_price in (None, 0) or exit_price is None:
                continue
            return_pct = (exit_price - entry_price) / entry_price * 100
            trades.append({
                "ts_code": ts_code,
                "signal_date": signal_date,
                "trade_date": trade_date,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "return_pct": return_pct,
            })
    summary = aggregate_results([{"returns": [trade["return_pct"] for trade in trades]}])
    return BacktestResult(entry.identifier, start_date, end_date, selections, trades, summary)
