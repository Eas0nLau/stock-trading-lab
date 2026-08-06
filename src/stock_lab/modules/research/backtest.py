from collections.abc import Iterable


def next_trade_date(trading_dates: Iterable[int], date: int) -> int | None:
    """Return the first available trading date strictly after ``date``."""
    return next((int(candidate) for candidate in sorted(trading_dates) if int(candidate) > int(date)), None)


def summarize_returns(rows, entry_column: str, exit_column: str) -> dict:
    """Calculate per-row percentage returns and aggregate win statistics."""
    returns = ((rows[exit_column] - rows[entry_column]) / rows[entry_column] * 100).tolist()
    return {
        "returns": returns,
        "win_rate": sum(value > 0 for value in returns) / len(returns) if returns else 0.0,
        "average_return": sum(returns) / len(returns) if returns else 0.0,
    }
