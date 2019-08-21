import time
from bson import ObjectId
from flask import request, jsonify
from eclogue.model import db
from eclogue.middleware import jwt_required, login_user
from eclogue.lib.integration import Integration
from eclogue.lib.logger import logger


def get_apps():
    query = request.args
    page = int(query.get('page', 1))
    size = int(query.get('pageSize', 50))
    offset = (page - 1) * size
    keyword = query.get('keyword')
    where = {}
    if keyword:
        where = {
            'name': {
                '$regex': keyword
            }
        }

    cursor = db.collection('apps').find(where, skip=offset, limit=size)
    total = cursor.count()

    return jsonify({
        'message': 'ok',
        'code': 0,
        'data': {
            'list': list(cursor),
            'total': total,
            'page': page,
            'pageSize': size
        }
    })
    pass


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
    maintainer = []
    maintainer.append(current_user)
    maintainer = set(maintainer)
    data = {
        'name': name,
        'server': server,
        'document': document,
        'type': app_type,
        'params': params,
        'repo': repo,
        'protocol': protocol,
        'port': port,
        'description': description,
        'maintainer': list(maintainer),
        'add_by': login_user.get('username'),
        'created_at': int(time.time())
    }
    logger.info('add apps', extra={'record': data})
    db.collection('apps').insert_one(data)

    return jsonify({
        'message': 'ok',
        'code': 0,
    })


def update_app(_id):
    pass


