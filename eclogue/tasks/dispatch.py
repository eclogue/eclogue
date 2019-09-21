import sys
import yaml
import os
import shutil
import datetime
from io import StringIO
from time import time
from bson import ObjectId

from tempfile import NamedTemporaryFile
from tasktiger import TaskTiger, Task, periodic
from tasktiger._internal import ERROR, QUEUED
from flask_log_request_id import current_request_id

from eclogue.model import Mongo
from eclogue.redis import redis_client
from eclogue.lib.helper import load_ansible_playbook, load_ansible_adhoc
from eclogue.lib.credential import get_credential_content_by_id
from eclogue.lib.workspace import Workspace
from eclogue.ansible.runer import PlayBookRunner, AdHocRunner
from eclogue.lib.integration import Integration
from eclogue.lib.logger import get_logger
from eclogue.middleware import login_user
from eclogue.tasks.reporter import Reporter
from eclogue.scheduler import scheduler
from eclogue.utils import make_zip

tiger = TaskTiger(connection=redis_client, config={
    'REDIS_PREFIX': 'ece',
    'ALWAYS_EAGER': False,
}, setup_structlog=True)

logger = get_logger('console')


def run_job(_id, **kwargs):
    db = Mongo()
    record = db.collection('jobs').find_one({'_id': ObjectId(_id)})
    if not record:
        return False

    request_id = str(current_request_id())
    username = None if not login_user else login_user.get('username')
    params = (_id, request_id, username)
    queue_name = get_queue_by_job(_id)
    extra = record.get('extra')
    schedule = extra.get('schedule')
    ansible_type = record.get('type')
    if schedule:
        existed = db.collection('scheduler_jobs').find_one({'_id': record['_id']})
        if existed:
            return False

        scheduler.add_job(func=run_schedule_task, trigger='cron', args=params, minute='1', coalesce=True,
                          kwargs=kwargs, id=str(record.get('_id')), max_instances=1, namne=record.get('name'))
        return True
    else:
        func = run_task if ansible_type != 'adhoc' else run_adhoc_task

        task = Task(tiger, func=func, args=params, kwargs=kwargs, queue=queue_name,
                    unique=False, lock=True, lock_key=_id)

        task_record = {
            'job_id': _id,
            'type': 'trigger',
            'ansible': ansible_type,
            'state': QUEUED,
            'queue': queue_name,
            'result': '',
            'request_id': request_id,
            't_id': task.id,
            'created_at': time(),
        }

        result = db.collection('tasks').insert_one(task_record)
        task.delay()

        return result.inserted_id


def import_galaxy():
    pass


def run_adhoc_task(_id, request_id, username, **kwargs):
    extra = {'request_id': request_id}
    db = Mongo()
    task_record = db.collection('tasks').find_one({'request_id': request_id})
    if not task_record:
        return False

    start_at = time()
    state = 'progressing'
    result = ''
    task_id = task_record.get('_id')
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    sys.stderr = sys.stdout = temp_stdout = Reporter(StringIO())
    try:
        record = db.collection('jobs').find_one({'_id': ObjectId(_id)})
        ret = load_ansible_adhoc(record)
        if ret.get('message') != 'ok':
            raise Exception(ret.get('message'))

        payload = ret.get('data')
        options = payload.get('options')
        private_key = payload.get('private_key')
        module = payload.get('module')
        args = payload.get('args')
        hosts = options['hosts']
        with NamedTemporaryFile('w+t', delete=True) as fd:
            fd.write(private_key)
            fd.seek(0)
            options['private_key'] = fd.name
            tasks = [{
                'action': {
                    'module': module,
                    'args': args
                }
            }]
            runner = AdHocRunner(hosts, options=options)
            runner.run('all', tasks)
            result = runner.get_result()
            state = 'success'
            update = {
                '$set': {
                    'result': result,
                    'state': state,
                }
            }
            db.collection('tasks').update_one({'_id': task_id}, update=update)
    except Exception as e:
        result = e.args
        logger.error('run task with exception: {}'.format(str(e)), extra=extra)

        raise e
    finally:
        content = temp_stdout.getvalue()
        sys.stdout = old_stdout
        sys.stderr = old_stderr
        eclogue_logger = get_logger('eclogue')
        extra.update({'task_id': str(task_id), 'currentUser': username})
        eclogue_logger.info(content, extra=extra)
        finish_at = time()
        update = {
            '$set': {
                'start_at': start_at,
                'finish_at': finish_at,
                'state': state,
                'duration': finish_at - start_at,
                'result': result,
            }

        }

        db.collection('tasks').update_one({'_id': task_id}, update=update)


