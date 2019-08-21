import time
from bson import ObjectId
from flask import request, jsonify
from eclogue.middleware import jwt_required, login_user
from eclogue.model import db
from eclogue.models.notification import Notification


def add_notify(payload):
    if not payload:
        return {
                   'message': 'invalid params',
                   'code': 104000,
               }, 400

    user_id = payload.get('user_id')
    msg_type = payload.get('type', 'common')
    title = payload.get('title')
    content = payload.get('content')
    action = payload.get('action')
    params = payload.get('params')
    if not user_id:
        return {
                   'message': 'invalid user_id',
                   'code': 104001,
               }, 400

    if not msg_type:
        return {
                   'message': 'invalid type',
                   'code': 104001,
               }, 400

    if not title:
        return {
                   'message': 'invalid title',
                   'code': 104001,
               }, 400

    data = {
        'user_id': user_id,
        'type': msg_type,
        'title': title,
        'content': content,
        'action': action,
        'params': params,
        'created_at': time.time(),
    }

    db.collection('notifications').insert_one(data)

    return jsonify({
               'message': 'ok',
               'code': 0,
           }), 200


@jwt_required
def get_notify():
    query = request.args
    page = abs(int(query.get('page', 1)))
    size = abs(int(query.get('pageSize', 20)))
    sort = query.get('sort', '_id')
    unread = query.get('unread')
    skip = (page - 1) * size
    model = Notification()
    where = {
        'user_id': login_user.get('user_id')
    }

    if unread:
        where['read'] = 0

    cursor = model.collection.find(where, skip=skip, limit=size).sort(sort, -1)
    total = cursor.count()

    return jsonify({
        'message': 'ok',
        'code': 0,
        'data': {
            'list': list(cursor),
            'total': total,
            'page': page,
            'pageSize': size,
        }
    })


@jwt_required
def mark_read():
    payload = request.get_json()
    if not payload:
        return jsonify({
            'message': 'invalid params',
            'code': 104000
        }), 400

    ids = payload.get('ids')
    if type(ids) != list:
        return jsonify({
            'message': 'invalid param',
            'code': 104001
        }), 400

    user_id = login_user.get('user_id')
    for n_id in ids:
        where = {
            '_id': ObjectId(n_id),
            'user_id': user_id,
        }
        update = {
            '$set': {
                'read': 1,
            }
        }
        Notification().collection.update_one(where, update=update)

    return jsonify({
        'message': 'ok',
        'code': 0,
    })

