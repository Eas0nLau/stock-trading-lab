import redis


def create_redis_client(settings):
    """Create a Redis client without performing a network operation."""
    return redis.Redis(
        host=settings.redis.host,
        port=settings.redis.port,
        db=settings.redis.database,
        decode_responses=True,
    )
