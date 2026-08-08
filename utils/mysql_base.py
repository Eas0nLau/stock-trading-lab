"""Legacy MySQL resource exports.

New code must depend on ``stock_lab.infrastructure.database`` directly.
"""

from stock_lab.config import get_settings
from stock_lab.infrastructure.database import LazyMysqlPool, MysqlResources


resources = MysqlResources.from_settings(get_settings())
connection_string = resources.url
engine = resources.get_engine()
mysql_localhost_pool = LazyMysqlPool(resources)


def load_mysql_localhost_pool():
    return mysql_localhost_pool
