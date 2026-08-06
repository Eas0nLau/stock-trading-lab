from collections.abc import Iterable
from math import prod


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
