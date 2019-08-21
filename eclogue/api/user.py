import re
import time

from bson import ObjectId
from flask import jsonify, request
from werkzeug.security import generate_password_hash
from eclogue.model import db
from eclogue.middleware import jwt_required, login_user
from eclogue.models.team import Team
from eclogue.models.role import Role
from eclogue.models.menu import Menu
from eclogue.models.user import User
from eclogue.models.team_user import TeamUser
from eclogue.utils import gen_password


@jwt_required
def search_user():
    user = request.args.get('user')
    if not user:
        where = {}
    else:
        where = {
            'username': {
                '$regex': user
            }
        }
    records = db.collection('users').find(where, limit=10)
    records = list(records)
    records = map(lambda item: {'username': item.get('username')}, records)
    records = list(records)
    print(records)

    return jsonify({
        'message': 'ok',
        'code': 0,
        'data': records,
    })


@jwt_required
def get_user_info(_id):
    user = User()
    record = user.find_by_id(_id)
    if not record:
        return jsonify({
            'message': 'record not found',
            'code': 104040
        }), 404
    relation = TeamUser().collection.find_one({'user_id': _id})
    team = Team().find_by_id(relation.get('team_id'))
    record['team'] = team
    record.pop('password')
    permissions, roles = user.get_permissions(_id)
    hosts = user.get_hosts(_id)
    return jsonify({
        'message': 'ok',
        'code': 0,
        'data': {
            'user': record,
            'roles': roles,
            'permissions': permissions,
            'hosts': hosts,
        }
    })


