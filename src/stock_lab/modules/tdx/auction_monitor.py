from decimal import Decimal, ROUND_HALF_UP


def safe_ratio(numerator, denominator):
    return None if numerator is None or denominator is None or denominator <= 0 else numerator / denominator


def amount_from_lots(volume_lots, price):
    return None if volume_lots is None or price is None else volume_lots * price / 100


def stock_limit_rate(code, name):
    code = str(code).upper()
    name = str(name or "").upper()
    if "ST" in name or "退" in name:
        return .05
    if code.endswith(".BJ"):
        return .30
    return .20 if code.split(".")[0].startswith(("300", "301", "688", "689")) else .10


def limit_up_price(code, name, pre_close):
    if pre_close is None or pre_close <= 0:
        return None
    code = str(code).upper()
    name = str(name or "").upper()
    rate = stock_limit_rate(code, name)
    return float(Decimal(str(pre_close * (1 + rate))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def build_monitor_row(row):
    code = str(row.get("代码") or "")
    name = str(row.get("名称") or "")
    latest = row.get("最新价")
    latest_pct = row.get("最新涨幅")
    pre_close = row.get("昨收价")
    buy_price = row.get("买一价")
    buy_volume = row.get("买一量")
    sell_volume = row.get("卖一量")
    auction_amount = row.get("竞价金额(万)")
    ratio = safe_ratio(buy_volume, sell_volume)
    seal_amount = amount_from_lots(buy_volume, buy_price)
    up_price = limit_up_price(code, name, pre_close)
    sealed = bool(up_price and buy_price is not None and latest is not None and buy_price >= up_price - .01 and latest >= up_price - .01)
    grabbed = bool(latest_pct is not None and latest_pct >= 2 and auction_amount is not None and auction_amount >= 1000 and (ratio is None or ratio >= 1.5))
    return {"读取时间": row.get("读取时间"), "代码": code, "名称": name, "最新价": latest, "最新涨幅": latest_pct, "昨收价": pre_close, "涨停价": up_price, "竞价金额(万)": auction_amount, "买一价": buy_price, "买一量": buy_volume, "卖一量": sell_volume, "买卖量比": ratio, "封单金额(万)": seal_amount, "抢筹": "Y" if grabbed else "", "封板": "Y" if sealed else "", "_is_grab": grabbed, "_is_sealed": sealed}


def main():
    from .runtime import run_auction_monitor
    return run_auction_monitor()
