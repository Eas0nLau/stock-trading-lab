from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import Any, Callable

from .context import ResearchConfigurationError, ResearchSafetyError


ROOT = Path(__file__).resolve().parents[4]
STRATEGY_DIR = ROOT / "strategy"
LEGACY_CAPABILITIES = ("database", "account")


@dataclass(frozen=True, slots=True)
class StrategyMetadata:
    identifier: str
    source_name: str
    display_name: str
    entrypoint: str | None
    capabilities: tuple[str, ...]
    safety_status: str
    requires_target_date: bool


CATALOG = (
    StrategyMetadata("legacy_strategy_001", "20250113_收盘齐升.py", "20250113_收盘齐升", "strategy", LEGACY_CAPABILITIES, "unsafe_legacy", True),
    StrategyMetadata("legacy_strategy_002", "20250113_机构.py", "20250113_机构", "strategy", LEGACY_CAPABILITIES, "unsafe_legacy", True),
    StrategyMetadata("legacy_strategy_003", "20250113_量价齐升.py", "20250113_量价齐升", "strategy", LEGACY_CAPABILITIES, "unsafe_legacy", True),
    StrategyMetadata("legacy_strategy_004", "20250113_量价齐升_近20日无跌停.py", "20250113_量价齐升_近20日无跌停", "strategy", LEGACY_CAPABILITIES, "unsafe_legacy", True),
    StrategyMetadata("legacy_strategy_005", "20250725_一红定江山策略验证.py", "20250725_一红定江山策略验证", "start", LEGACY_CAPABILITIES, "unsafe_legacy", True),
    StrategyMetadata("legacy_strategy_006", "20250725_仙人指路策略验证.py", "20250725_仙人指路策略验证", "start", LEGACY_CAPABILITIES, "unsafe_legacy", True),
    StrategyMetadata("legacy_strategy_007", "20250725_止跌策略验证.py", "20250725_止跌策略验证", "start", LEGACY_CAPABILITIES, "unsafe_legacy", True),
    StrategyMetadata("legacy_strategy_008", "20250725_爆量策略验证.py", "20250725_爆量策略验证", "strategy", LEGACY_CAPABILITIES, "unsafe_legacy", True),
    StrategyMetadata("legacy_strategy_009", "20250725_趋势策略验证.py", "20250725_趋势策略验证", "start", LEGACY_CAPABILITIES, "unsafe_legacy", True),
    StrategyMetadata("legacy_strategy_010", "20250725_趋势策略验证_涨天数大于跌天数比例.py", "20250725_趋势策略验证_涨天数大于跌天数比例", "start", LEGACY_CAPABILITIES, "unsafe_legacy", True),
    StrategyMetadata("legacy_strategy_011", "20250804_grok.py", "20250804_grok", "start", LEGACY_CAPABILITIES, "unsafe_legacy", True),
    StrategyMetadata("legacy_strategy_012", "20250921_临近突破左侧前高_策略验证.py", "20250921_临近突破左侧前高_策略验证", "strategy", LEGACY_CAPABILITIES, "unsafe_legacy", True),
    StrategyMetadata("legacy_strategy_013", "20250921_强更强策略验证.py", "20250921_强更强策略验证", "start", LEGACY_CAPABILITIES, "unsafe_legacy", True),
    StrategyMetadata("legacy_strategy_014", "20250921_突破左侧前高_策略验证.py", "20250921_突破左侧前高_策略验证", "start", LEGACY_CAPABILITIES, "unsafe_legacy", True),
    StrategyMetadata("legacy_strategy_015", "20250921_缩量策略验证.py", "20250921_缩量策略验证", "start", LEGACY_CAPABILITIES, "unsafe_legacy", True),
    StrategyMetadata("legacy_strategy_016", "20251112_策略验证.py", "20251112_策略验证", "strategy", LEGACY_CAPABILITIES, "unsafe_legacy", True),
    StrategyMetadata("legacy_strategy_017", "20260406_grok.py", "20260406_grok", "strategy", LEGACY_CAPABILITIES, "unsafe_legacy", True),
    StrategyMetadata("legacy_strategy_018", "20260406_grok_止跌_20100101_20260430_不卡龙虎榜_1809.py", "20260406_grok_止跌_20100101_20260430_不卡龙虎榜_1809", "strategy", LEGACY_CAPABILITIES, "unsafe_legacy", True),
    StrategyMetadata("legacy_strategy_019", "20260406_grok_止跌_20150101_20260430_不卡龙虎榜.py", "20260406_grok_止跌_20150101_20260430_不卡龙虎榜", "strategy", LEGACY_CAPABILITIES, "unsafe_legacy", True),
    StrategyMetadata("legacy_strategy_020", "20260406_grok_止跌_20200101_20200101_去除当日放量_82.py", "20260406_grok_止跌_20200101_20200101_去除当日放量_82", "strategy", LEGACY_CAPABILITIES, "unsafe_legacy", True),
    StrategyMetadata("legacy_strategy_021", "20260406_grok_止跌_20200101_20200101_叠加五分k.py", "20260406_grok_止跌_20200101_20200101_叠加五分k", "strategy", ("database", "account", "intraday_5m"), "unsafe_legacy", True),
    StrategyMetadata("legacy_strategy_022", "20260406_grok_止跌_20200101_20260430_146.9.py", "20260406_grok_止跌_20200101_20260430_146.9", "strategy", LEGACY_CAPABILITIES, "unsafe_legacy", True),
    StrategyMetadata("legacy_strategy_023", "20260406_grok_止跌_20200101_20260430_不卡龙虎榜_161.py", "20260406_grok_止跌_20200101_20260430_不卡龙虎榜_161", "strategy", LEGACY_CAPABILITIES, "unsafe_legacy", True),
    StrategyMetadata("legacy_strategy_024", "20260406_grok_止跌_20260401_20260430_不卡龙虎榜.py", "20260406_grok_止跌_20260401_20260430_不卡龙虎榜", "strategy", LEGACY_CAPABILITIES, "unsafe_legacy", True),
    StrategyMetadata("legacy_strategy_025", "20260406_grok_止跌_模板.py", "20260406_grok_止跌_模板", "strategy", LEGACY_CAPABILITIES, "unsafe_legacy", True),
    StrategyMetadata("legacy_strategy_026", "20260406_grok_止跌_模板_20150101_20260101_258.59.py", "20260406_grok_止跌_模板_20150101_20260101_258.59", "strategy", LEGACY_CAPABILITIES, "unsafe_legacy", True),
    StrategyMetadata("legacy_strategy_027", "20260406_grok_止跌_模板_20150101_20260101_不卡龙虎榜.py", "20260406_grok_止跌_模板_20150101_20260101_不卡龙虎榜", "strategy", LEGACY_CAPABILITIES, "unsafe_legacy", True),
    StrategyMetadata("legacy_strategy_028", "20260406_grok_止跌_模板_20160101_20260101_26.98.py", "20260406_grok_止跌_模板_20160101_20260101_26.98", "strategy", LEGACY_CAPABILITIES, "unsafe_legacy", True),
    StrategyMetadata("legacy_strategy_029", "20260406_grok_止跌_模板_20230101_20260101_162.47.py", "20260406_grok_止跌_模板_20230101_20260101_162.47", "strategy", LEGACY_CAPABILITIES, "unsafe_legacy", True),
    StrategyMetadata("legacy_strategy_030", "20260406_grok_止跌_模板_20250101_20260101_.py", "20260406_grok_止跌_模板_20250101_20260101_", "strategy", LEGACY_CAPABILITIES, "unsafe_legacy", True),
    StrategyMetadata("legacy_strategy_031", "20260406_grok_止跌_模板_20250101_20260101_58.py", "20260406_grok_止跌_模板_20250101_20260101_58", "strategy", LEGACY_CAPABILITIES, "unsafe_legacy", True),
    StrategyMetadata("legacy_strategy_032", "20260406_grok_止跌_模板_20250101_20260101_61.py", "20260406_grok_止跌_模板_20250101_20260101_61", "strategy", LEGACY_CAPABILITIES, "unsafe_legacy", True),
    StrategyMetadata("legacy_strategy_033", "20260406_grok_止跌_模板_20250101_20260101_79.9.py", "20260406_grok_止跌_模板_20250101_20260101_79.9", "strategy", LEGACY_CAPABILITIES, "unsafe_legacy", True),
    StrategyMetadata("legacy_strategy_034", "20260407_异动.py", "20260407_异动", "strategy", LEGACY_CAPABILITIES, "unsafe_legacy", True),
    StrategyMetadata("legacy_strategy_035", "20260502_新高.py", "20260502_新高", "strategy", LEGACY_CAPABILITIES, "unsafe_legacy", True),
    StrategyMetadata("legacy_strategy_036", "20260502_新高_历史新高_近20日最大量为近100日最大量.py", "20260502_新高_历史新高_近20日最大量为近100日最大量", "strategy", LEGACY_CAPABILITIES, "unsafe_legacy", True),
    StrategyMetadata("legacy_strategy_037", "20260502_新高_历史新高_近20日最大量为近100日最大量_20240101_20240901.py", "20260502_新高_历史新高_近20日最大量为近100日最大量_20240101_20240901", "strategy", LEGACY_CAPABILITIES, "unsafe_legacy", True),
    StrategyMetadata("legacy_strategy_038", "20260502_新高_历史新高_近20日最大量为近100日最大量_20240901_20270901.py", "20260502_新高_历史新高_近20日最大量为近100日最大量_20240901_20270901", "strategy", LEGACY_CAPABILITIES, "unsafe_legacy", True),
    StrategyMetadata("legacy_strategy_039", "20260502_新高_近日新高_近20日最大量为近100日最大量_20240901_20270901.py", "20260502_新高_近日新高_近20日最大量为近100日最大量_20240901_20270901", "strategy", LEGACY_CAPABILITIES, "unsafe_legacy", True),
    StrategyMetadata("legacy_strategy_040", "20260609_龙头缩量收红策略.py", "20260609_龙头缩量收红策略", "strategy", ("database", "account", "dragon_tiger"), "unsafe_legacy", True),
    StrategyMetadata("legacy_strategy_041", "20260616_市值100亿前日成交额360日新高策略.py", "20260616_市值100亿前日成交额360日新高策略", "strategy", LEGACY_CAPABILITIES, "unsafe_legacy", True),
    StrategyMetadata("legacy_strategy_042", "20260617_资金流向935回测.py", "20260617_资金流向935回测", "strategy", LEGACY_CAPABILITIES, "unsafe_legacy", True),
    StrategyMetadata("legacy_strategy_043", "20260619_今年80收益策略.py", "20260619_今年80收益策略", "strategy", LEGACY_CAPABILITIES, "unsafe_legacy", True),
    StrategyMetadata("legacy_strategy_044", "20260628_20240520_20240919_趋势强势最佳策略.py", "20260628_20240520_20240919_趋势强势最佳策略", "strategy", LEGACY_CAPABILITIES, "unsafe_legacy", True),
    StrategyMetadata("legacy_strategy_045", "20260629_强趋势龙头加速增强策略.py", "20260629_强趋势龙头加速增强策略", "strategy", LEGACY_CAPABILITIES, "unsafe_legacy", True),
    StrategyMetadata("legacy_strategy_046", "20260629_连续3日站上MA5近250日新高策略.py", "20260629_连续3日站上MA5近250日新高策略", "strategy", LEGACY_CAPABILITIES, "unsafe_legacy", True),
    StrategyMetadata("legacy_strategy_047", "20260706_三连阳趋势均线多头策略.py", "20260706_三连阳趋势均线多头策略", "strategy", LEGACY_CAPABILITIES, "unsafe_legacy", True),
    StrategyMetadata("legacy_strategy_048", "kdj.py", "kdj", "strategy", ("database", "account", "kdj"), "unsafe_legacy", True),
    StrategyMetadata("legacy_strategy_049", "kdj根据kdj卖出.py", "kdj根据kdj卖出", "strategy", ("database", "account", "kdj"), "unsafe_legacy", True),
    StrategyMetadata("legacy_strategy_050", "玉柱.py", "玉柱", "start", LEGACY_CAPABILITIES, "unsafe_legacy", True),
    StrategyMetadata("strategy_demo", "策略Demo.py", "策略Demo", "strategy", LEGACY_CAPABILITIES, "unsafe_legacy", True),
    StrategyMetadata("legacy_strategy_052", "龙虎榜_动态资金分仓_可重复买入_最大5个仓位_每个仓位总资产五分之一_3跟5分k判断.py", "龙虎榜_动态资金分仓_可重复买入_最大5个仓位_每个仓位总资产五分之一_3跟5分k判断", "start", ("database", "account", "dragon_tiger", "intraday_5m"), "unsafe_legacy", True),
    StrategyMetadata("legacy_strategy_053", "龙虎榜_动态资金分仓_可重复买入_最大5个仓位_每个仓位总资产五分之一_winner.py", "龙虎榜_动态资金分仓_可重复买入_最大5个仓位_每个仓位总资产五分之一_winner", "strategy", ("database", "account", "dragon_tiger"), "unsafe_legacy", True),
    StrategyMetadata("legacy_strategy_054", "龙虎榜_固定资金分仓_不可重复买入.py", "龙虎榜_固定资金分仓_不可重复买入", "start", ("database", "account", "dragon_tiger"), "unsafe_legacy", True),
    StrategyMetadata("legacy_strategy_055", "龙虎榜_固定资金分仓_可重复买入.py", "龙虎榜_固定资金分仓_可重复买入", "start", ("database", "account", "dragon_tiger"), "unsafe_legacy", True),
    StrategyMetadata("legacy_strategy_056", "龙虎榜_基础.py", "龙虎榜_基础", "start", ("database", "account", "dragon_tiger"), "unsafe_legacy", True),
    StrategyMetadata("legacy_strategy_057", "龙虎榜_明日遴选.py", "龙虎榜_明日遴选", None, ("database", "dragon_tiger"), "unsupported", False),
)


