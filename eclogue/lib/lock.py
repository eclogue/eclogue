from redis.lock import Lock
from eclogue.redis import redis_client


class Lock:

    def __init__(self, name, blocking=True, timeout=60):
        self.client = redis_client
        self.name = name
        self.blocking = blocking
        self.locking = False
        self.timeout = timeout

    def lock(self):
        try:
            self.locking = self.client.lock(self.name, timeout=self.timeout)

            return self.locking
        finally:
            self.locking = False

            return self.locking

    def release(self):
        if isinstance(self.locking, Lock):
            return self.locking.release()
