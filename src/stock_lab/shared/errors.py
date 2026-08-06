class StockLabError(Exception):
    """Base class for expected application errors."""


class ConfigurationError(StockLabError):
    pass


class InfrastructureError(StockLabError):
    pass


class DataValidationError(StockLabError):
    pass


class JobExecutionError(StockLabError):
    pass


class DomainError(StockLabError):
    pass
