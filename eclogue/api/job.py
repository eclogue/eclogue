import os
import time
import datetime
import base64
import yaml
import json

from bson import ObjectId
from tempfile import NamedTemporaryFile, TemporaryDirectory
from flask import request, jsonify
from jinja2 import Template

from eclogue.model import db
from eclogue.middleware import jwt_required, login_user
from eclogue.lib.helper import parse_cmdb_inventory, parse_file_inventory, load_ansible_playbook
from eclogue.lib.inventory import get_inventory_from_cmdb, get_inventory_by_book
from eclogue.lib.workspace import Workspace
from eclogue.ansible.runer import PlayBookRunner, AdHocRunner
from eclogue.ansible.plugins.callback import CallbackModule
from eclogue.lib.credential import get_credential_content_by_id
from eclogue.tasks.dispatch import run_job, get_tasks_by_job
from eclogue.ansible.doc import AnsibleDoc
from eclogue.ansible.playbook import check_playbook
from eclogue.models.job import Job
from eclogue.models.playbook import Playbook
from eclogue.lib.logger import logger
from flask_log_request_id import current_request_id
from eclogue.utils import extract
from eclogue.models.book import Book
from eclogue.models.task import Task
from eclogue.models.application import Application


@jwt_required
def get_job(_id):
    username = login_user.get('username')
    if not _id:
        return jsonify({
            'message': 'invalid id',
            'code': 154000
        }), 400

    job = Job.find_one({
        '_id': ObjectId(_id),
        'maintainer': {'$in': [username]}
    })

    # @todo job status
    if not job:
        return jsonify({
            'message': 'invalid id',
            'code': 154001,
        }), 400

    template = job.get('template')
    inventory_type = template.get('inventory_type')
    inventory = template.get('inventory')
    if job.get('type') == 'adhoc':
        inventory_content = parse_cmdb_inventory(inventory)
        return jsonify({
            'message': 'ok',
            'code': 0,
            'data': {
                'record': job,
                'previewContent': inventory_content,
            },
        })

    if inventory_type == 'file':
        inventory_content = parse_file_inventory(inventory)
    else:
        inventory_content = parse_cmdb_inventory(inventory)

    check_playbook(job['book_id'])
    if inventory_type == 'file':
        book = Book.find_one({'_id': ObjectId(job['book_id'])})
        if not book:
            hosts = []
        else:
            hosts = get_inventory_by_book(book.get('_id'), book_name=book.get('name'))
    else:
        hosts = get_inventory_from_cmdb()

    roles = []
    condition = {
        'book_id': str(job['book_id']),
        'role': 'roles',
        'is_dir': True
    }
    parent = Playbook.find_one(condition)
    if parent:
        where = {
            'book_id': job['book_id'],
            'is_dir': True,
            'parent': parent.get('path')
        }
        cursor = Playbook.find(where)
        roles = list(cursor)

    logs = None
    task = Task.find_one({'job_id': _id})
    if task:
        log = db.collection('logs').find_one({'task_id': str(task['_id'])})
        if log:
            logs = log.get('message')

    return jsonify({
        'message': 'ok',
        'code': 0,
        'data': {
            'record': job,
            'previewContent': inventory_content,
            'hosts': hosts,
            'roles': roles,
            'logs': logs,
        },
    })


@jwt_required
def get_jobs():
    username = login_user.get('username')
    query = request.args
    page = int(query.get('page', 1))
    size = int(query.get('pageSize', 50))
    offset = (page - 1) * size
    is_admin = login_user.get('is_admin')
    keyword = query.get('keyword')
    status = query.get('status')
    job_type = query.get('type')
    start = query.get('start')
    end = query.get('end')
    where = {
        'status': {
            '$gt': -1
        }
    }

    if not is_admin:
        where['maintainer'] = {'$in': [username]}

    if keyword:
        where['name'] = {
            '$regex': keyword
        }

    if status is not None:
        where['status'] = status

    if job_type:
        where['type'] = job_type

    date = []
    if start:
        date.append({
            'created_at': {
                '$gte': int(time.mktime(time.strptime(start, '%Y-%m-%d')))
            }
        })

    if end:
        date.append({
            'created_at': {
                '$lte': int(time.mktime(time.strptime(end, '%Y-%m-%d')))
            }
        })

    if date:
        where['$and'] = date

    jobs = db.collection('jobs').find(where, skip=offset, limit=size)
    total = jobs.count()
    jobs = list(jobs)

    return jsonify({
        'message': 'ok',
        'code': 0,
        'data': {
            'list': jobs,
            'total': total,
            'page': page,
            'pageSize': size,
        },
    })


