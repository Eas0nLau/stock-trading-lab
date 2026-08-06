from datetime import datetime


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 Chrome/101.0.4951.64 Safari/537.36",
    "Accept": "*/*",
    "X-Requested-With": "XMLHttpRequest",
    "Host": "data.10jqka.com.cn",
    "Connection": "keep-alive",
}


class DragonTigerHttpSource:
    def __init__(self, get=None, timeout=30):
        self._get = get
        self.timeout = timeout

    @property
    def get(self):
        if self._get is None:
            import requests

            self._get = requests.get
        return self._get

    def _request(self, url, *, referer=None):
        headers = dict(HEADERS)
        if referer:
            headers["Referer"] = referer
        response = self.get(url, headers=headers, timeout=self.timeout)
        response.raise_for_status()
        return response.text

    def fetch_listing_page(self, trade_date):
        date_text = datetime.strptime(str(trade_date), "%Y%m%d").strftime("%Y-%m-%d")
        return self._request(
            f"http://data.10jqka.com.cn/ifmarket/lhbggxq/report/{date_text}/",
            referer="http://data.10jqka.com.cn/market/longhu/",
        )

    def broker_directory_pages(self):
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
                            yield self._request(
                                f"http://data.10jqka.com.cn/ifmarket/lhbyyb/type/{broker_type}/tab/{tab}/field/{field}/sort/{order}/page/{page}/",
                                referer="http://data.10jqka.com.cn/market/longhu/",
                            )

    def fetch_broker_history_page(self, broker_id, page):
        return self._request(
            f"http://data.10jqka.com.cn/ifmarket/lhbhistory/orgcode/{broker_id}/field/ENDDATE/order/desc/page/{page}/",
            referer=f"http://data.10jqka.com.cn/market/lhbyyb/orgcode/{broker_id}/",
        )


class RedisPageCache:
    def __init__(self, client):
        self._client = client

    @staticmethod
    def _key(item):
        broker_id, page = item
        return f"stock_lab:dragon_tiger:v1:broker_page:{broker_id}:{page}"

    def get(self, item):
        value = self._client.get(self._key(item))
        return value.decode("utf-8") if isinstance(value, bytes) else value

    def __setitem__(self, item, value):
        self._client.set(self._key(item), value)
