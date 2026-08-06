"""Official, dependency-injected research and backtesting APIs."""

from .backtest import aggregate_results, next_trade_date, position_size, run_backtest, summarize_returns
from .context import ResearchConfigurationError, ResearchContext, ResearchExecutionError, ResearchSafetyError
from .data import ResearchData
from .providers import OfflineResearchProvider, configured_local_context
from .results import BacktestResult, SelectionResult

__all__ = [
    "BacktestResult",
    "OfflineResearchProvider",
    "ResearchConfigurationError",
    "ResearchContext",
    "ResearchData",
    "ResearchExecutionError",
    "ResearchSafetyError",
    "SelectionResult",
    "aggregate_results",
    "configured_local_context",
    "next_trade_date",
    "position_size",
    "run_backtest",
    "summarize_returns",
]
