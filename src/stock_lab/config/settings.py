import os
from dataclasses import dataclass
from pathlib import Path

import dotenv

from . import defaults


@dataclass(frozen=True)
class MySQLSettings:
    host: str
    port: int
    user: str
    password: str
    database: str


@dataclass(frozen=True)
class RedisSettings:
    host: str = defaults.DEFAULT_REDIS_HOST
    port: int = defaults.DEFAULT_REDIS_PORT
    database: int = defaults.DEFAULT_REDIS_DATABASE


@dataclass(frozen=True)
class Settings:
    project_root: Path
    mysql: MySQLSettings
    redis: RedisSettings
    tushare_tokens: tuple[str, ...]
    deepseek_api_key: str
    tdx_root: str
    init_url: str
    tdx_cache_refresh_interval_seconds: int
    browser_close_old_tabs: bool
    fund_flow_interval_seconds: int
    fund_flow_history_top_n: int
    concept_exclusions: tuple[str, ...]
    strategy_pick_timeout_seconds: int
    strategy_pick_max_retries: int
    hot_board_emotion_selection_threshold: int
    hot_board_emotion_climax_threshold: int
    hot_board_emotion_strong_continuation_ratio: float
    hot_board_emotion_excluded_boards: tuple[str, ...]

    @classmethod
    def from_env(cls, *, load_file: bool = True, project_root: Path | None = None) -> "Settings":
        root = project_root or Path(__file__).resolve().parents[3]
        if load_file:
            dotenv.load_dotenv(root / ".env", override=False)

        return cls(
            project_root=root,
            mysql=MySQLSettings(
                host=_required_env("MYSQL_HOST"),
                port=_required_int_env("MYSQL_PORT"),
                user=_required_env("MYSQL_USER"),
                password=_required_env("MYSQL_PASSWORD"),
                database=_required_env("MYSQL_DATABASE"),
            ),
            redis=RedisSettings(
                host=os.getenv("REDIS_HOST", defaults.DEFAULT_REDIS_HOST).strip(),
                port=_optional_int_env("REDIS_PORT", defaults.DEFAULT_REDIS_PORT),
                database=_optional_int_env("REDIS_DATABASE", defaults.DEFAULT_REDIS_DATABASE),
            ),
            tushare_tokens=tuple(_csv_env("TUSHARE_TOKENS")),
            deepseek_api_key=os.getenv("DEEPSEEK_API_KEY", "").strip(),
            tdx_root=os.getenv("TDX_ROOT", "").strip(),
            init_url=os.getenv("INIT_URL", defaults.DEFAULT_INIT_URL).strip(),
            tdx_cache_refresh_interval_seconds=_optional_positive_float_env(
                "TDX_CACHE_REFRESH_INTERVAL_SECONDS",
                defaults.DEFAULT_TDX_CACHE_REFRESH_INTERVAL_SECONDS,
            ),
            browser_close_old_tabs=defaults.DEFAULT_BROWSER_CLOSE_OLD_TABS,
            fund_flow_interval_seconds=defaults.DEFAULT_FUND_FLOW_INTERVAL_SECONDS,
            fund_flow_history_top_n=defaults.DEFAULT_FUND_FLOW_HISTORY_TOP_N,
            concept_exclusions=defaults.DEFAULT_CONCEPT_EXCLUSIONS,
            strategy_pick_timeout_seconds=defaults.DEFAULT_STRATEGY_PICK_TIMEOUT_SECONDS,
            strategy_pick_max_retries=defaults.DEFAULT_STRATEGY_PICK_MAX_RETRIES,
            hot_board_emotion_selection_threshold=defaults.DEFAULT_HOT_BOARD_EMOTION_SELECTION_THRESHOLD,
            hot_board_emotion_climax_threshold=defaults.DEFAULT_HOT_BOARD_EMOTION_CLIMAX_THRESHOLD,
            hot_board_emotion_strong_continuation_ratio=defaults.DEFAULT_HOT_BOARD_EMOTION_STRONG_CONTINUATION_RATIO,
            hot_board_emotion_excluded_boards=defaults.DEFAULT_HOT_BOARD_EMOTION_EXCLUDED_BOARDS,
        )


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"缺少必需环境变量 {name}，请在项目根目录 .env 中配置")
    return value


def _required_int_env(name: str) -> int:
    value = _required_env(name)
    try:
        return int(value)
    except ValueError as error:
        raise RuntimeError(f"环境变量 {name} 必须是整数") from error


def _optional_int_env(name: str, default: int) -> int:
    value = os.getenv(name, "").strip()
    if not value:
        return default
    try:
        return int(value)
    except ValueError as error:
        raise RuntimeError(f"环境变量 {name} 必须是整数") from error


def _optional_positive_float_env(name: str, default: float) -> float:
    value = os.getenv(name, "").strip()
    if not value:
        return float(default)
    try:
        parsed = float(value)
    except ValueError as error:
        raise RuntimeError(f"环境变量 {name} 必须是正数") from error
    if parsed <= 0:
        raise RuntimeError(f"环境变量 {name} 必须是正数")
    return parsed


def _csv_env(name: str) -> list[str]:
    return [value.strip() for value in os.getenv(name, "").split(",") if value.strip()]
