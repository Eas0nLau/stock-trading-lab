from stock_lab.infrastructure.database import MysqlResources
from stock_lab.config import get_settings
from stock_lab.modules.market_data.repository import MarketDataRepository

from .analytics import analyze_broker_premium
from .repository import DragonTigerRepository


def main(start_date, latest_date):
    resources = MysqlResources.from_settings(get_settings())
    engine = resources.get_engine()

    def query(sql=None, params=None, fetch=False, commit=False):
        connection = resources.get_pool().get_connection()
        cursor = connection.cursor(dictionary=True)
        try:
            cursor.execute(sql, tuple(params or ()))
            result = cursor.fetchall() if fetch else None
            if commit:
                connection.commit()
            return result
        finally:
            cursor.close()
            connection.close()

    return analyze_broker_premium(
        int(start_date),
        int(latest_date),
        DragonTigerRepository(query, engine),
        MarketDataRepository(query, engine),
    )
