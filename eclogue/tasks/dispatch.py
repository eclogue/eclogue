import sys
import yaml
import uuid
from io import StringIO
from time import time
from bson import ObjectId

from tempfile import NamedTemporaryFile
from tasktiger import TaskTiger, Task, periodic
# from tasktiger._internal import ERROR, QUEUED, serialize_func_name
from celery_once import QueueOnce

from eclogue.model import Mongo
# from eclogue.redis import redis_client
from eclogue.lib.helper import load_ansible_playbook
from eclogue.lib.credential import get_credential_content_by_id
from eclogue.lib.workspace import Workspace
from eclogue.ansible.runer import PlayBookRunner
from eclogue.lib.integration import Integration
from eclogue.middleware import login_user
from eclogue.tasks.reporter import Reporter
from eclogue.celery import celery
from logging import getLogger


logger = getLogger('console')
tiger = TaskTiger()


def run_job(_id, **kwargs):
    logger.info('id:::::::' + _id)
    db = Mongo()
    record = db.collection('jobs').find_one({'_id': ObjectId(_id)})
    if not record:
        return False

    task_id = str(uuid.uuid4())
    username = None if not login_user else login_user.get('username')
    params = (_id, task_id, username)
    queue_name = get_queue_by_job(_id)
    extra = record.get('extra')
    schedule = extra.get('schedule')
    if schedule:
        print('schedule:::1:', schedule)
        # parsed = {}
        # for k, v in schedule.items():
        #     parsed[k] = int(v)

        # schedule = periodic(**parsed)
        # serialize_name = serialize_func_name(func)
        # print('serialize_name::', serialize_name, tiger.periodic_task_funcs)
        # if serialize_name in origin_periodic:
        #     return False

        return None
    else:
        task_record = {
            'job_id': _id,
            'state': 'queued',
            'queue': queue_name,
            'result': '',
            'task_id': task_id,
            'created_at': time(),
        }

        result = db.collection('tasks').insert_one(task_record)
        task = run_task.apply_async(task_id=task_id, args=params)
        print(task)

        return result.inserted_id


def import_galaxy():
    pass


# @celery.task(base=QueueOnce, once={'graceful': True})
@celery.task()
def run_task(_id, task_id, username, **kwargs):
    logger.info('11123123123123123' + str(kwargs))
    print('xxxfuckckckadfkadksfak')
    extra = {'task_id': task_id}
    db = Mongo()
    task_record = db.collection('tasks').find_one({'task_id': task_id})
    if not task_record:
        return False

    task_id = task_record.get('_id')
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    sys.stderr = sys.stdout = temp_stdout = Reporter(StringIO())
    try:
        record = db.collection('jobs').find_one({'_id': ObjectId(_id)})
        template = record.get('template')
        body = {
            'template': record.get('template'),
            'extra': record.get('extra')
        }

        payload = load_ansible_playbook(body)
        if payload.get('message') is not 'ok':
            raise Exception('load ansible options error: ' + payload.get('message'))

        app_id = template.get('app')
        if app_id:
            app_info = db.collection('apps').find_one({'_id': ObjectId(app_id)})
            if not app_info:
                raise Exception('app not found: {}'.format(app_id))

            app_type = app_info.get('type')
            app_params = app_info.get('params')
            if kwargs:
                app_params.update(kwargs)

            integration = Integration(app_type, app_params)
            integration.install()

        data = payload.get('data')
        options = data.get('options')
        private_key = data.get('private_key')
        wk = Workspace()
        res = wk.load_book_from_db(name=data.get('book_name'), roles=data.get('roles'))
        if not res:
            raise Exception('install playbook failed, book name: {}'.format(data.get('book_name')))

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
            options['tags'] = ['uptime']
            inventory = data.get('inventory')
            # report = {
            #     'inventory': data.get('inventory'),
            #     'task_id': task_id,
            # }
            logger.info('ansible-playbook run load inventory: \n{}'.format(yaml.safe_dump(inventory)))
            play = PlayBookRunner(data.get('inventory'), options)
            play.run(entry)

            update = {
                '$set': {
                    # 'result': result,
                    'state': 'finish'
                }
            }
            db.collection('tasks').update_one({'_id': task_id}, update=update)
    except Exception as e:
        update = {
            '$set': {
                'result': e.args,
                'state': 'ERROR',
            }

        }

        db.collection('tasks').update_one({'_id': task_id}, update=update)
        logger.error('run task with exception: {}'.format(str(e)), extra=extra)

    finally:
        content = temp_stdout.getvalue()
        sys.stdout = old_stdout
        sys.stderr = old_stderr
        eclogue_logger = getLogger('eclogue')
        extra.update({'task_id': str(task_id), 'currentUser': username})
        eclogue_logger.info(content, extra=extra)


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
