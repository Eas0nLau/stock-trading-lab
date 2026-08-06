import re
from typing import Optional

from bs4 import BeautifulSoup

from .models import Broker, BrokerListingHistory, DragonTigerListing


UNPUBLISHED_TEXT = "今日龙虎榜暂未公布"


def parse_amount(value) -> Optional[float]:
    if value is None:
        return None
    text = str(value).strip().replace(",", "").replace("元", "")
    if text in {"", "-", "--"}:
        return None
    multiplier = 1.0
    if "亿" in text:
        multiplier = 10000.0
    text = text.replace("亿", "").replace("万", "").replace("%", "")
    return float(text) * multiplier


def _broker_id(anchor) -> Optional[str]:
    if anchor is None:
        return None
    match = re.search(r"/(?:org)?code/([^/]+)/", anchor.get("href", ""))
    return match.group(1) if match else None


def _seat_values(table, side, trade_date, source_id):
    values = {}
    if table is None:
        return values
    for rank, row in enumerate(table.find_all("tr")[1:6], start=1):
        cells = row.find_all("td")
        if len(cells) < 4:
            raise ValueError(
                f"{side} seat row {rank} malformed for {trade_date} source {source_id}: "
                f"expected 4 cells, got {len(cells)}"
            )
        anchor = cells[0].find("a")
        if anchor is None:
            raise ValueError(
                f"{side} seat row {rank} malformed for {trade_date} source {source_id}: broker link missing"
            )
        prefix = f"{side}_{rank}"
        try:
            values[f"{prefix}_broker_id"] = _broker_id(anchor)
            values[f"{prefix}_broker_name"] = anchor.get("title") or cells[0].get_text(strip=True) or None
            values[f"{prefix}_buy_amount"] = parse_amount(cells[1].get_text(strip=True))
            values[f"{prefix}_sell_amount"] = parse_amount(cells[2].get_text(strip=True))
            values[f"{prefix}_net_amount"] = parse_amount(cells[3].get_text(strip=True))
        except (TypeError, ValueError) as error:
            raise ValueError(
                f"{side} seat row {rank} malformed for {trade_date} source {source_id}: {error}"
            ) from error
    return values


def _label_amount(text, label):
    match = re.search(rf"{re.escape(label)}\s*([^\s]+)", text)
    return parse_amount(match.group(1)) if match else None


def parse_listing_page(html: str, trade_date: int):
    if UNPUBLISHED_TEXT in html:
        return []
    soup = BeautifulSoup(html, "lxml")
    wrapper = soup.find("div", class_="twrap")
    table = wrapper.find("table", class_="m-table") if wrapper else None
    if table is None:
        raise ValueError(f"listing table missing for {trade_date}")

    listings = []
    for row_index, row in enumerate(table.find_all("tr"), start=1):
        cells = row.find_all("td")
        if not cells:
            continue
        if len(cells) < 7:
            raise ValueError(
                f"listing row {row_index} malformed for {trade_date}: expected 7 cells, got {len(cells)}"
            )
        stock_anchor = cells[2].find("a")
        source_id = stock_anchor.get("rid") if stock_anchor else None
        detail = soup.find("div", attrs={"rid": source_id}) if source_id else None
        detail_tables = detail.find_all("table", class_="m-table m-table-nosort mt10") if detail else []
        if detail is None or len(detail_tables) < 2:
            raise ValueError(f"listing detail missing for {trade_date} source {source_id}")
        paragraphs = detail.find_all("p")
        detail_text = paragraphs[0].get_text(" ", strip=True) if paragraphs else ""
        if "明细：" not in detail_text:
            raise ValueError(f"listing reason missing for {trade_date} source {source_id}")
        summary_text = " ".join(item.get_text(" ", strip=True) for item in paragraphs[1:])
        try:
            values = {
                "data_id": f"{int(trade_date)}_{source_id}",
                "trade_date": int(trade_date),
                "source_id": source_id,
                "detail_type": detail_text.split("明细：", 1)[1].strip(),
                "date_type": cells[0].get_text(strip=True) or "1日",
                "stock_code": cells[1].get_text(strip=True),
                "stock_name": cells[2].get_text(strip=True),
                "current_price": parse_amount(cells[3].get_text(strip=True)),
                "change_pct": parse_amount(cells[4].get_text(strip=True)),
                "turnover": parse_amount(cells[5].get_text(strip=True)),
                "net_buy_amount": parse_amount(cells[6].get_text(strip=True)),
                "total_buy_amount": _label_amount(summary_text, "合计买入："),
                "total_sell_amount": _label_amount(summary_text, "合计卖出："),
            }
        except (TypeError, ValueError) as error:
            raise ValueError(
                f"listing row {row_index} malformed for {trade_date} source {source_id}: {error}"
            ) from error
        values.update(_seat_values(detail_tables[0], "buy", trade_date, source_id))
        values.update(_seat_values(detail_tables[1], "sell", trade_date, source_id))
        listings.append(DragonTigerListing(**values))
    return listings