@jwt_required
def add_jobs():
    """
    add job
    TODO(sang)
    :return: json
    """
    body = request.get_json()
    user = login_user
    if not body:
        return jsonify({
            'message': 'miss required params',
            'code': 104000,
        }), 400

    job_type = body.get('type')
    if job_type == 'adhoc':
        return add_adhoc()

    current_id = body.get('currentId')
    record = None
    if current_id:
        record = Job.find_by_id(current_id)
        if not record:
            return jsonify({
                'message': 'job not found',
                'code': 104044
            }), 400

    payload = load_ansible_playbook(body)
    if payload.get('message') is not 'ok':
        return jsonify(payload), 400

    data = payload.get('data')
    options = data.get('options')
    is_check = body.get('check')
    private_key = data.get('private_key')
    wk = Workspace()
    res = wk.load_book_from_db(name=data.get('book_name'), roles=data.get('roles'))
    if not res:
        return jsonify({
            'message': 'book not found',
            'code': 104000,
        }), 400

    entry = wk.get_book_entry(data.get('book_name'),  data.get('entry'))
    dry_run = bool(is_check)
    options['check'] = dry_run
    if dry_run:
        with NamedTemporaryFile('w+t', delete=True) as fd:
            if private_key:
                key_text = get_credential_content_by_id(private_key, 'private_key')
                if not key_text:
                    return jsonify({
                        'message': 'invalid private_key',
                        'code': 104033,
                    }), 401

                fd.write(key_text)
                fd.seek(0)
                options['private_key'] = fd.name

            play = PlayBookRunner(data['inventory'], options, callback=CallbackModule())
            play.run(entry)

            return jsonify({
                'message': 'ok',
                'code': 0,
                'data': {
                    'result': play.get_result(),
                    'options': options
                }
            })

    name = data.get('name')
    existed = Job.find_one({'name': name})
    if existed and not current_id:
        return jsonify({
            'message': 'name existed',
            'code': 104001,
        }), 400

    token = str(base64.b64encode(bytes(current_request_id(), 'utf8')), 'utf8')
    new_record = {
        'name': name,
        'type': 'playbook',
        'token': token,
        'description': data.get('description'),
        'book_id': data.get('book_id'),
        'template': data.get('template'),
        'extra': data.get('extra'),
        'entry': data['entry'],
        'status': data['status'],
        'maintainer': [user.get('username')],
        'created_at': int(time.time()),
        'updated_at': datetime.datetime.now().isoformat(),
    }

    if record:
        Job.update_one({'_id': record['_id']}, update={'$set': new_record})
    else:
        Job.insert_one(new_record)

    return jsonify({
        'message': 'ok',
        'code': 0,
    })


@jwt_required
def delete_job(_id):
    record = Job.find_by_id(ObjectId(_id))
    if not record:
        return jsonify({
            'message': 'record not found',
            'code': 104040
        }), 404

    update = {
        '$set': {
            'status': -1
        }
    }

    Job.update_one({'_id': record['_id']}, update=update)
    extra = {
        'record': record
    }
    logger.info('delete job', extra=extra)

    return jsonify({
        'message': 'ok',
        'code': 0,
    })


@jwt_required
def check_job(_id):
    record = Job.find_one({'_id': ObjectId(_id)})
    if not record:
        return jsonify({
            'message': 'job not found',
            'code': 104001
        }), 400

    body = {
        'template': record.get('template'),
        'extra': record.get('extra')
    }

    payload = load_ansible_playbook(body)
    if payload.get('message') is not 'ok':
        return jsonify(payload), 400

    data = payload.get('data')
    options = data.get('options')
    private_key = data.get('private_key')
    wk = Workspace()
    res = wk.load_book_from_db(name=data.get('book_name'), roles=data.get('roles'))
    if not res:
        return jsonify({
            'message': 'book not found',
            'code': 104000,
        }), 400

    entry = wk.get_book_entry(data.get('book_name'), data.get('entry'))
    with NamedTemporaryFile('w+t', delete=True) as fd:
        key_text = get_credential_content_by_id(private_key, 'private_key')
        if not key_text:
            return jsonify({
                'message': 'invalid private_key',
                'code': 104033,
            }), 401
        fd.write(key_text)
        fd.seek(0)
        options['private_key'] = fd.name
        play = PlayBookRunner(data['inventory'], options)
        play.run(entry)
        result = play.get_result()

        return jsonify({
            'message': 'ok',
            'code': 0,
            'data': result
        })


