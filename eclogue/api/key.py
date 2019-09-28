import time
import hashlib

from flask import request, jsonify
from sshpubkeys import SSHKey

from eclogue.middleware import jwt_required, login_user
from eclogue.model import db
from eclogue.config import config
from eclogue.ansible.vault import Vault


@jwt_required
def add_key():
    user = login_user
    payload = request.get_json()
    if not payload:
        return jsonify({
            'message': 'illegal params',
            'code': 104000,
        }), 400

    public_key = payload.get('public_key')
    if not public_key:
        return jsonify({
            'message': 'invalid public key',
            'code': 104000
        }), 400

    ssh = SSHKey(public_key)
    try:
        ssh.parse()
    except Exception as err:
        return jsonify({
            'message': 'invalid ssh key: {}'.format(str(err)),
            'code': 104001,
        }), 400

    fingerprint = ssh.hash_md5()
    existed = db.collection('public_keys').find_one({'fingerprint': fingerprint})
    if existed:
        return jsonify({
            'message': 'ssh public key existed',
            'code': 104003
        }), 400

    options = {
        'vault_pass':  config.vault.get('secret')
    }
    encode = Vault(options).encrypt_string(public_key)
    data = {
        'fingerprint': fingerprint,
        'user_id': user.get('user_id'),
        'content': encode,
        'created_at': time.time()
    }

    db.collection('public_keys').insert_one(data)

    return jsonify({
        'message': 'ok',
        'code': 0,
    })


@jwt_required
def get_keys():
    query = request.args
    page = int(query.get('page', 1))
    limit = int(query.get('pageSize', 50))
    skip = (page - 1) * limit
    where = {
        'user_id': login_user.get('user_id')
    }
    projection = ['fingerprint', 'created_at']
    records = db.collection('public_keys').find(where, limit=limit, skip=skip, projection=projection)
    total = records.count()

    return jsonify({
        'message': 'ok',
        'code': 0,
        'data': {
            'list': list(records),
            'page': page,
            'pageSize': limit,
            'total': total,

        }
    })


def get_secret(password):
    salt = config.vault.get('secret')
    length = len(password)
    prefix = salt[:length]
    postfix = salt[length:]
    secret = prefix + password + postfix

    return hashlib.sha256(secret).hexdigest()
