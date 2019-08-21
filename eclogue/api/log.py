from flask import request, jsonify
from eclogue.model import db
from eclogue.middleware import jwt_required


@jwt_required
def log_query():
    query = request.args or {}
    log_type = query.get('type')
    keyword = query.get('keyword')
    q = query.get('q')
    kwargs = {}
    page = int(query.get('page', 1))
    limit = int(query.get('pageSize', 50))
    skip = (page - 1) * limit
    where = dict()
    if log_type:
        where['name'] = log_type

    if keyword:
        where['message'] = {
            '$regex': keyword
        }

    if q:
        where.update(kwargs)

    cursor = db.collection('logs').find(where, skip=skip, limit=limit)
    total = cursor.count()

    return jsonify({
        'message': 'ok',
        'code': 0,
        'data': {
            'list': list(cursor),
            'total': total,
            'page': page,
            'pageSize': limit,
        }
    })