@jwt_required
def job_detail(_id):
    query = request.args
    record = db.collection('jobs').find_one({'_id': ObjectId(_id)})
    if not record:
        return jsonify({
            'message': 'record not found',
            'code': 104040,
        }), 404

    if record.get('type') == 'adhoc':
        template = record.get('template')
        inventory = template.get('inventory')
        inventory_content = parse_cmdb_inventory(inventory)
        template['inventory_content'] = inventory_content
    else:
        book = db.collection('books').find_one({'_id': ObjectId(record.get('book_id'))})
        record['book_name'] = book.get('name')
        template = record.get('template')
        if template:
            app_id = template.get('app')
            if app_id:
                app = db.collection('apps').find_one({'_id': ObjectId(app_id)})
                if app:
                    template['app_name'] = app.get('name')
                    template['app_params'] = app.get('params')

            inventory_type = template.get('inventory_type')
            inventory = template.get('inventory')
            if inventory_type == 'file':
                inventory_content = parse_file_inventory(inventory)
            else:
                inventory_content = parse_cmdb_inventory(inventory)

            template['inventory_content'] = inventory_content
            role_ids = template.get('roles')
            if role_ids:
                roles = Playbook.find_by_ids(role_ids)
                template['roles'] = list(map(lambda i: i.get('name'), roles))

    page = int(query.get('page', 1))
    size = int(query.get('pageSize', 20))
    offset = (page - 1) * size
    tasks = get_tasks_by_job(_id, offset=offset, limit=size)
    tasks = list(tasks)
    logs = []
    sort = [('_id', -1)]
    task = db.collection('tasks').find_one({'job_id': _id}, sort=sort)
    if task:
        records = db.collection('task_logs').find({'task_id': str(task['_id'])})
        for item in records:
            logs.append({
                'content': str(item.get('content')),
                'created_at': item.get('created_at')
            })

    return jsonify({
        'message': 'ok',
        'code': 0,
        'data': {
            'job': record,
            'logs': logs,
            'tasks': tasks,
        }
    })


def runner_doc():
    query = request.args
    if not query:
        return jsonify({
            'message': 'invalid params',
            'code': 104001
        })

    module = query.get('module')
    if not module:
        return jsonify({
            'message': 'invalid module',
            'code': 104002
        })

    doc = AnsibleDoc(module)
    # result = doc.store_modules()
    result = doc.run()

    return jsonify({
        'message': 'ok',
        'code': 0,
        'data': result,
    })


def runner_module():
    query = request.args
    if not query:
        return jsonify({
            'message': 'invalid params',
            'code': 104001
        })

    keyword = query.get('keyword')

    where = {}
    if keyword:
        where = {
            'name': {
                '$regex': '^' + keyword
            }
        }

    records = db.collection('ansible_modules').find(where, limit=10)

    return jsonify({
        'message': 'ok',
        'data': list(records)
    })