@jwt_required
def get_profile(_id):
    user = User()
    record = user.find_by_id(_id)
    if not record:
        return jsonify({
            'message': 'record not found',
            'code': 104040
        }), 404
    relation = TeamUser().collection.find_one({'user_id': _id})
    team = Team().find_by_id(relation.get('team_id'))
    record['team'] = team
    record.pop('password')
    record['team'] = team

    return jsonify({
        'message': 'ok',
        'code': 0,
        'data': record,
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
    tag = payload.get('tag')
    role_type = payload.get('type')
    parent = payload.get('parent', None)
    alias = payload.get('alias')
    menus = payload.get('menus')
    actions = payload.get('actions') or []
    if not tag or not name:
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

    # roles = ['admin', 'master', 'owner', 'member', 'guest']
    # if tag not in roles:
    #     return jsonify({
    #         'message': 'invalid param role',
    #         'code': 104000,
    #     }), 400

    data = {
        'name': name,
        'alias': alias,
        'type': role_type,
        'tag': tag,
        'actions': actions,
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
    print(result)
    role_id = result.inserted_id
    if menus and type(menus) == list:
        data = []
        # menus = Menu().find_by_ids(menus)
        menus = Menu().collection.find({})
        if menus:
            for item in menus:
                data.append({
                    'role_id': str(role_id),
                    'm_id': str(item['_id']),
                    'created_at': time.time(),
                    'add_by': login_user.get('username'),
                })

            db.collection('role_menus').insert_many(data)

    return jsonify({
        'message': 'ok',
        'code': 0,
    })


def get_permissions(user_id):
    user = db.collection('users').find_one({'_id': ObjectId(user_id)})
    if not user:
        return jsonify({
            'message': 'user not found',
            'code': 104040
        }), 404
    team = Team()
    relate_team = db.collection('team_users').find({'user_id': user_id})
    team_ids = list(map(lambda i: i['_id'], relate_team))
    role_ids = []
    permissions = []
    if team_ids:
        team_records = team.find_by_ids(team_ids)
        for record in team_records:
            team_role = db.collection('roles').find_one({
                'name': record.get('name'),
                'type': 'team',
            })
            if not team_role:
                continue
            role_ids.append(team_role.get('_id'))

    roles = db.collection('user_roles').find({'user_id': user_id})
    roles = list(roles)
    if roles:
        ids = map(lambda i: i['_id'], roles)
        role_ids.extend(list(ids))

    if role_ids:
        where = {
            'role_id': {
                '$in': role_ids
            }
        }
        permissions = db.collection('role_menus').find(where)
        permissions = list(permissions)

    return jsonify({
        'message': 'ok',
        'code': 0,
        'data': permissions
    })


@jwt_required
def bind_role(user_id):
    payload = request.get_json()
    if not payload:
        return jsonify({
            'message': 'invalid params',
            'code': 104030
        }), 400

    role_ids = payload.get('role_ids')
    if not role_ids or type(role_ids) != list:
        return jsonify({
            'message': 'invalid params',
            'code': 104031
        }), 400

    user = User()
    user_info = user.find_by_id(user_id)
    if not user_info:
        return jsonify({
            'message': 'record not found',
            'code': 104040
        }), 404

    roles = Role().find_by_ids(role_ids)
    if not roles:
        return jsonify({
            'message': 'invalid param',
            'code': 104031
        }), 400

    for role in roles:
        data = {
            'user_id': user_id,
            'role_id': str(role['_id']),
        }
        where = data.copy()
        data['created_at'] = time.time()
        data['add_by'] = login_user.get('username')
        db.collection('user_roles').update_one(where, {'$set': data}, upsert=True)

    return jsonify({
        'message': 'ok',
        'code': 0,
    })


@jwt_required
def bind_hosts(user_id):
    payload = request.get_json()
    if not payload:
        return jsonify({
            'message': 'invalid params',
            'code': 104030
        }), 400

    user_info = User().find_by_id(user_id)
    if not user_info:
        return jsonify({
            'message': 'invalid user',
            'code': 104043
        }), 400

    hosts = payload.get('hosts')
    if not hosts or len(hosts) > 2:
        return jsonify({
            'message': 'invalid params',
            'code': 104041
        }), 400

    if len(hosts) == 2:
        group_id, host_id = hosts
        check = db.collection('user_hosts').find_one({
            '$or': [
                {
                    'user_id': user_id,
                    'group_id': group_id,
                    'host_id': host_id,
                    'type': 'node'
                },
                {
                    'user_id': user_id,
                    'group_id': group_id,
                    'type': 'group'
                }
            ]
        })

        if check:
            return jsonify({
                'message': 'record exist',
                'code': 104005
            }), 400

        data = {
            'user_id': user_id,
            'host_id': host_id,
            'group_id': group_id,
            'type': 'node',
            'add_by': login_user.get('username'),
            'created_at': time.time(),
        }

        db.collection('user_hosts').insert_one(data)
    else:
        group_id = hosts[0]
        check = db.collection('user_hosts').find_one({
            'user_id': user_id,
            'group_id': group_id,
            'type': 'group'
        })
        if check:
            return jsonify({
                'message': 'record exist',
                'code': 104005
            }), 400

        data = {
            'user_id': user_id,
            'group_id': group_id,
            'type': 'group',
            'add_by': login_user.get('username'),
            'created_at': time.time(),
        }

        db.collection('user_hosts').insert_one(data)

    return jsonify({
        'message': 'ok',
        'code': 0,
    })


@jwt_required
def add_user():
    payload = request.get_json()
    if not payload:
        return jsonify({
            'message': 'invalid params',
            'code': 104000
        }), 400

    username = payload.get('username')
    nickname = payload.get('nickname')
    email = payload.get('email')
    phone = payload.get('phone')
    role_ids = payload.get('role_ids')
    team_id = payload.get('team_id')
    address = payload.get('address')
    if not username or not nickname or not email or not phone:
        return jsonify({
            'message': 'miss required params',
            'code': 104001,
        }), 400

    user = User()
    where = {
        '$or': [
            {'username': username},
            {'email': email},
        ]
    }
    existed = user.collection.find_one(where)
    if existed:
        return jsonify({
            'message': 'username or email existed',
            'code': 104030
        }), 400
    password = gen_password()
    encrypt_pwd = generate_password_hash(password)
    user_info = {
        'username': username,
        'nickname': nickname,
        'password': encrypt_pwd,
        'email': email,
        'phone': phone,
        'active': 0,
        'address': address,
        'created_at': time.time(),
        'add_by': login_user.get('username'),
    }
    result = user.collection.insert_one(user_info)
    user_id = str(result.inserted_id)
    role = Role()
    if role_ids:
        role_ids = role_ids if type(role_ids) == list else [role_ids]
        roles = role.find_by_ids(role_ids)
        if roles:
            for item in roles:
                data = {
                    'role_id': str(item['_id']),
                    'user_id': user_id,
                    'add_by': login_user.get('username'),
                    'created_at': time.time(),
                }
                db.collection('user_roles').insert_one(data)
    if team_id:
        data = {
            'team_id': team_id,
            'user_id': user_id,
            'is_owner': False,
            'add_by': login_user.get('username'),
            'created_at': time.time(),
        }
        Team().add_member(data)

    return jsonify({
        'message': 'ok',
        'code': 0,
    })


@jwt_required
def get_current_roles():
    username = login_user.get('username')
    is_admin = login_user.get('is_admin')
    role = Role()
    if is_admin:
        roles = role.collection.find({})
        return jsonify({
            'message': 'ok',
            'code': 0,
            'data': list(roles),
        })

    user = User()
    user_info = user.collection.find_one({'username': username})
    where = {
        'user_id': str(user_info['_id']),
    }
    roles = db.collection('user_roles').find(where)
    roles = list(roles)
    data = []
    if roles:
        role_ids = map(lambda i: i['role_id'], roles)
        data = role.find_by_ids(list(role_ids))

    return jsonify({
        'message': 'ok',
        'code': 0,
        'data': data,
    })


@jwt_required
def get_hosts():
    is_admin = login_user.get('is_admin')
    if is_admin:
        groups = db.collection('groups').find({})
    pass
