import re
import time

from bson import ObjectId
from flask import jsonify, request
from flask_log_request_id import current_request_id
from werkzeug.security import check_password_hash, generate_password_hash
from eclogue.model import db
from eclogue.middleware import jwt_required, login_user
from eclogue.models.team import Team
from eclogue.models.role import Role
from eclogue.models.menu import Menu
from eclogue.models.user import User
from eclogue.models.team_user import TeamUser
from eclogue.models.userrole import UserRole
from eclogue.models.member import TeamMember
from eclogue.utils import gen_password
from eclogue.config import config
from eclogue.utils import md5
from eclogue.lib.logger import logger
from eclogue.notification.smtp import SMTP


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
    setting = db.collection('setting').find_one({})
    options = {
        'slack': True,
        'sms': True,
        'wechat': True,
        'smtp': True,
    }
    if setting:
        slack = setting.get('slack') or {}
        sms = setting.get('nexmo') or {}
        wechat = setting.get('wechat') or {}
        smtp = setting.get('smtp') or {}
        options['slack'] = bool(slack.get('enable'))
        options['sms'] = bool(sms.get('enable'))
        options['wechat'] = bool(wechat.get('enable'))
        options['smtp'] = bool(smtp.get('enable'))

    record['setting'] = options

    return jsonify({
        'message': 'ok',
        'code': 0,
        'data': record,
    })


