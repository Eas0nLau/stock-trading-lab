from decimal import Decimal, ROUND_HALF_UP


AUCTION_START = "09:15:00"
AUCTION_PHASE_1_END = "09:20:00"
AUCTION_PHASE_2_START = "09:20:00"
AUCTION_END = "09:25:00"


def current_auction_phase(current=None):
    if current is None:
        from datetime import datetime
        current = datetime.now().strftime("%H:%M:%S")
    if AUCTION_START <= current < AUCTION_PHASE_1_END:
        return "09:15-09:20"
    if AUCTION_PHASE_2_START <= current <= AUCTION_END:
        return "09:20-09:25"
    return ""


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
    seal_amount = amount_from_lots(buy_volume, buy_price)
    sealed = bool(up_price and buy_price is not None and latest is not None and buy_price >= up_price - .01 and latest >= up_price - .01 and seal_amount is not None and seal_amount >= 300)
    grabbed = bool(latest_pct is not None and latest_pct >= 2 and auction_amount is not None and auction_amount >= 1000 and (ratio is None or ratio >= 1.5))
    return {"读取时间": row.get("读取时间"), "竞价阶段": "", "代码": code, "名称": name, "最新价": latest, "最新涨幅": latest_pct, "昨收价": pre_close, "涨停价": up_price, "竞价金额(万)": auction_amount, "买一价": buy_price, "买一量": buy_volume, "卖一价": row.get("卖一价"), "卖一量": sell_volume, "买卖量比": ratio, "五档总买金额(万)": row.get("五档总买金额(万)"), "五档总卖金额(万)": row.get("五档总卖金额(万)"), "五档买卖金额比": safe_ratio(row.get("五档总买金额(万)"), row.get("五档总卖金额(万)")), "封单金额(万)": seal_amount, "封单变化(万)": None, "抢筹": "Y" if grabbed else "", "封板": "Y" if sealed else "", "_is_grab": grabbed, "_is_sealed": sealed}


class AuctionState:
    def __init__(self, add_delta=300, reduce_delta=300):
        self.add_delta = add_delta
        self.reduce_delta = reduce_delta
        self.last_seal = {}

    def update(self, phase, code, current):
        key = (phase, code)
        previous = self.last_seal.get(key)
        self.last_seal[key] = current
        if previous is None:
            return ("seal", 0) if current > 0 else (None, 0)
        delta = current - previous
        if previous <= 0 < current:
            return "seal", delta
        if delta >= self.add_delta:
            return "add", delta
        if delta <= -self.reduce_delta:
            return ("withdraw" if current <= 0 else "reduce"), delta
        return None, delta


def process_auction_rows(rows, phase, state, grab_alerted=None, emit=None):
    grab_alerted = grab_alerted if grab_alerted is not None else set()
    emit = emit or (lambda event: None)
    for row in rows:
        row["竞价阶段"] = phase
        code = str(row.get("代码") or "")
        if row.get("_is_grab") and code not in grab_alerted:
            grab_alerted.add(code)
            emit({"signal": "grab", "code": code, "row": row})
        amount = row.get("封单金额(万)") if row.get("_is_sealed") else 0
        signal, delta = state.update(phase, code, float(amount or 0))
        if signal:
            row["封单变化(万)"] = delta
            emit({"signal": signal, "code": code, "delta": delta, "row": row})
    return rows


def main():
    from .runtime import run_auction_monitor
    from stock_lab.config import get_settings
    from stock_lab.infrastructure.tdx.composition import build_market_data_repository
    return run_auction_monitor(get_settings(), build_market_data_repository(get_settings()))