@jwt_required
def add_adhoc():
    payload = request.get_json()
    if not payload:
        return jsonify({
            'message': 'invalid params',
            'code': 104001,
        }), 400

    module = payload.get('module')
    args = payload.get('args')
    inventory = payload.get('inventory')
    private_key = payload.get('private_key')
    verbosity = payload.get('verbosity')
    name = payload.get('name')
    schedule = payload.get('schedule')
    check = payload.get('check')
    job_id = payload.get('job_id')
    extra_options = payload.get('extraOptions')
    status = int(payload.get('status', 0))
    notification = payload.get('notification')
    maintainer = payload.get('maintainer') or []
    if maintainer and isinstance(maintainer, list):
        users = db.collection('users').find({'username': {'$in': maintainer}})
        names = list(map(lambda i: i['username'], users))
        maintainer.extend(names)

    maintainer.append(login_user.get('username'))
    if not job_id:
        existed = db.collection('jobs').find_one({'name': name})
        if existed and existed.get('status') != -1:
            return jsonify({
                'message': 'name exist',
                'code': 104007
            }), 400

    if not module or not inventory or not name:
        return jsonify({
            'message': 'miss required params',
            'code': 104002,
        }), 400

    # check_module = db.collection('ansible_modules').find_one({
    #     'name': module
    # })
    #
    # if not check_module:
    #     return jsonify({
    #         'message': 'invalid module',
    #         'code': 104003,
    #     }), 400

    inventory_content = parse_cmdb_inventory(inventory)
    if not inventory:
        return jsonify({
            'message': 'invalid inventory',
            'code': 104004,
        }), 400

    key_text = get_credential_content_by_id(private_key, 'private_key')
    if not key_text:
        return jsonify({
            'message': 'invalid private key',
            'code': 104004,
        }), 400

    options = {}
    if extra_options:
        options.update(extra_options)

    if verbosity:
        options['verbosity'] = verbosity

    if check:
        with NamedTemporaryFile('w+t', delete=True) as fd:
            fd.write(key_text)
            fd.seek(0)
            options['private_key'] = fd.name
            tasks = [{
                'action': {
                    'module': module,
                    'args': args
                }
            }]
            hosts = inventory_content
            runner = AdHocRunner(hosts, options=options)
            runner.run('all', tasks)
            result = runner.get_result()

            return jsonify({
                'message': 'ok',
                'code': 0,
                'data': result
            })

    else:
        token = str(base64.b64encode(bytes(current_request_id(), 'utf8')), 'utf8')
        data = {
            'name': name,
            'template': {
                'inventory': inventory,
                'private_key': private_key,
                'verbosity': verbosity,
                'module': module,
                'args': args,
                'extraOptions': extra_options,
            },
            'extra': {
                'schedule': schedule,
                'notification': notification,
            },
            'token': token,
            'maintainer': maintainer,
            'type': 'adhoc',
            'created_at': time.time(),
            'status': status,
            'add_by': login_user.get('username')
        }

        if job_id:
            record = db.collection('jobs').find_one({'_id': ObjectId(job_id)})
            if not record:
                return jsonify({
                    'message': 'record not found',
                    'code': 104040
                }), 404

            update = {
                '$set': data,
            }
            db.collection('jobs').update_one({'_id': ObjectId(job_id)}, update=update)
            logger.info('update job', extra={'record': record, 'changed': data})
        else:
            result = db.collection('jobs').insert_one(data)
            data['_id'] = result.inserted_id
            logger.info('add job', extra={'record': data})

    return jsonify({
        'message': 'ok',
        'code': 0,
    })


@jwt_required
def job_webhook():
    query = request.args
    token = query.get('token')
    payload = request.get_json()
    if not payload or not token:
        return jsonify({
            'message': 'invalid params',
            'code': 104000
        }), 400

    record = Job().collection.find_one({'token': token})
    if not record:
        return jsonify({
            'message': 'illegal token',
            'code': 104010
        }), 401

    if record.get('type') == 'adhoc':
        task_id = run_job(str(record.get('_id')))
        if not task_id:
            return jsonify({
                'message': 'try to queue task faield',
                'code': 104008
            }), 400

        return jsonify({
            'message': 'ok',
            'code': 0,
            'data': task_id
        })

    template = record.get('template')
    app_id = template.get('app')
    income_params = {'cache': True}
    if app_id:
        app_info = Application.find_by_id(app_id)
        if not app_info:
            return jsonify({
                'message': 'app not found, please check your app',
                'code': 104001
            }), 400

        app_params = app_info.get('params')
        income = app_params.get('income')
        if income and payload.get('income'):
            income = Template(income)
            tpl = income.render(**payload.get('income'))
            tpl = yaml.safe_load(tpl)
            if tpl:
                income_params.update(tpl)

    task_id = run_job(str(record.get('_id')), **income_params)
    if not task_id:
        return jsonify({
            'message': 'put job enqueue failed',
            'code': 104002
        }), 400

    # if app_type == 'jenkins':
    #     build_id = '19'
    #     job_name = 'upward'
    #     run_job(_id, job_name, build_id)
    # elif app_type == 'gitlab':
    #     project_id = '13539397'
    #     job_id = '261939258'
    #     run_job(_id, project_id, job_id)
    # else:
    #     run_job(_id)

    # logger.error('test', extra={'a': {'b': 1}})

    return jsonify({
        'message': 'ok',
        'code': 0,
        'data': task_id
    })

