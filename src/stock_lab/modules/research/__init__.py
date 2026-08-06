"""Official, dependency-injected research and backtesting APIs."""

from .backtest import next_trade_date, summarize_returns
from .context import ResearchContext
from .data import ResearchData

__all__ = ["ResearchContext", "ResearchData", "next_trade_date", "summarize_returns"]