@dataclass(slots=True)
class StrategyEntry:
    metadata: StrategyMetadata
    loader: Callable[[], Any] | None = None

    @property
    def identifier(self):
        return self.metadata.identifier

    @property
    def display_name(self):
        return self.metadata.display_name

    @property
    def source_path(self):
        return STRATEGY_DIR / self.metadata.source_name

    def _load(self):
        if self.loader is not None:
            return self.loader()
        module_name = f"stock_lab_legacy_{self.identifier}"
        spec = spec_from_file_location(module_name, self.source_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"cannot load strategy {self.source_path}")
        module = module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def run(self, context):
        if self.metadata.safety_status != "context_aware":
            raise ResearchSafetyError(
                f"strategy {self.identifier} has safety status {self.metadata.safety_status}; blocked before import"
            )
        if self.metadata.entrypoint != "run":
            raise ResearchConfigurationError(
                f"context-aware strategy {self.identifier} must declare the run entrypoint"
            )
        if self.metadata.requires_target_date:
            validate_target_date(context.parameters.get("target_date"))
        module = self._load()
        runner = getattr(module, self.metadata.entrypoint, None)
        if not callable(runner):
            raise ResearchConfigurationError(
                f"strategy {self.identifier} does not define declared entrypoint {self.metadata.entrypoint}"
            )
        return runner(context)


def validate_target_date(value):
    if value is None:
        raise ResearchConfigurationError("target_date is required")
    try:
        datetime.strptime(str(int(value)), "%Y%m%d")
    except (TypeError, ValueError) as error:
        raise ResearchConfigurationError("target_date must be a valid YYYYMMDD date") from error


@lru_cache(maxsize=1)
def discover_strategies() -> tuple[StrategyEntry, ...]:
    return tuple(StrategyEntry(metadata) for metadata in CATALOG)


def get_strategy(identifier: str) -> StrategyEntry | None:
    return next((entry for entry in discover_strategies() if entry.identifier == identifier), None)
