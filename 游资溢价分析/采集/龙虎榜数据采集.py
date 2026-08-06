import sys
from datetime import datetime
from pathlib import Path

import requests

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"
for _path in (_ROOT, _SRC):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

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
