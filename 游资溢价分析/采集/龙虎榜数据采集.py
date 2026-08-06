import sys
from pathlib import Path


_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"
for _path in (_ROOT, _SRC):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from stock_lab.infrastructure.market_data.dragon_tiger import DragonTigerHttpSource
from stock_lab.modules.dragon_tiger.collectors import collect_listings
from stock_lab.modules.dragon_tiger.repository import DragonTigerRepository


_fetch_page = DragonTigerHttpSource().fetch_listing_page


def main(date):
    from utils import db

    return collect_listings(int(date), DragonTigerRepository(db.mysql_localhost, db.engine), _fetch_page)


if __name__ == "__main__":
    main(20150301)