@jwt_required
def save_profile(_id):
    payload = request.get_json()
    user = User()
    record = user.find_by_id(_id)
    if not record:
        return jsonify({
            'message': 'record not found',
            'code': 104040
        }), 404

    nickname = payload.get('nickname')
    phone = payload.get('phone')
    email = payload.get('email')
    address = payload.get('address')
    wechat = payload.get('wechat')
    update = {}
    if nickname:
        update['nickname'] = nickname

    if phone:
        update['phone'] = phone

    if email:
        update['email'] = email

    if address:
        update['address'] = address

    if wechat:
        update['wechat'] = wechat

    if update:
        user.collection.update_one({'_id': record['_id']}, update={'$set': update})

    return jsonify({
        'message': 'ok',
        'code': 0,
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

    current_user = login_user.get('username')
    is_admin = login_user.get('is_admin')
    username = payload.get('username')
    nickname = payload.get('nickname')
    email = payload.get('email')
    phone = payload.get('phone')
    role_ids = payload.get('role_ids')
    team_id = payload.get('team_id')
    address = payload.get('address')
    password = payload.get('password')
    if not username or not email:
        return jsonify({
            'message': 'miss required params',
            'code': 104001,
        }), 400

    if not is_admin:
        if team_id:
            team = Team.find_by_id(team_id)
            if not team or current_user not in team.get('master'):
                return jsonify({
                    'message': 'permission deny',
                    'code': 104031
                }), 403
        else:
            return jsonify({
                'message': 'permission deny',
                'code': 104032,
            }), 403

    where = {
        '$or': [
            {'username': username},
            {'email': email},
        ]
    }
    existed = User.find_one(where)
    if existed:
        return jsonify({
            'message': 'username or email existed',
            'code': 104030
        }), 400

    password = password or gen_password()
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
    result = User.insert_one(user_info)
    user_id = str(result.inserted_id)
    if role_ids:
        role_ids = role_ids if type(role_ids) == list else [role_ids]
        roles = Role.find_by_ids(role_ids)
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
        Team().add_member(team_id=team_id, members=[user_id], owner_id=login_user.get('user_id'))

    notify = SMTP()
    text = '''
    <p>Dear user:</p>
    <p>Your eclogue account is active~!</p>
    <p>username: {}</p>
    <p>password: {} </p>
    '''
    text = text.format(username, password)
    notify.send(text, to=email, subject='', subtype='html')

    return jsonify({
        'message': 'ok',
        'code': 0,
        'data': password
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
def send_verify_mail():
    user_id = login_user.get('user_id')
    record = User().find_by_id(user_id)
    if not record:
        return jsonify({
            'message': 'invalid user',
            'code': 104033
        }), 403

    email = record.get('email')
    token = md5(str(current_request_id))
    url = config.dommain + '/users/email/verify?token=' + token
    message = '[Eclogue]Please click url to verify your email:<a href="{}">{}</a>'.format(url, url)
    smtp = SMTP()
    smtp.send(message, email, subtype='html')
    data = {
        'user_id': user_id,
        'token': token,
        'created_at': time.time(),
        'email': email,
        'content': message,
    }

    db.collection('mail_verify').insert_one(data)

    return jsonify({
        'message': 'ok',
        'code': 0
    })


def verify_mail():
    query = request.args
    token = query.get('token')
    if not query.get('token'):
        return jsonify({
            'message': 'invalid token',
            'code': 104030
        }), 403

    record = db.collection('mail_verify').find_one({'token': token})
    if not record:
        return jsonify({
            'message': 'record not found',
            'code': 104040
        }), 404

    update = {
        '$set': {
            'email_status': 1
        }
    }

    User().collection.update_one({'_id': ObjectId(record.get('user_id'))}, update=update)

    return jsonify({
        'message': 'ok',
        'code': 0,
    })


@jwt_required
def reset_pwd():
    payload = request.get_json()
    if not payload:
        return jsonify({
            'message': 'illegal params',
            'code': 104000,
        }), 400

    old_password = payload.get('old_pwd')
    new_password = payload.get('new_pwd')
    confirm = payload.get('confirm')
    if not old_password or not new_password or not confirm:
        return jsonify({
            'message': 'miss required params',
            'code': 104001
        }), 400

    if new_password != confirm:
        return jsonify({
            'message': 'inconsistent confirm password',
            'code': 104002
        }), 400

    user = User().find_by_id(login_user.get('user_id'))
    checked = check_password_hash(user.get('password'), old_password)
    if not checked:
        return jsonify({
            'message': 'password incorrect',
            'code': 104003,
        }), 400

    pwd = generate_password_hash(new_password)
    update = {
        '$set': {
            'password': pwd,
        }
    }
    User().collection.update_one({'_id': user['_id']}, update=update)

    return jsonify({
        'message': 'ok',
        'code': 0,
    })


@jwt_required
def save_alert():
    payload = request.get_json()
    if not payload:
        return jsonify({
            'message': 'invalid params',
            'code': 104000
        }), 400

    alerts = payload.get('alerts')
    alert_type = payload.get('type')
    if not alerts or type(alerts) != list:
        return jsonify({
            'message': 'invalid param alerts',
            'code': 104001
        }), 400

    where = {
        '_id': ObjectId(login_user.get('user_id'))
    }
    field = 'alerts.' + alert_type
    update = {
        '$set': {
            field: alerts
        }
    }

    user = User()
    record = user.collection.find_one(where)
    user.collection.update_one(where, update=update)
    logger.info('add alerts', extra={'change': update, 'record': record})

    return jsonify({
        'message': 'ok',
        'code': 0
    })


@jwt_required
def update_user(_id):
    payload = request.get_json()
    record = User.find_by_id(_id)
    if not record:
        return jsonify({
            'message': 'record not found',
            'code': 104040
        }), 404

    if not payload:
        return jsonify({
            'message': 'illegal params',
            'code': 104000
        }), 400

    current_user_id = login_user.get('user_id')
    is_admin = login_user.get('is_admin')
    username = payload.get('username')
    nickname = payload.get('nickname')
    email = payload.get('email')
    phone = payload.get('phone')
    role_ids = payload.get('role')
    team_id = payload.get('team_id')
    address = payload.get('address')
    # current_team_id = payload.get('currentTeamId')
    # current_role_ids = payload.get('currentRoleIds')
    if not is_admin:
        return jsonify({
            'message': 'bad permission',
            'code': 104130
        }), 403

    update = {}
    if username and record['username'] != username:
        update['username'] = username
        check = User.find_one({'username': username})
        if check:
            return jsonify({
                'message': 'username existed',
                'code': 104001
            }), 400

    if email and record.get('email') != email:
        update['email'] = email
        check = User.find_one({'email': email})
        if check:
            return jsonify({
                'message': 'email existed',
                'code': 104001
            }), 400

    if phone and record.get('phone') != phone:
        update['phone'] = phone
        check = User.find_one({'phone': phone})
        if check:
            return jsonify({
                'message': 'phone existed',
                'code': 104001
            }), 400

    if nickname:
        update['nickname'] = nickname

    if address:
        update['address'] = address

    if team_id:
        change = {
            '$set': {
                'team_id': team_id,
                'user_id': _id,
                'updated_at': time.time(),
            }
        }
        condition = {
            'user_id': _id,
        }
        db.collection('team_members').update_one(condition, update=change, upsert=True)

    if role_ids:
        result = User().bind_roles(_id, role_ids, add_by=login_user.get('username'))

    User.update_one({'_id': record['_id']}, {'$set': update})

    return jsonify({
        'message': 'ok',
        'code': 0,
    })


@jwt_required
def delete_user(_id):
    is_admin = login_user.get('is_admin')
    if not is_admin:
        return jsonify({
            'message': 'admin required',
            'code': 104033,
        }), 403

    record = User.find_by_id(_id)
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
    User.update_one(condition, update=update)

    TeamMember.delete_one({'user_id': _id})
    user_roles = UserRole.find(condition)
    for item in user_roles:
        where = {
            '_id': item['_id']
        }
        UserRole.delete_one(where)

    return jsonify({
        'message': 'ok',
        'code': 0,
    })

