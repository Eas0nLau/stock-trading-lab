"""Legacy Redis client export."""

from stock_lab.config import get_settings
from stock_lab.infrastructure.cache import create_redis_client


redis_con_localhost = create_redis_client(get_settings())
