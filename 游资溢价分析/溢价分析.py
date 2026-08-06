import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
for _path in (_ROOT, _SRC):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from stock_lab.modules.dragon_tiger import DragonTigerRepository, analyze_broker_premium
from stock_lab.modules.market_data import MarketDataRepository


def _run_analysis(start_date, latest_date):
    from utils import db

    repository = DragonTigerRepository(db.mysql_localhost, db.engine)
    market_data_repository = MarketDataRepository(db.mysql_localhost, db.engine)
    return analyze_broker_premium(
        start_date,
        latest_date,
        repository,
        market_data_repository,
    )


def main(start_date, latest_date):
    return _run_analysis(int(start_date), int(latest_date))


if __name__ == "__main__":
    main(20260404, 20260803)
