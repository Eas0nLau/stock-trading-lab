import requests

from stock_lab.modules.dragon_tiger.collectors import collect_broker_directory
from stock_lab.modules.dragon_tiger.repository import DragonTigerRepository


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 Chrome/101.0.4951.64 Safari/537.36",
    "Accept": "*/*",
    "X-Requested-With": "XMLHttpRequest",
    "Host": "data.10jqka.com.cn",
    "Referer": "http://data.10jqka.com.cn/market/longhu/",
    "Connection": "keep-alive",
}


def _pages():
    fields = {
        "sbcs": ("sbcs", "dyzj", "nnsbcs", "nnmrcs", "nngmcgl"),
        "zjsl": ("zgcz", "zgczje", "zgmrje", "dyzj", "ljmrje"),
        "btcz": ("xsjs", "zjgpcs", "zjcgl"),
    }
    for page in range(1, 11):
        for broker_type in (1, 2, 3):
            for order in ("desc", "asc"):
                for tab, tab_fields in fields.items():
                    for field in tab_fields:
                        response = requests.get(
                            f"http://data.10jqka.com.cn/ifmarket/lhbyyb/type/{broker_type}/tab/{tab}/field/{field}/sort/{order}/page/{page}/",
                            headers=HEADERS,
                            timeout=30,
                        )
                        response.raise_for_status()
                        yield response.text


def main():
    from utils import db

    return collect_broker_directory(
        DragonTigerRepository(db.mysql_localhost, db.engine),
        _pages,
    )


if __name__ == "__main__":
    main()