def listing_brokers(listings):
    brokers = {}
    for listing in listings:
        for side in ("buy", "sell"):
            for rank in range(1, 6):
                broker_id = getattr(listing, f"{side}_{rank}_broker_id")
                if broker_id and broker_id not in brokers:
                    brokers[broker_id] = Broker(broker_id, getattr(listing, f"{side}_{rank}_broker_name"))
    return list(brokers.values())


def listing_history(listings):
    history = {}
    for listing in listings:
        for side in ("buy", "sell"):
            for rank in range(1, 6):
                prefix = f"{side}_{rank}"
                broker_id = getattr(listing, f"{prefix}_broker_id")
                if not broker_id:
                    continue
                data_id = f"{broker_id}_{listing.trade_date}_{listing.stock_code}_{listing.detail_type}"
                if data_id in history:
                    continue
                history[data_id] = BrokerListingHistory(
                    data_id=data_id,
                    broker_id=broker_id,
                    broker_name=getattr(listing, f"{prefix}_broker_name"),
                    trade_date=listing.trade_date,
                    stock_name=listing.stock_name,
                    stock_code=listing.stock_code,
                    listing_reason=listing.detail_type,
                    change_pct=listing.change_pct,
                    buy_amount=getattr(listing, f"{prefix}_buy_amount"),
                    sell_amount=getattr(listing, f"{prefix}_sell_amount"),
                    net_amount=getattr(listing, f"{prefix}_net_amount"),
                )
    return list(history.values())


def parse_broker_directory_page(html: str):
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table", class_="m-table")
    if table is None:
        raise ValueError("broker directory table missing")
    brokers = {}
    for row in table.find_all("tr")[1:]:
        cells = row.find_all("td")
        for index in (1, 3):
            anchor = cells[index].find("a") if len(cells) > index else None
            broker_id = _broker_id(anchor)
            if broker_id and broker_id not in brokers:
                brokers[broker_id] = Broker(broker_id, anchor.get("title") or anchor.get_text(strip=True))
    return list(brokers.values())


def parse_broker_history_page(html: str, broker_id: str, broker_name: str):
    soup = BeautifulSoup(html, "lxml")
    page_info = soup.find("span", class_="page_info")
    page_count = int(page_info.get_text(strip=True).split("/")[-1]) if page_info else 2
    table = soup.find("table", class_="m-table m-table-nosort")
    if table is None:
        raise ValueError(f"broker history table missing for {broker_id}")
    rows = []
    for row_index, row in enumerate(table.find_all("tr")[1:], start=1):
        cells = row.find_all("td")
        if len(cells) < 8:
            raise ValueError(
                f"broker history row {row_index} malformed for {broker_id}: expected 8 cells, got {len(cells)}"
            )
        try:
            stock_anchor = cells[1].find("a")
            stock_code = _broker_id(stock_anchor)
            if not stock_code:
                raise ValueError("stock code link missing")
            trade_date = int(cells[0].get_text(strip=True).replace("-", ""))
            reason = cells[2].get_text(strip=True)
            rows.append(BrokerListingHistory(
                data_id=f"{broker_id}_{trade_date}_{stock_code}_{reason}",
                broker_id=broker_id,
                broker_name=broker_name,
                trade_date=trade_date,
                stock_name=cells[1].get_text(strip=True),
                stock_code=stock_code,
                listing_reason=reason,
                change_pct=parse_amount(cells[3].get_text(strip=True)),
                buy_amount=parse_amount(cells[4].get_text(strip=True)),
                sell_amount=parse_amount(cells[5].get_text(strip=True)),
                net_amount=parse_amount(cells[6].get_text(strip=True)),
                board_name=cells[7].get_text(strip=True) or None,
            ))
        except (TypeError, ValueError) as error:
            raise ValueError(
                f"broker history row {row_index} malformed for {broker_id}: {error}"
            ) from error
    return rows, page_count
