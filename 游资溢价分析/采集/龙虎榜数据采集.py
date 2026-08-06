from datetime import datetime

import requests

from stock_lab.modules.dragon_tiger.collectors import collect_listings
from stock_lab.modules.dragon_tiger.repository import DragonTigerRepository


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 Chrome/101.0.4951.64 Safari/537.36",
    "Accept": "*/*",
    "X-Requested-With": "XMLHttpRequest",
    "Host": "data.10jqka.com.cn",
    "Referer": "http://data.10jqka.com.cn/market/longhu/",
    "Connection": "keep-alive",
}


def _fetch_page(trade_date):
    range_date = datetime.strptime(str(trade_date), "%Y%m%d").strftime("%Y-%m-%d")
    response = requests.get(
        f"http://data.10jqka.com.cn/ifmarket/lhbggxq/report/{range_date}/",
        headers=HEADERS,
        timeout=30,
    )
    response.raise_for_status()
    return response.text


def main(date):
    from utils import db

    return collect_listings(
        int(date),
        DragonTigerRepository(db.mysql_localhost, db.engine),
        _fetch_page,
    )


if __name__ == "__main__":
    main(20150301)
