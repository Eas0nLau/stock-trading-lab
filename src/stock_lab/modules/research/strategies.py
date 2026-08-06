from dataclasses import dataclass
from hashlib import sha1
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import re
from typing import Any, Callable
from functools import lru_cache


ROOT = Path(__file__).resolve().parents[4]
STRATEGY_DIR = ROOT / "strategy"


def _identifier(path: Path) -> str:
    if path.stem == "策略Demo":
        return "strategy_demo"
    ascii_name = re.sub(r"[^a-zA-Z0-9]+", "_", path.stem).strip("_").lower()
    digest = sha1(path.name.encode("utf-8")).hexdigest()[:8]
    return f"strategy_{ascii_name or 'legacy'}_{digest}"


@dataclass
class StrategyEntry:
    identifier: str
    display_name: str
    source_path: Path
    loader: Callable[[], Any] | None = None

    def load(self):
        if self.loader:
            return self.loader()
        module_name = f"stock_lab_legacy_{self.identifier}"
        spec = spec_from_file_location(module_name, self.source_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"cannot load strategy {self.source_path}")
        module = module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def run(self, context, **parameters):
        module = self.load()
        runner = getattr(module, "run", None)
        if callable(runner):
            return runner(context)
        options = {**getattr(context, "parameters", {}), **parameters}
        if "filtered_codes" not in options:
            options["filtered_codes"] = context.market_data.security_codes()
        runner = getattr(module, "start", None)
        if callable(runner):
            return runner(target_date=options.get("target_date"), filtered_codes=options["filtered_codes"])
        runner = getattr(module, "strategy", None)
        if callable(runner):
            if "target_date" not in options:
                raise ValueError(f"strategy {self.identifier} requires target_date")
            return runner(options["filtered_codes"], options["target_date"])
        raise TypeError(f"strategy {self.identifier} has no supported run or strategy entrypoint")


@lru_cache(maxsize=1)
def discover_strategies() -> tuple[StrategyEntry, ...]:
    return tuple(
        StrategyEntry(_identifier(path), path.stem, path)
        for path in sorted(STRATEGY_DIR.glob("*.py"))
        if path.name != "__init__.py"
    )


def get_strategy(identifier: str) -> StrategyEntry | None:
    return next((entry for entry in discover_strategies() if entry.identifier == identifier), None)
