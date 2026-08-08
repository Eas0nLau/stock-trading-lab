from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TdxSettings:
    root: Path
    refresh_interval_seconds: float = 20.0

    def __post_init__(self):
        root = Path(self.root).expanduser()
        interval = float(self.refresh_interval_seconds)
        if interval <= 0:
            raise ValueError("TDX refresh interval must be positive")
        object.__setattr__(self, "root", root)
        object.__setattr__(self, "refresh_interval_seconds", interval)

    @classmethod
    def from_settings(cls, settings):
        return cls(Path(settings.tdx_root), settings.tdx_cache_refresh_interval_seconds)


def validate_tdx_root(root: Path) -> Path:
    root = Path(root).expanduser()
    plugin = root / "PYPlugins" / "user" / "tqcenter.py"
    if not plugin.is_file():
        raise FileNotFoundError(plugin)
    return root
