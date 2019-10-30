import json
import time
from bson import ObjectId
from eclogue.model import db
from flask import request, jsonify
from eclogue.middleware import jwt_required, login_user
from eclogue.ansible.vault import Vault
from eclogue.config import config
from eclogue.lib.logger import logger
from eclogue.models.credential import Credential


@jwt_required
def credentials():
    query = request.args
    page = int(query.get('page', 1))
    size = int(query.get('pageSize', 20))
    where = {}
    name = query.get('name')
    if name:
        where['name'] = name
    offset = (page - 1) * size
    cursor = db.collection('credentials').find(where, skip=offset, limit=size)
    total = cursor.count()

    return jsonify({
        'message': 'ok',
        'code': 0,
        'data': {
            'list': list(cursor),
            'page': page,
            'pagesize': size,
            'total': total,
        }
    })


@jwt_required
def add_credential():
    payload = request.get_json()
    current_user = login_user
    allow_types = [
        'vault_pass',
        'private_key',
        'token',
    ]
    description = payload.get('description')
    status = payload.get('status', 1)
    name = payload.get('name')
    if not name or name in ['all', 'global']:
        return jsonify({
            'message': 'invalid name',
            'code': 134000,
        }), 400

    existed = db.collection('credentials').find_one({'name': name})
    if existed:
        return jsonify({
            'message': 'name already existed',
            'code': 134002
        }), 400

    ctype = payload.get('type')
    if not ctype or ctype not in allow_types:
        return jsonify({
            'message': 'invalid type',
            'code': 134001
        }), 400

    body = payload.get('body')
    if not body or not body.get(ctype):
        return jsonify({
            'message': 'credential body required',
            'code': 134002
        }), 400

    body[ctype] = encrypt_credential(body[ctype])
    scope = payload.get('scope', 'global')
    users = payload.get('users', [])
    user_list = db.collection('users').find({'username': {'$in': users}})
    user_list = list(user_list)
    usernames = []
    for item in user_list:
        usernames.append(item.get('username'))

    data = {
        'name': name,
        'description': description,
        'users': usernames,
        'body': body,
        'scope': scope,
        'type': ctype,
        'status': status,
        'add_by': current_user.get('username'),
        'created_at': time.time()
    }

    Credential.insert_one(data)

    return jsonify({
        'message': 'ok',
        'code': 0,
    })


@jwt_required
def update_credential(_id):
    payload = request.get_json()
    current_user = login_user
    allow_types = [
        'vault_pass',
        'private_key',
        'token',
    ]
    record = db.collection('credentials').find_one({'_id': ObjectId(_id)})
    if not record:
        return jsonify({
            'message': 'record not found',
            'code': 134040,
        }), 404
    data = {}
    description = payload.get('description')
    name = payload.get('name')
    status = payload.get('status')
    if name and record.get('name') != name:
        data['name'] = name
        existed = db.collection('credentials').find_one({'name': name})
        if existed:
            return jsonify({
                'message': 'name already existed',
                'code': 134002
            }), 400

    if status is not None:
        data['status'] = int(status)

    if description:
        data['description'] = description

    credential_type = payload.get('type')
    if credential_type:
        data['type'] = credential_type
        if credential_type not in allow_types:
            return jsonify({
                'message': 'invalid type',
                'code': 134001
            }), 400

    body = payload.get('body')
    if not body or not body.get(credential_type):
        return jsonify({
            'message': 'illegal credential params',
            'code': 134002
        }), 400

    is_encrypt = Vault.is_encrypted(body[credential_type])
    if not is_encrypt:
        body[credential_type] = encrypt_credential(body[credential_type])
        data['body'] = body

    scope = payload.get('scope', 'global')
    data['scope'] = scope
    users = payload.get('users', [login_user.get('username')])
    user_list = db.collection('users').find({'username': {'$in': users}})
    user_list = list(user_list)
    data['maintainer'] = []
    for item in user_list:
        data['maintainer'].append(item.get('username'))

    Credential.update_one({'_id': record['_id']}, {'$set': data})

    return jsonify({
        'message': 'ok',
        'code': 0,
    })


def encrypt_credential(text):
    secret = config.vault.get('secret')
    options = {
        'vault_pass': secret
    }
    vault = Vault(options=options)
    return vault.encrypt_string(text)
