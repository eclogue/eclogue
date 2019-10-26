from datetime import timedelta

from celery import Celery
from kombu import Queue
from kombu import Exchange
from celery_once import QueueOnce
from celery.backends.mongodb import MongoBackend
from eclogue.config import config

celery_config = config.celery
celery = Celery(
    celery_config.get('name') or 'eclogue',
    backend=celery_config.get('backend'),
    broker=celery_config.get('broker'),
    include=['eclogue.tasks.dispatch']
)
celery.config_from_object('eclogue.celeryconfig')


def task_router(name, args, kwargs, options, task):
    print('task_router:::', name, 1, args, 2, kwargs, 3, options, task)
    return {
        'queue': options.get('queue', 'default'),
        'routing_key': options.get('routing_key', 'eclogue.job')
    }


@celery.task()
def feeddog():
    print('dooooooooooooooooooooooooooooooooooooooooog=---\n')


@celery.task(base=QueueOnce)
def add(x, y):
    print('I will sleep')
    print('I am wake up now')
    return x + y
