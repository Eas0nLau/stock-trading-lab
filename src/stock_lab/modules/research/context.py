from dataclasses import dataclass
from typing import Any


class ResearchSafetyError(RuntimeError):
    """Raised when research execution would use an unapproved live capability."""


class ResearchConfigurationError(ValueError):
    """Raised when a strategy cannot run with the supplied configuration."""


class DisabledCapability:
    def __init__(self, capability: str):
        self.capability = capability

    def __getattr__(self, name):
        raise ResearchSafetyError(f"research capability {self.capability}.{name} is disabled")


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
            self.dragon_tiger = DisabledCapability("dragon_tiger")
        if self.account is None:
            self.account = DisabledCapability("account")
        if self.network is None:
            self.network = DisabledCapability("network")

    @classmethod
    def test_context(cls, market_data=None, parameters=None):
        if market_data is None:
            market_data = DisabledCapability("market_data")
        return cls(market_data, parameters=parameters)

    def with_parameters(self, **parameters):
        return ResearchContext(
            market_data=self.market_data,
            dragon_tiger=self.dragon_tiger,
            account=self.account,
            network=self.network,
            parameters={**self.parameters, **parameters},
        )

    def require_network(self):
        if isinstance(self.network, DisabledCapability):
            raise ResearchSafetyError("network access must be explicitly injected")
        return self.network
