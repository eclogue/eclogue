from bson import ObjectId
from flask import jsonify, request
from eclogue.middleware import jwt_required, login_user
from eclogue.model import db
from eclogue.utils import collection_array
import time


@jwt_required
def show():
    user = login_user
    page = request.args.get('page', 1)
    size = request.args.get('pagesize', 20)
    condition = {
        'status': 1
    }
    skip = int((page - 1) * size)
    cursor = db.collection('books').find(filter=condition, skip=skip, limit=size)
    total = cursor.count()
    books = collection_array(cursor)

    return jsonify({
        'message': 'ok',
        'code': 0,
        'data': {
            'page': page,
            'pagesize': size,
            'list': books,
            'total': total,
        }
    })


def get_playbook(name):
    filter = {
        'book_name': name,
        'is_dir': True,
        'role': 'role',
    }
    cursor = db.collection('playbook').find(filter)
    return jsonify({
        'message': 'ok',
        'code': 0,
        'data': collection_array(cursor),
    })


def get_entry(_id):
    book = db.collection('books').find_one(({
        '_id': ObjectId(_id)
    }))
    if not book:
        return jsonify({
            'message': 'book not found',
            'code': 164000
        }), 400

    where = {
        'book_id': str(book.get('_id')),
        'is_dir': False,
        'role': 'entry',
    }
    cursor = db.collection('playbook').find(where)

    return jsonify({
        'message': 'ok',
        'code': 0,
        'data': list(cursor),
    })
