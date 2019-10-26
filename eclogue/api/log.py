import time

from flask import request, jsonify
from urllib import parse
from eclogue.model import db
from eclogue.middleware import jwt_required


@jwt_required
def log_query():
    query = request.args or {}
    log_type = query.get('logType')
    keyword = query.get('keyword')
    level = query.get('level')
    q = query.get('q')
    start = query.get('start')
    end = query.get('end')
    page = int(query.get('page', 1))
    limit = int(query.get('pageSize', 50))
    skip = (page - 1) * limit
    where = dict()
    if log_type:
        where['loggerName'] = log_type

    if level:
        where['level'] = level.upper()

    if keyword:
        where['message'] = {
            '$regex': keyword
        }

    if q:
        q = dict(parse.parse_qsl(q))
        where.update(q)

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

