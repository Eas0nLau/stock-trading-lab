from typing import Any


def to_number(value: Any):
    if value is None or isinstance(value, bool) or value in ("", "--", "-"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def crossed_above(previous_price, current_price, previous_level, current_level):
    return all(value is not None for value in (previous_price, current_price, previous_level, current_level)) and previous_price <= previous_level and current_price > current_level


def can_emit_alert(history, stock_code, signal, now_ts, repeat_after_seconds):
    key = (stock_code, signal)
    previous = history.get(key)
    if previous is None or repeat_after_seconds > 0 and now_ts - previous >= repeat_after_seconds:
        history[key] = now_ts
        return True
    return False


def is_effective_quote_row(row):
    if row.get("状态") != "OK":
        return False
    return any((to_number(row.get(field)) or 0) > 0 for field in ("最新价", "开盘价", "最高价", "最低价", "买一价", "卖一价", "成交量(手)", "成交额(万)", "买一量", "卖一量"))


def build_alert_message(row, signal, level_name, level):
    return f"ALERT {row.get('读取时间')} {row.get('代码')} {row.get('名称')} {signal}: {level_name}={level} 最新价={row.get('最新价')}"


def main():
    from .runtime import run_global_monitor
    return run_global_monitor()
