import time
from bson import  ObjectId
from eclogue.middleware import jwt_required, login_user
from flask import request, jsonify
from eclogue.model import db
from eclogue.models.user import User
from eclogue.models.role import Role
from eclogue.models.menu import Menu


@jwt_required
def get_roles():
    query = request.args
    page = int(query.get('page', 1))
    size = int(query.get('size', 50))
    offset = (page - 1) * size
    keyword = query.get('keyword')
    user = User()
    username = login_user.get('username')
    is_admin = login_user.get('is_admin')
    data = []
    total = 0
    role = Role()
    print(is_admin)
    if not is_admin:
        user_info = user.collection.find_one({'username': username})
        where = {
            'user_id': str(user_info['_id']),
        }
        roles = db.collection('user_roles').find(where)
        roles = list(roles)
        if roles:
            role_ids = map(lambda i: ObjectId(i['role_id']), roles)
            where = {
                '_id': {
                    '$in': list(role_ids),
                },
            }
            if keyword:
                where['name'] = {
                    '$regex': keyword
                }

            print(where)
            cursor = role.collection.find(where, skip=offset, limit=size)
            total = cursor.count()
            data = list(cursor)
    else:
        cursor = role.collection.find({}, skip=offset, limit=size)
        total = cursor.count()
        data = list(cursor)

    return jsonify({
        'message': 'ok',
        'code': 0,
        'data': {
            'page': page,
            'pageSize': size,
            'total': total,
            'list': data,
        },
    })


@jwt_required
def add_role():
    payload = request.get_json()
    if not payload:
        return jsonify({
            'message': 'invalid params',
            'code': 104000
        }), 400

    name = payload.get('name')
    description = payload.get('description')
    tags = payload.get('tags')
    role_type = payload.get('type')
    parent = payload.get('parent', None)
    alias = payload.get('alias')
    menus = payload.get('permissions')
    if not name:
        return jsonify({
            'message': 'invalid params',
            'code': 104000,
        }), 400

    role = Role()
    record = role.collection.find_one({'name': name})
    if record:
        return jsonify({
            'message': 'name existed',
            'code': 104001
        }), 400

    data = {
        'name': name,
        'alias': alias,
        'type': role_type,
        'tags': tags,
        'description': description,
        'parent': parent,
        'created_at': time.time()
    }

    if parent:
        check = role.find_by_id(parent)
        if not check:
            return jsonify({
                'message': 'invalid param',
                'code': 104001
            }), 400

    result = role.collection.insert_one(data)
    role_id = result.inserted_id
    if menus and type(menus) == dict:
        model = Menu()
        data = []
        methods = {
            'read': ['option', 'get'],
            'edit': ['post', 'put', 'patch'],
            'delete': ['delete']
        }
        for _id, actions in menus.items():
            record = model.find_by_id(_id)
            if not record:
                continue

            action_list = []
            for action in actions:
                if not methods.get(action):
                    continue

                action_list.extend(methods.get(action))

            data.append({
                'role_id': str(role_id),
                'm_id': _id,
                'actions': action_list,
                'created_at': time.time(),
                'add_by': login_user.get('username'),
            })

        db.collection('role_menus').insert_many(data)

    return jsonify({
        'message': 'ok',
        'code': 0,
    })


@jwt_required
def update_role(_id):
    payload = request.get_json()
    if not payload:
        return jsonify({
            'message': 'invalid params',
            'code': 104000
        }), 400

    record = Role().find_by_id(_id)
    if not record:
        return jsonify({
            'message': 'record not found',
            'code': 104040
        }), 404

    role_id = record.get('_id')
    name = payload.get('name')
    description = payload.get('description')
    tags = payload.get('tags')
    role_type = payload.get('type')
    parent = payload.get('parent', None)
    alias = payload.get('alias')
    menus = payload.get('permissions')
    data = {
        'name': name,
        'alias': alias,
        'type': role_type,
        'tags': tags,
        'parent': parent,
        'description': description,
    }

    update = {
        '$set': data
    }

    db.collection('roles').update_one({'_id': record['_id']}, update=update)
    if menus and type(menus) == dict:
        model = Menu()
        methods = {
            'read': ['option', 'get'],
            'edit': ['post', 'put', 'patch'],
            'delete': ['delete']
        }
        for _id, actions in menus.items():
            record = model.find_by_id(_id)
            if not record:
                continue

            action_list = []
            for action in actions:
                if not methods.get(action):
                    continue

                action_list.extend(methods.get(action))

            data = {
                'role_id': str(role_id),
                'm_id': _id,
                'actions': action_list,
            }

            where = {
                'role_id': str(role_id),
                'm_id': _id,
            }
            check = db.collection('role_menus').find_one(where)
            if not check:
                data['created_at'] = time.time(),
                data['add_by'] = login_user.get('username'),
                db.collection('role_menus').insert_one(data)
            else:
                db.collection('role_menus').update_one(where, update={'$set': data})

    return jsonify({
        'message': 'ok',
        'code': 0,
    })