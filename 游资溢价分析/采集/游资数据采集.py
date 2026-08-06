import sys
from pathlib import Path


_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"
for _path in (_ROOT, _SRC):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from stock_lab.infrastructure.market_data.dragon_tiger import DragonTigerHttpSource, RedisPageCache
from stock_lab.modules.dragon_tiger.collectors import collect_broker_history
from stock_lab.modules.dragon_tiger.repository import DragonTigerRepository


_RedisPageCache = RedisPageCache
_fetch_page = DragonTigerHttpSource().fetch_broker_history_page


def main():
    from utils import db

    return collect_broker_history(
        DragonTigerRepository(db.mysql_localhost, db.engine),
        _fetch_page,
        RedisPageCache(db.redis_con_localhost),
    )


if __name__ == "__main__":
    main()
