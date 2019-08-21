from time import time
from bson import ObjectId
import uuid
from tempfile import NamedTemporaryFile
from tasktiger import TaskTiger, Task
from tasktiger._internal import ERROR, QUEUED
from eclogue.model import Mongo
from eclogue.redis import redis_client
from eclogue.lib.helper import load_ansible_playbook
from eclogue.lib.credential import get_credential_content_by_id
from eclogue.lib.workspace import Workspace
from eclogue.ansible.runer import PlayBookRunner
from eclogue.lib.integration import Integration
from eclogue.lib.logger import logger
from flask_log_request_id import current_request_id

tiger = TaskTiger(connection=redis_client, config={
    'REDIS_PREFIX': 'ece',
    'ALWAYS_EAGER': True,
}, setup_structlog=False)


def run_job(job_id, *args, **kwargs):
    db = Mongo()
    record = db.collection('jobs').find_one({'_id': ObjectId(job_id)})
    if not record:
        return False

    request_id = current_request_id
    params = (job_id, request_id)
    params = params + args
    queue_name = get_queue_by_job(job_id)
    task = Task(tiger, func=run_task, args=params, kwargs=kwargs, queue=queue_name,
                unique=False, lock=True, lock_key=job_id)
    task_record = {
        'job_id': job_id,
        'state': QUEUED,
        'queue': queue_name,
        'result': '',
        'request_id': request_id,
        't_id': task.id,
        'created_at': time(),
    }

    db.collection('tasks').insert_one(task_record)
    task.delay()

    return True


def import_galaxy():
    pass


def run_task(job_id, request_id, *args, **kwargs):
    db = Mongo()
    task_record = db.collection('tasks').find_one({'request_id': request_id})
    if not task_record:
        return False

    task_id = task_record.get('_id')
    try:
        record = db.collection('jobs').find_one({'_id': ObjectId(job_id)})
        template = record.get('template')
        body = {
            'template': record.get('template'),
            'extra': record.get('extra')
        }

        payload = load_ansible_playbook(body)
        if payload.get('message') is not 'ok':
            raise Exception('load ansible options error: %s'.format(payload.get('message')))

        app_id = template.get('app')
        if app_id:
            app_info = db.collection('apps').find_one({'_id': ObjectId(app_id)})
            if not app_info:
                raise Exception('app not found: %s'.format(app_id))

            app_type = app_info.get('type')
            app_params = app_info.get('params')
            integration = Integration(app_type, app_params)
            integration.install(*args, **kwargs)

        data = payload.get('data')
        options = data.get('options')
        private_key = data.get('private_key')
        wk = Workspace()
        res = wk.load_book_from_db(name=data.get('book_name'), roles=data.get('roles'))
        if not res:
            raise Exception('install playbook failed, book name: %s'.format(data.get('book_name')))

        entry = wk.get_book_entry(data.get('book_name'), data.get('entry'))
        with NamedTemporaryFile('w+t', delete=False) as fd:
            key_text = get_credential_content_by_id(private_key, 'private_key')
            if not key_text:
                return {
                    'message': 'invalid private_key',
                    'code': 104033,
                }
            fd.write(key_text)
            fd.seek(0)
            options['private-key'] = fd.name
            # options['tags'] = ['uptime']
            extra = {
                'request_id': request_id,
                'inventory': data.get('inventory'),
                'options': options
            }
            logger.info('ansible-playbook run with args', extra=extra)
            play = PlayBookRunner(data.get('inventory'), options)
            play.run(entry)
            result = play.get_result()
            update = {
                '$set': {
                    'result': result,
                    'state': 'finish'
                }
            }
            db.collection('tasks').update_one({'_id': task_id}, update=update)
    except Exception as e:
        update = {
            '$set': {
                'result': e.args,
                'state': ERROR,
            }

        }
        db.collection('tasks').update_one({'_id': task_id}, update=update)
        logger.error('run task with exception: %s'.format(str(e)), extra={'request_id': request_id})


def get_tasks_by_job(job_id, offset=0, limit=20):
    queue = get_queue_by_job(job_id)
    if not queue:
        return []

    where = {
        'job_id': job_id,
    }
    return Mongo().collection('tasks').find(where, skip=offset, limit=limit)


def get_queue_by_job(job_id):
    return 'queue:job.' + job_id
