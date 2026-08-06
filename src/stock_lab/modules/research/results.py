from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class SelectionResult:
    strategy_id: str
    display_name: str
    target_date: int
    rows: list[dict]
    diagnostics: dict = field(default_factory=dict)

    def to_dict(self):
        return {
            "strategy_id": self.strategy_id,
            "display_name": self.display_name,
            "target_date": self.target_date,
            "rows": self.rows,
            "diagnostics": self.diagnostics,
        }


@dataclass(frozen=True, slots=True)
class BacktestResult:
    strategy_id: str
    start_date: int
    end_date: int
    selections: list[SelectionResult]
    trades: list[dict]
    summary: dict

    def to_dict(self):
        return {
            "strategy_id": self.strategy_id,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "selections": [selection.to_dict() for selection in self.selections],
            "trades": self.trades,
            "summary": self.summary,
        }
