# import pickle
# import time
# from bson import ObjectId
# from celery import Celery
# from eclogue.config import config
# from eclogue.lib.logger import logger
# from eclogue.redis import redis_client
# from eclogue.model import db
#
#
# celery = Celery(
#     config.celery.get('name') or 'eclogue',
#     backend=config.celery['backend'],
#     broker=config.celery['broker'],
#     include=['test']
# )
# celery.conf.update(config.celery)
# queue_key = 'pb:job:123123xxxxx'
#
#
# def only_one(function=None, key="", timeout=None):
#     """Enforce only one celery task at a time."""
#
#     def _dec(run_func):
#         """Decorator."""
#
#         def _caller(*args, **kwargs):
#             """Caller."""
#             ret_value = None
#             have_lock = False
#             lock = redis_client.lock(key, timeout=timeout)
#             try:
#                 have_lock = lock.acquire(blocking=False)
#                 if have_lock:
#                     ret_value = run_func(*args, **kwargs)
#             finally:
#                 if have_lock:
#                     lock.release()
#
#             return ret_value
#
#         return _caller
#
#     return _dec(function) if function is not None else _dec
#
#
# class MyTask(celery.Task):
#
#     def on_failure(self, exc, task_id, *args, **kwargs):
#         print(args, kwargs)
#
#
# @celery.on_after_configure.connect
# def setup_periodic_tasks(sender, **kwargs):
#     # Calls test('hello') every 10 seconds.
#     logger.info('start periodic')
#     sender.add_periodic_task(2.0, test.s(time.time()), name='add every 10')
#
#
# @celery.task(bind=MyTask)
# @only_one(key='test')
# def test():
#     logger().info('call function test')
#     length = redis_client.llen(queue_key)
#     if not length:
#         return False
#
#     current = redis_client.lrange(length - 1, -1)
#     job_id = current.get('job_id')
#     lock_key = 'eclock:' + job_id
#     try:
#         is_locked = redis_client.get(lock_key)
#         print('is_locked', is_locked)
#         if is_locked:
#             return False
#         redis_client.set(lock_key, 1)
#         handler = pickle.loads(bytes(current.get('func_name')))
#         if callable(handler):
#
#             handler(*current.get('args'), **current.get('kwargs'))
#     finally:
#         redis_client.rpop()
#         redis_client.delete(lock_key)
#
#
#
# def playbook_task(job_id):
#     record = db.collection('jobs').find_one({'_id': ObjectId(job_id)})
#     if not record:
#         return False
#
#     pass
