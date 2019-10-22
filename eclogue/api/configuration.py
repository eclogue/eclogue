import time
import datetime
from bson import ObjectId
from flask import request, jsonify
from eclogue.middleware import jwt_required, login_user
from eclogue.model import db
from eclogue.models.configuration import Configuration
from eclogue.lib.logger import logger
from eclogue.models.playbook import Playbook
from eclogue.models.book import Book


@jwt_required
def list_config():
    query = request.args
    page = int(query.get('page', 1))
    size = int(query.get('pageSize', 50))
    offset = (page - 1) * size
    keyword = query.get('keyword')
    is_admin = login_user.get('is_admin')
    start = query.get('start')
    end = query.get('end')
    maintainer = query.get('maintainer')
    where = {
        'status': {
            '$ne': -1
        }
    }
    if keyword:
        where['name'] = {
            '$regex': keyword
        }

    if not is_admin:
        where['maintainer'] = {
            '$in': [login_user.get('username')]
        }
    elif maintainer:
        where['maintainer'] = {
            '$in': [maintainer]
        }

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

    cursor = db.collection('configurations').find(where, skip=offset, limit=size)
    total = cursor.count()
    bucket = []

    def get_registry(record):
        if not record:
            return None

        book_id = record.get('book_id')
        book = Book().find_by_id(book_id) or {}

        return {
            '_id': record['_id'],
            'playbook': record.get('name'),
            'path': record.get('path'),
            'book_name': book.get('name'),
            'book_id': book_id,
        }

    for item in cursor:
        register = db.collection('playbook').find({'register': {'$in': [str(item['_id'])]}})
        item['registry'] = list(map(get_registry, register))
        bucket.append(item)

    return jsonify({
        'message': 'ok',
        'code': 0,
        'data': {
            'list': bucket,
            'total': total,
            'page': page,
            'pageSize': size
        }
    })


@jwt_required
def add_configuration():
    payload = request.get_json()
    if not payload:
        return jsonify({
            'message': 'invalid params',
            'code': 184000,
        }), 400
    name = payload.get('name')
    if not name:
        return jsonify({
            'message': 'invalid name',
            'code': 184001,
        }), 400

    existed = db.collection('configurations').find_one({'name': name})
    if existed:
        return jsonify({
            'message': 'name existed',
            'code': 184002,
        }), 400

    description = payload.get('description')
    maintainer = payload.get('maintainer') or []
    variables = payload.get('variables')
    status = payload.get('status', 0) or 0
    data = {
        'name': name,
        'description': description,
        'maintainer': maintainer,
        'variables': variables,
        'status': status,
        'add_by': login_user.get('username'),
        'created_at': int(time.time())
    }

    result = db.collection('configurations').insert_one(data)
    data['_id'] = result.inserted_id
    logger.info('add configuration, name: {}'.format(name), extra={'record': data})

    return jsonify({
        'message': 'ok',
        'code': 0,
    })


def get_configs_by_ids():
    query = request.args
    ids = query.get('ids')
    if not ids:
        return jsonify({
            'message': 'invalid params',
            'code': 184000
        }), 400
    ids = ids.split(',')
    ids = map(lambda i: ObjectId(i), ids)
    where = {
        '_id': {
            '$in': list(ids)
        }
    }
    records = db.collection('configurations').find(where)

    return jsonify({
        'message': 'ok',
        'code': 0,
        'data': list(records)
    })


def get_register_config(playbook_id):
    where = {
        '_id': ObjectId(playbook_id)
    }

    record = db.collection('playbook').find_one(where)
    if not record:
        return jsonify({
            'message': 'record not found'
        }), 104040

    records = Configuration().find_by_ids(record.get('register'))

    return jsonify({
        'message': 'ok',
        'code': 0,
        'data': records,
    })


def get_config_info(_id):
    record = Configuration().find_by_id(_id)
    if not record:
        return jsonify({
            'message': 'record not found',
            'code': 0,
        }), 400

    return jsonify({
        'message': 'ok',
        'code': 0,
        'data': record,
    })


@jwt_required
def update_configuration(_id):
    payload = request.get_json()
    if not payload:
        return jsonify({
            'message': 'invalid params',
            'code': 184000,
        }), 400

    name = payload.get('name')
    record = db.collection('configurations').find_one({'_id': ObjectId(_id)})
    if not record:
        return jsonify({
            'message': 'record not found',
            'code': 104040,
        }), 404

    description = payload.get('description')
    maintainer = payload.get('maintainer') or []
    variables = payload.get('variables')
    status = payload.get('status')
    data = {}
    if name:
        data['name'] = name

    if description:
        data['description'] = description

    if variables:
        data['variables'] = variables

    if maintainer:
        data['maintainer'] = maintainer

    if status is not None:
        data['status'] = int(status)

    if len(data.keys()):
        update = {
            '$set': data,
        }
        db.collection('configurations').update_one({'_id': record['_id']}, update=update)
        msg = 'update configuration, name: {}'.format(record.get('name'))
        logger.info(msg, extra={'record': record, 'changed': data})

    return jsonify({
        'message': 'ok',
        'code': 0,
    })


@jwt_required
def delete(_id):
    record = db.collection('configurations').find_one({'_id': ObjectId(_id)})
    if not record:
        return jsonify({
            'message': 'record not found',
            'code': 104040,
        }), 404

    update = {
        '$set': {
            'status': -1,
            'updated_at': datetime.datetime.now()
        },
    }
    db.collection('configurations').update_one({'_id': record['_id']}, update=update)
    msg = 'update configuration, name: {}'.format(record.get('name'))
    logger.info(msg, extra={'record': record, 'force': False})

    return jsonify({
        'message': 'ok',
        'code': 0,
    })

