import requests

from stock_lab.modules.dragon_tiger.collectors import collect_broker_history
from stock_lab.modules.dragon_tiger.repository import DragonTigerRepository


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 Chrome/101.0.4951.64 Safari/537.36",
    "Accept": "*/*",
    "X-Requested-With": "XMLHttpRequest",
    "Host": "data.10jqka.com.cn",
    "Connection": "keep-alive",
}


class _RedisPageCache:
    def __init__(self, client):
        self._client = client

    @staticmethod
    def _key(item):
        broker_id, page = item
        return f"股票:游资数据采集:{broker_id}:{page}"

    def get(self, item):
        value = self._client.get(self._key(item))
        return value.decode("utf-8") if isinstance(value, bytes) else value

    def __setitem__(self, item, value):
        self._client.set(self._key(item), value)


def _fetch_page(broker_id, page):
    headers = dict(HEADERS)
    headers["Referer"] = f"http://data.10jqka.com.cn/market/lhbyyb/orgcode/{broker_id}/"
    response = requests.get(
        f"http://data.10jqka.com.cn/ifmarket/lhbhistory/orgcode/{broker_id}/field/ENDDATE/order/desc/page/{page}/",
        headers=headers,
        timeout=30,
    )
    response.raise_for_status()
    return response.text


def main():
    from utils import db

    return collect_broker_history(
        DragonTigerRepository(db.mysql_localhost, db.engine),
        _fetch_page,
        _RedisPageCache(db.redis_con_localhost),
    )


if __name__ == "__main__":
    main()
