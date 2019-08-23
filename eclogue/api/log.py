from flask import request, jsonify
from urllib import parse
from eclogue.model import db
from eclogue.middleware import jwt_required


@jwt_required
def log_query():
    query = request.args or {}
    log_type = query.get('type')
    keyword = query.get('keyword')
    q = query.get('q')
    page = int(query.get('page', 1))
    limit = int(query.get('pageSize', 50))
    skip = (page - 1) * limit
    where = dict()
    if log_type:
        where['loggerName'] = log_type

    if keyword:
        where['message'] = {
            '$regex': keyword
        }

    if q:
        q = dict(parse.parse_qsl(q))
        where.update(q)

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

