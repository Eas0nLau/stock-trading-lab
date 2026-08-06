import sys
from pathlib import Path


_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"
for _path in (_ROOT, _SRC):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from stock_lab.infrastructure.market_data.dragon_tiger import DragonTigerHttpSource
from stock_lab.modules.dragon_tiger.collectors import collect_broker_directory
from stock_lab.modules.dragon_tiger.repository import DragonTigerRepository


_pages = DragonTigerHttpSource().broker_directory_pages


def main():
    from utils import db

    return collect_broker_directory(DragonTigerRepository(db.mysql_localhost, db.engine), _pages)


if __name__ == "__main__":
    main()
