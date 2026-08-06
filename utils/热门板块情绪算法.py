from stock_lab.modules.emotion.contracts import translate_canonical_payload
from stock_lab.modules.emotion.hot_board import (
    analyze_legacy_hot_board_day,
    coerce_int,
    legacy_config_value,
    refresh_legacy_config,
)


def __getattr__(name):
    return legacy_config_value(name)


def 刷新运行配置():
    return refresh_legacy_config()


def 生成每日分析(**values):
    return translate_canonical_payload(analyze_legacy_hot_board_day(values))


def 取整数(value):
    return coerce_int(value)
