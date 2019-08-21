import time
import datetime
import base64

from bson import ObjectId
from tempfile import NamedTemporaryFile
from flask import request, jsonify
from eclogue.model import db
from eclogue.middleware import jwt_required, login_user
from eclogue.lib.helper import parse_cmdb_inventory, parse_file_inventory, load_ansible_playbook
from eclogue.lib.inventory import get_inventory_from_cmdb, get_inventory_by_book
from eclogue.lib.workspace import Workspace
from eclogue.ansible.runer import PlayBookRunner, AdHocRunner
from eclogue.lib.credential import get_credential_content_by_id
from eclogue.tasks.dispatch import run_job, get_tasks_by_job
from eclogue.ansible.doc import AnsibleDoc
from eclogue.ansible.playbook import check_playbook
from eclogue.models.job import Job
from eclogue.lib.logger import logger
from flask_log_request_id import current_request_id


@jwt_required
def get_job(_id):
    username = login_user.get('username')
    if not _id:
        return jsonify({
            'message': 'invalid id',
            'code': 154000
        }), 400

    job = db.collection('jobs').find_one({
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
    if inventory_type == 'file':
        inventory_content = parse_file_inventory(inventory)
    else:
        inventory_content = parse_cmdb_inventory(inventory)

    check_playbook(job['book_id'])
    if inventory_type == 'file':
        book = db.collection('books').find_one({'_id': ObjectId(job['book_id'])})
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
    parent = db.collection('playbook').find_one(condition)
    if parent:
        where = {
            'book_id': job['book_id'],
            'is_dir': True,
            'parent': parent.get('path')
        }
        cursor = db.collection('playbook').find(where)
        roles = list(cursor)

    return jsonify({
        'message': 'ok',
        'code': 0,
        'data': {
            'record': job,
            'previewContent': inventory_content,
            'hosts': hosts,
            'roles': roles,
        },
    })


@jwt_required
def get_jobs():
    username = login_user.get('username')
    query = request.args
    page = int(query.get('page', 1))
    size = int(query.get('pageSize', 50))
    offset = (page - 1) * size
    where = {
        'maintainer': {'$in': [username]}
    }
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
        record = db.collection('jobs').find_one({'_id': ObjectId(current_id)})
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
    is_check = body.get('check', False)
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
            key_text = get_credential_content_by_id(private_key, 'private_key')
            if not key_text:
                return jsonify({
                    'message': 'invalid private_key',
                    'code': 104033,
                }), 401
            fd.write(key_text)
            fd.seek(0)
            options['private_key'] = fd.name
            options['verbosity'] = 5
            play = PlayBookRunner(data['inventory'], options)
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
    existed = db.collection('jobs').find_one({'name': name})
    if existed and not current_id:
        return jsonify({
            'message': 'name existed',
            'code': 104001,
        }), 400

    token = str(base64.b64encode(bytes(current_request_id)))
    new_record = {
        'name': name,
        'token': token,
        'description': data.get('description'),
        'book_id': data.get('book_id'),
        'template': data.get('template'),
        'extra': data.get('extra'),
        'entry': data['entry'],
        'status': 0,
        'maintainer': [user.get('username')],
        'created_at': int(time.time()),
        'updated_at': datetime.datetime.now().isoformat(),
    }
    if record:
        db.collection('jobs').update_one({'_id': record['_id']}, update={'$set': new_record})
        logger.info('update job', {'record': record, 'changed': new_record})
    else:
        result = db.collection('jobs').insert_one(new_record)
        new_record['_id'] = result.inserted_id
        logger.info('add job', extra={'record': new_record})

    return jsonify({
        'message': 'ok',
        'code': 0,
    })


def check_job(_id):
    record = db.collection('jobs').find_one({'_id': ObjectId(_id)})
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


def job_detail(_id):
    query = request.args
    record = db.collection('jobs').find_one({'_id': ObjectId(_id)})
    if not record:
        return jsonify({
            'message': 'record not found',
            'code': 104040,
        }), 404

    book = db.collection('books').find_one({'_id': ObjectId(record.get('book_id'))})
    record['book_name'] = book.get('name')
    template = record.get('template')
    if template:
        app_id = template.get('app')
        if app_id:
            app = db.collection('apps').find_one({'_id': ObjectId(app_id)})
            if app:
                template['app_name'] = app.get('name')
        inventory_type = template.get('inventory_type')
        inventory = template.get('inventory')
        if inventory_type == 'file':
            inventory_content = parse_file_inventory(inventory)
        else:
            inventory_content = parse_cmdb_inventory(inventory)
        template['inventory_content'] = inventory_content
    page = int(query.get('page', 1))
    size = int(query.get('pageSize', 20))
    offset = (page - 1) * size
    tasks = get_tasks_by_job(_id, offset=offset, limit=size)

    return jsonify({
        'message': 'ok',
        'code': 0,
        'data': {
            'job': record,
            'tasks': list(tasks),
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
    notification = payload.get('notification')
    schedule = payload.get('schedule')
    check = payload.get('check')
    job_id = payload.get('job_id')
    if not job_id:
        existed = db.collection('jobs').find_one({'name': name})
        if existed:
            return jsonify({
                'message': 'name exist',
                'code': 104007
            }), 400

    if not module or not inventory or not name:
        return jsonify({
            'message': 'miss required params',
            'code': 104002,
        }), 400

    check_module = db.collection('ansible_modules').find_one({
        'name': module
    })

    if not check_module:
        return jsonify({
            'message': 'invalid module',
            'code': 104003,
        }), 400

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
    options = {
        'verbosity': verbosity,
        'check': False
    }
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
        data = {
            'template': {
                'inventory': inventory,
                'private_key': private_key,
                'verbosity': verbosity,
                'module': module,
                'args': args,
                'maintainer': [],
                'schedule': schedule,
                'notification': notification,
            },
            'type': 'adhoc',
            'name': name,
            'created_at': time.time(),
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
            logger.log('update job', extra={'record': record, 'changed': data})
        else:
            result = db.collection('jobs').insert_one(data)
            data['_id'] = result.inserted_id
            logger.info('add job', extra={'record': data})

    return jsonify({
        'message': 'ok',
        'code': 0,
    })


def test_job():
    _id = '5d4058b4b9a76b7eea946b99'
    record = Job().find_by_id(_id)
    tempate = record.get('template')
    app_id = tempate.get('app')
    app_info = db.collection('apps').find_one({'_id': ObjectId(app_id)})
    app_type = app_info.get('type')
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

    logger.error('test', extra={'a': {'b': 1}})
    print(login_user)

    return jsonify({
        'message': 'ok',
        'code': 11111
    })
