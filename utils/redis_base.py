import redis

redis_con_localhost = redis.Redis("127.0.0.1", 6379, db=0, decode_responses=True)
