from dataclasses import dataclass
from typing import Any


class ResearchSafetyError(RuntimeError):
    """Raised when research execution would use an unapproved live capability."""


class _DisabledCapability:
    def __getattr__(self, name):
        raise ResearchSafetyError(f"research capability {name!r} is disabled")


@dataclass(slots=True)
class ResearchContext:
    """All external capabilities required by a strategy, supplied by its caller."""

    market_data: Any
    dragon_tiger: Any = None
    account: Any = None
    network: Any = None
    parameters: dict[str, Any] | None = None

    def __post_init__(self):
        if self.parameters is None:
            self.parameters = {}
        if self.dragon_tiger is None:
            self.dragon_tiger = _DisabledCapability()
        if self.account is None:
            self.account = _DisabledCapability()
        if self.network is None:
            self.network = _DisabledCapability()

    @classmethod
    def test_context(cls, market_data=None):
        return cls(market_data or _DisabledCapability())

    def require_network(self):
        if isinstance(self.network, _DisabledCapability):
            raise ResearchSafetyError("network access must be explicitly injected")
        return self.network