def run_task(_id, request_id, username, **kwargs):
    extra = {'request_id': request_id}
    db = Mongo()
    task_record = db.collection('tasks').find_one({'request_id': request_id})
    if not task_record:
        return False

    start_at = time()
    state = 'progressing'
    result = ''
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
        roles = data.get('roles')
        bookname = data.get('book_name')
        bookspace = wk.load_book_from_db(name=bookname, roles=roles, build_id=task_id)
        if not bookspace:
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
            #     'request_id': request_id,
            # }
            logger.info('ansible-playbook run load inventory: \n{}'.format(yaml.safe_dump(inventory)))
            play = PlayBookRunner(data.get('inventory'), options)
            play.run(entry)
            result = play.get_result()
            builds = db.collection('build_books').count({'job_id': _id})
            # @todo
            if builds > 10:
                last_one = db.collection('build_books').find_one({'job_id': _id}).sort('_id', 1)
                if last_one:
                    file = db.get_file(last_one.get('file_id'))
                    file.delete()
                    db.collection('build_books').delete_one({'job_id': _id})

            with NamedTemporaryFile(mode='w+b', delete=True) as fp:
                bookname = data.get('book_name')
                make_zip(bookspace, fp.name)
                with open(fp.name, mode='rb') as stream:
                    filename = bookname + '.zip'
                    file_id = db.save_file(filename=filename, fileobj=stream)
                    store_info = {
                        'task_id': task_id,
                        'file_id': file_id,
                        'job_id': _id,
                        'filename': os.path.basename(bookspace),
                        'created_at': time()
                    }
                    db.collection('build_books').insert_one(store_info)
                    shutil.rmtree(bookspace)

    except Exception as e:
        result = e.args
        logger.error('run task with exception: {}'.format(str(e)), extra=extra)

        raise e
    finally:
        content = temp_stdout.getvalue()
        sys.stdout = old_stdout
        sys.stderr = old_stderr
        eclogue_logger = get_logger('eclogue')
        extra.update({'task_id': str(task_id), 'currentUser': username})
        eclogue_logger.info(content, extra=extra)
        finish_at = time()
        update = {
            '$set': {
                'start_at': start_at,
                'finish_at': finish_at,
                'state': state,
                'duration': finish_at - start_at,
                'result': result,
            }
        }
        db.collection('tasks').update_one({'_id': task_id}, update=update)


def run_schedule_task(_id, request_id, username, **kwargs):
    db = Mongo()
    params = (_id, request_id, username)
    queue_name = get_queue_by_job(_id)
    job = db.collection('jobs').find_one({'_id': ObjectId(_id)})
    func = run_task
    if job.get('type') == 'adhoc':
        func = run_adhoc_task

    task = Task(tiger, func=func, args=params, kwargs=kwargs, queue=queue_name,
                unique=False, lock=True, lock_key=_id)
    task_record = {
        'job_id': _id,
        'state': QUEUED,
        'type': 'schedule',
        'ansible': job.get('type'),
        'queue': queue_name,
        'result': '',
        'request_id': request_id,
        't_id': task.id,
        'created_at': time(),
    }

    db.collection('tasks').insert_one(task_record)
    task.delay()


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
