import redis

from eclogue.config import config
redis_conf = config.redis
redis_conn = redis_conf.get('conn')
redis_client = None
if redis_conf.get('cluster'):
    redis_client = redis.Sentinel(redis_conn, redis_conf.get('options'))
else:
    redis_client = redis.Redis(**redis_conn)
