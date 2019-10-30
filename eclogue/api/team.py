import time

from bson import ObjectId
from flask import request, jsonify
from eclogue.model import db
from eclogue.middleware import jwt_required, login_user
from eclogue.models.team import Team
from eclogue.models.user import User
from eclogue.models.menu import Menu
from eclogue.models.role import Role
from eclogue.models.member import TeamMember
from eclogue.models.teamrole import TeamRole
from eclogue.lib.logger import logger



@jwt_required
def add_team():
    payload = request.get_json()
    if not payload:
        return jsonify({
            'message': 'invalid params',
            'code': 104000
        }), 400

    is_admin = login_user.get('is_admin')
    if not is_admin:
        return jsonify({
            'message': 'admin required',
            'code': 104039
        }), 403

    name = payload.get('name')
    description = payload.get('description')
    parent = payload.get('parent')
    role_ids = payload.get('role_ids')
    members = payload.get('members') or []
    master = payload.get('master') or [login_user.get('username')]
    record = Team.find_one({'name': name})
    if record:
        return jsonify({
            'message': 'name existed',
            'code': 104001
        }), 400

    if role_ids:
        role_record = Role.find_by_ids(role_ids)
        if not role_record:
            return jsonify({
                'message': 'role not found',
                'code': 104041
            }), 404

    data = {
        'name': name,
        'description': description,
        'master': master,
        'parent': parent,
        'add_by': login_user.get('username'),
        'created_at': time.time(),
    }

    result = Team.insert_one(data)
    team_id = str(result.inserted_id)
    data['_id'] = team_id
    logger.info('add team', extra={'record': data})
    if not role_ids:
        role = {
            'name': name,
            'type': 'team',
            'role': 'owner',
            'add_by': login_user.get('username'),
            'created_at': time.time(),
        }
        result = Role.insert_one(role)
        role['_id'] = result.inserted_id
        role['team_id'] = data['_id']
        logger.info('add role by team', extra={'record': role})
        role_ids = [role['_id']]

    for role_id in role_ids:
        team_role = {
            '$set': {
                'team_id': team_id,
                'role_id': role_id,
                'created_at': time.time()
            }
        }
        where = {
            'team_id': team_id,
            'role_id': role_id,
        }

        db.collection('team_roles').update_one(where, team_role, upsert=True)

    Team().add_member(team_id, members, owner_id=login_user.get('user_id'))

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
    is_admin = login_user.get('is_admin')
    username = login_user.get('username')
    where = {}
    if not is_admin:
        where = {
            'master': {
                '$in': [username]
            }
        }

    teams = db.collection('teams').find(where)
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
            tree.append(item)
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
    record = Team.find_by_id(_id)
    if not record:
        return jsonify({
            'message': 'record not found',
            'code': 104040,
        }), 404

    roles = Team().get_roles(_id)
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

    members = db.collection('team_members').find({'team_id': _id}, projection=['user_id'])
    record['members'] = list(map(lambda i: i['user_id'], members))

    return jsonify({
        'message': 'ok',
        'code': 0,
        'data': {
            'team': record,
            'roles': list(roles),
            'permissions': permissions,
        }
    })


@jwt_required
def update_team(_id):
    payload = request.get_json()
    if not payload:
        return jsonify({
            'message': 'invalid params',
            'code': 104000
        }), 400

    is_admin = login_user.get('is_admin')
    owner_id = login_user.get('user_id')
    record = Team.find_by_id(_id)
    if not record:
        return jsonify({
            'message': 'record not found',
            'code': 104040,
        }), 404

    if not is_admin and owner_id not in record.get('master'):
        return jsonify({
            'message': 'bad permission',
            'code': 104038
        }), 403

    name = payload.get('name')
    description = payload.get('description')
    parent = payload.get('parent')
    role_ids = payload.get('role') or []
    members = payload.get('members') or []
    master = payload.get('master') or [login_user.get('username')]
    if name and name != record.get('name'):
        check = Team.find_one({'name': name})
        if check:
            return jsonify({
                'message': 'name existed',
                'code': 104001
            }), 400

    update = {
        '$set': {
            'name': name,
            'description': description,
            'master': master,
            'parent': parent,
            'updated_at': time.time(),
        },
    }

    where = {
        '_id': record['_id']
    }

    team = Team()
    team.update_one(where, update=update)
    team.add_member(_id, members, owner_id=owner_id)
    for role_id in role_ids:
        team_role = {
            '$set': {
                'team_id': _id,
                'role_id': role_id,
                'created_at': time.time()
            }
        }
        where = {
            'team_id': _id,
            'role_id': role_id,
        }

        db.collection('team_roles').update_one(where, team_role, upsert=True)

    return jsonify({
        'message': 'ok',
        'code': 0,
    })


@jwt_required
def delete_team(_id):
    is_admin = login_user.get('is_admin')
    if not is_admin:
        return jsonify({
            'message': 'admin required',
            'code': 104033,
        }), 403

    record = Team.find_by_id(_id)
    if not record:
        return jsonify({
            'message': 'record not found',
            'code': 104040,
        }), 404

    update = {
        '$set': {
            'status': -1,
            'delete_at': time.time(),
        }
    }

    condition = {
        '_id': record['_id']
    }
    Team.update_one(condition, update=update)
    members = TeamMember.find({'team_id': _id})
    for member in members:
        where = {
            '_id': member['_id']
        }
        TeamMember.delete_one(where)
    team_roles = TeamRole.find(condition)
    for item in team_roles:
        where = {
            '_id': item['_id']
        }
        TeamRole.delete_one(where)

    return jsonify({
        'message': 'ok',
        'code': 0,
    })
