import time

from bson import ObjectId
from flask import request, jsonify
from eclogue.model import db
from eclogue.middleware import jwt_required, login_user
from eclogue.models.team import Team
from eclogue.models.user import User
from eclogue.models.menu import Menu
from eclogue.lib.logger import logger


@jwt_required
def add_team():
    payload = request.get_json()
    print(payload)
    if not payload:
        return jsonify({
            'message': 'invalid params',
            'code': 104000
        }), 400

    name = payload.get('name')
    description = payload.get('description')
    parent = payload.get('parent')
    record = db.collection('teams').find_one({'name': name})
    if record:
        return jsonify({
            'message': 'name existed',
            'code': 104001
        }), 400

    data = {
        'name': name,
        'description': description,
        'parent': parent,
        'add_by': login_user.get('username'),
        'created_at': time.time(),
    }

    result = db.collection('teams').insert_one(data)
    data['_id'] = result['_id']
    logger.info('add team', extra={'record': data})

    role = {
        'name': name,
        'type': 'team',
        'role': 'owner',
        'add_by': login_user.get('username'),
        'created_at': time.time(),
    }
    result = db.collection('roles').insert_one(role)
    role['_id'] = result.inserted_id
    role['team_id'] = data['_id']
    logger.info('add role by team', extra={'record': role})

    return jsonify({
        'message': 'ok',
        'code': 0,
    })


@jwt_required
def add_user_to_team():
    payload = request.get_json()
    if not payload:
        return jsonify({
            'message': 'invalid params',
            'code': 104000
        }), 400

    user_id = payload.get('user_id')
    team_id = payload.get('team_id')
    is_owner = payload.get('is_owner')
    team = Team().find_by_id(user_id)
    if not team:
        return jsonify({
            'message': 'invalid team',
            'code': 104031
        }), 400

    where = {
        'team_id': team_id,
        'user_id': user_id,
        'is_owner': is_owner,
    }

    data = where.copy()
    data['created_at'] = time.time()
    data['add_by'] = login_user.get('username')
    db.collection('team_members').update_one(where, {'$set': data}, upsert=True)
    role = db.collection('roles').find_one({
        'name': team.get('name'),
        'type': 'team',
    })

    return jsonify({
        'message': 'ok',
        'code': 0,
    })


def get_members(_id):
    records = db.collection('roles').find_one({'parent': _id})

    return jsonify({
        'message': 'ok',
        'code': 0,
        'data': records
    })


@jwt_required
def get_user_menus():
    username = login_user.get('username')
    user = db.collection('users').find_one({'username': username})
    records = db.collection('user_roles').find_one({'user_id': user.get('_id')})
    menus = set()
    for record in records:
        menus.update(record.get('menus'))

    menus = list(map(lambda i: ObjectId(i), menus))
    where = {
        '_id': {
            '$in': menus
        }
    }
    bucket = db.collection('menus').find(where)

    return jsonify({
        'message': 'ok',
        'code': 0,
        'data': bucket,
    })


def bind_user():
    payload = request.get_json()
    if not payload:
        return jsonify({
            'message': 'invalid params',
            'code': 104000,
        }), 400

    user_id = payload.get('user_id')
    roles = payload.get('roles')
    if not user_id or not roles:
        return jsonify({
            'message': 'invalid params',
            'code': 104000,
        }), 400

    user = User().find_by_id(user_id)
    if not user:
        return jsonify({
            'message': 'invalid user',
            'code': 104001,
        }), 400

    where = {
        '_id': {
            '$in': roles
        }
    }
    role_records = db.collection('roles').find(where)
    roles = map(lambda i: str(i['_id']), role_records)
    roles = list(roles)
    if not roles:
        return jsonify({
            'message': 'invalid roles',
            'code': 104003,
        }), 400

    data = {
        'user_id': user['_id'],
        'roles': roles,
        'add_by': login_user.get('username'),
        'created_at': time.time()
    }
    db.collection('user_roles').insert_one(data)

    return jsonify({
        'message': 'ok',
        'code': 0,
    })


def add_permission():
    """
    todo menus_id or api_id
    :param role_id:
    :param menus_id:
    :return:
    """

    payload = request.get_json()
    if not payload:
        return jsonify({
            'message': 'invalid params',
            'code': 104001,
        }), 400

    role_id = payload.get('role_id')
    menu_ids = payload.get('menu_ids')
    if not role_id or type(menu_ids) != list:
        return jsonify({
            'message': 'illegal params',
            'code': 104002
        }), 400

    role = db.collection('roles').find_one({'_id': ObjectId(role_id)})
    if not role:
        return jsonify({
            'message': 'invalid params',
            'code': 104001,
        }), 400

    where = {
        '_id': {
            '$in': menu_ids
        }
    }
    menus = db.collection('roles').find(where)
    menus = list(menus)
    if not menus:
        return jsonify({
            'message': 'invalid params',
            'code': 104001,
        }), 400

    mids = map(lambda i: i['_id'], menus)
    mids = list(mids)
    data = {
        'role_id': role_id,
        'mids': mids,
        'created_at': time.time()
    }
    db.collection('role_menus').insert_one(data)

    return jsonify({
        'message': 'ok',
        'data': 0,
    })


@jwt_required
def get_team_tree():
    teams = db.collection('teams').find({})
    teams = list(teams)
    tree = []
    user_collection = User()
    for team in teams:
        item = {
            'title': team['name'],
            'key': team['_id'],
            'team': team.get('name'),
        }
        relations = db.collection('team_members').find({'team_id': str(team['_id'])})
        relations = list(relations)
        if not relations:
            continue

        user_ids = map(lambda i: i['user_id'], relations)
        user_ids = list(user_ids)
        users = user_collection.find_by_ids(user_ids)
        children = []
        for user in users:
            children.append({
                'title': user.get('nickname'),
                'key': user.get('_id'),
                'team': None,
            })
        item['children'] = children
        tree.append(item)

    return jsonify({
        'message': 'ok',
        'code': 0,
        'data': tree,
    })


@jwt_required
def get_team_info(_id):
    record = Team().find_by_id(_id)
    if not record:
        return jsonify({
            'message': 'record not found',
            'code': 104040,
        }), 404

    where = {
        'name': record.get('name'),
        'type': 'team',
    }

    roles = db.collection('roles').find(where)
    roles = list(roles)
    permissions = []
    if roles:
        role_ids = map(lambda i: str(i['_id']), roles)
        where = {
            'role_id': {
                '$in': list(role_ids),
            }
        }
        records = db.collection('role_menus').find(where)
        records = list(records)
        ids = list(map(lambda i: i['m_id'], records))
        permissions = Menu().find_by_ids(ids)

    return jsonify({
        'message': 'ok',
        'code': 0,
        'data': {
            'team': record,
            'roles': list(roles),
            'permissions': permissions,
        }
    })
