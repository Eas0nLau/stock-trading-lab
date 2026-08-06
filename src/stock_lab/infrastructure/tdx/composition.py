from stock_lab.infrastructure.database import MysqlResources
from stock_lab.modules.market_data import MarketDataRepository


def build_market_data_repository(settings):
    resources = MysqlResources.from_settings(settings)

    def query(sql, params=None, fetch=False):
        connection = resources.get_pool().get_connection()
        try:
            cursor = connection.cursor(dictionary=True)
            cursor.execute(sql, params or ())
            return cursor.fetchall() if fetch else cursor.rowcount
        finally:
            connection.close()

    return MarketDataRepository(query)
