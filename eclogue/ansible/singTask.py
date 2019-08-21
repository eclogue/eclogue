import redis
import pprint
from celery.task import Task

REDIS_CLIENT = redis.Redis()


def only_one(function=None, key="", timeout=None):
    """Enforce only one celery task at a time."""
    print('>>>>>', key, function, timeout)
    def _dec(run_func):
        """Decorator."""
        pprint.pprint(run_func.name)
        def _caller(*args, **kwargs):
            """Caller."""
            ret_value = None
            have_lock = False
            lock = REDIS_CLIENT.lock(key, timeout=timeout)
            print('only one=========+++++', key)
            try:
                have_lock = lock.acquire(blocking=False)
                print('is had lock~~~~~~~~`', have_lock)
                if have_lock:
                    ret_value = run_func(*args, **kwargs)
            finally:
                if have_lock:
                    lock.release()

            return ret_value

        return _caller

    return _dec(function) if function is not None else _dec


class SingleTask(Task):
    """A task."""

    # @only_one(key="SingleTask", timeout=60 * 5)
    def run(self, *args, **kwargs):
        """Run task."""
        print("Acquired lock for up to 5 minutes and ran task!")
        # super().run(*args, **kwargs)


# LOCK_EXPIRE = 60 * 10
# @contextmanager
# def memcache_lock(lock_id, oid):
#     have_lock = False
#     current_lock = redis.Redis().lock("lock_id")
#     try:
#         have_lock = current_lock.acquire(blocking=False)
#         if have_lock:
#             print("Got lock.")
#         else:
#             print("Did not acquire lock.")
#
#     finally:
#         if have_lock:
#             current_lock.release()
