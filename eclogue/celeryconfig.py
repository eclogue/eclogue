from datetime import timedelta

from celery.backends.mongodb import MongoBackend
from eclogue.config import config
from eclogue.celery import celery

celery_config = config.celery
print(celery_config)


# broker
broker_url = celery_config.get('broker')

# result
# http://docs.celeryproject.org/en/master/_modules/celery/backends/mongodb.html
# mongodb_url = celery_config.get('backend')
result_backend = celery_config.get('backend')
mongodb_backend_settings = {
    'host': config.mongodb.get('uri'),
    'password': '',
    'database': 'upward',
    'taskmeta_collection': 'celery'     # collection name
}

print(config.mongodb.get('uri'), celery_config.get('backend'))
# special task backend setting collection
job_backend = MongoBackend(celery, url=celery_config.get('backend'))
job_backend.taskmeta_collection = 'job_result'

result_expires = 180 * 86400

# serializer, compare to json, msgpacker is smaller and better performance
# task_serializer = 'msgpack'
# result_serializer = 'msgpack'
# accept_content = ['msgpack']

timezone = 'Asia/Shanghai'
enable_utc = True

# task attribute setting
# http://docs.celeryproject.org/en/latest/userguide/tasks.html
task_annotations = {
    'proj.tasks.eat': {
        'rate_limit': '50/s',
        'backend': job_backend
    },
    'proj.tasks.feeddog': {
        'ignore_result': True
    }
}

# task_routes = ('task_router.TaskRouter',)
# task_queues = (
#     Queue('feed', exchange=Exchange('feed'),
#           routing_key='feed.#'),
#     Queue('eat', exchange=Exchange('eat'),
#           routing_key='eat.#')
# )

# routing
# http://docs.celeryproject.org/en/latest/userguide/routing.html
# task_routes = ('eclogue.celery.task_router',)

# beat schedule
# http://docs.celeryproject.org/en/master/userguide/periodic-tasks.html#beat-entries
beat_schedule = {
    'do-nmap-scan-60-seconds': {  # scheduler task name
        'task': 'eclogue.celery.feeddog',  # special task name with project name
        'schedule': timedelta(seconds=60),
        'options': {
            'queue': 'cruiser'  # task to specific queue
        }
    }
}

ONCE = {
  'backend': 'celery_once.backends.Redis',
  'settings': {
    'url': 'redis://localhost:6379/0',
    'default_timeout': 60 * 60
  }
}
