"""Official, dependency-injected research and backtesting APIs."""

from .backtest import aggregate_results, next_trade_date, position_size, summarize_returns
from .context import ResearchConfigurationError, ResearchContext, ResearchSafetyError
from .data import ResearchData

__all__ = [
    "ResearchConfigurationError",
    "ResearchContext",
    "ResearchData",
    "ResearchSafetyError",
    "aggregate_results",
    "next_trade_date",
    "position_size",
    "summarize_returns",
]
