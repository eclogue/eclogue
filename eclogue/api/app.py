import time
from bson import ObjectId
from flask import request, jsonify, current_app
from eclogue.model import db
from eclogue.middleware import jwt_required, login_user
from eclogue.lib.integration import Integration
from eclogue.lib.logger import logger
from eclogue.models.application import Application


def get_apps():
    query = request.args
    page = int(query.get('page', 1))
    size = int(query.get('pageSize', 50))
    offset = (page - 1) * size
    keyword = query.get('keyword')
    start = query.get('start')
    end = query.get('end')
    app_type = query.get('type')
    status = query.get('status')
    where = {}
    if keyword:
        where = {
            'name': {
                '$regex': keyword
            }
        }

    if app_type:
        where['type'] = app_type

    if status is not None:
        where['status'] = status

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

    cursor = db.collection('apps').find(where, skip=offset, limit=size)
    total = cursor.count()
    records = []
    for app in cursor:
        job = db.collection('jobs').find_one({'template.app': str(app['_id'])})
        app['job'] = None
        if job:
            app['job'] = {
                '_id': job['_id'],
                'type': job.get('type'),
                'name': job.get('name'),
            }
        records.append(app)

    return jsonify({
        'message': 'ok',
        'code': 0,
        'data': {
            'list': records,
            'total': total,
            'page': page,
            'pageSize': size
        }
    })


@jwt_required
def get_app(_id):
    record = db.collection('apps').find_one(({'_id': ObjectId(_id)}))
    if not record:
        return jsonify({
            'message': 'record not found',
            'code': 174041
        }), 404

    return jsonify({
        'message': 'ok',
        'code': 0,
        'data': record,
    })


@jwt_required
def add_apps():
    current_user = login_user.get('username')
    payload = request.get_json()
    if not payload:
        return jsonify({
            'message': 'empty params',
            'code': 174000,
        }), 400

    name = payload.get('name')
    app_type = payload.get('type')
    params = payload.get('params')
    integration = Integration(app_type, params)
    check = integration.check_app_params()
    if not check:
        return jsonify({
            'message': 'invalid ' + app_type + 'params',
            'code': 174003
        }), 400

    if not name or not app_type or not params:
        return jsonify({
            'message': 'miss required params',
            'code': 174001,
        }), 400

    existed = db.collection('apps').find_one({'name': name})
    if existed:
        return jsonify({
            'message': 'name existed',
            'code': 174002,
        }), 400

    repo = payload.get('repo')
    server = payload.get('server')
    document = payload.get('document')
    protocol = payload.get('protocol')
    port = payload.get('port')
    description = payload.get('description')
    # @todo
    # maintainer = payload.get('maintainer') or []
    maintainer = [current_user]
    maintainer = set(maintainer)
    data = {
        'name': name,
        'server': server,
        'document': document,
        'type': app_type,
        'params': params,
        'repo': repo,
        'status': 1,
        'protocol': protocol,
        'port': port,
        'description': description,
        'maintainer': list(maintainer),
        'add_by': login_user.get('username'),
        'created_at': int(time.time())
    }
    logger.info('add apps', extra={'record': data})
    Application.insert_one(data)

    return jsonify({
        'message': 'ok',
        'code': 0,
    })


@jwt_required
def update_app(_id):
    payload = request.get_json()
    if not payload:
        return jsonify({
            'message': 'empty params',
            'code': 174000,
        }), 400

    record = db.collection('apps').find_one({'_id': ObjectId(_id)})
    if not record:
        return jsonify({
            'message': 'record not found',
            'code': 104040
        }), 404

    name = payload.get('name')
    app_type = payload.get('type')
    params = payload.get('params')
    repo = payload.get('repo')
    server = payload.get('server')
    document = payload.get('document')
    protocol = payload.get('protocol')
    port = payload.get('port')
    description = payload.get('description')
    integration = Integration(app_type, params)
    check = integration.check_app_params()
    update = {}
    if not check:
        return jsonify({
            'message': 'invalid ' + app_type + 'params',
            'code': 174003
        }), 400

    if name != record.get('name'):
        existed = db.collection('apps').find_one({'name': name})
        if existed:
            return jsonify({
                'message': 'name existed',
                'code': 104001
            }), 400

        update['name'] = name

    if app_type:
        update['type'] = app_type

    if params:
        update['params'] = params

    if server:
        update['server'] = server

    if document:
        update['document'] = document

    if repo:
        update['repo'] = repo

    if port:
        update['port'] = port

    if protocol:
        update['protocol'] = protocol

    if description:
        update['description'] = description

    if update:
        update['updated_at'] = time.time()

    data = {'$set': update}
    # maintainer = payload.get('maintainer') or []
    db.collection('apps').update_one({'_id': record['_id']}, update=data)
    logger.info('add apps', extra={'record': record, 'changed': update})

    return jsonify({
        'message': 'ok',
        'code': 0,
    })


def test_docker():
    # print(current_app.logger.handlers)
    logger.info('aaaatest23412288886666')
    # client = Docker({
    #     'base_url': None,
    #     'image': 'alpine:latest',
    # })
    # # result = client.run(command='pwd', working_dir='/usr/lib', detach=False)
    # # print(result)
    # client.install('/usr/lib')

    return jsonify({
        'message': 'ok'
    })
