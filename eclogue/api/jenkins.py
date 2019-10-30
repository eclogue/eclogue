import time
from eclogue.middleware import jwt_required, login_user
from flask import jsonify, request
from eclogue.config import config
from eclogue.ansible.vault import Vault


@jwt_required
def add_jenkins():
    user = login_user
    body = request.get_json()
    if not body:
        return jsonify({
            'code': 114001,
            'message': 'invalid params',
        })
    base_url = body.get('base_url')
    username = body.get('username')
    password = body.get('password')
    artifacts = body.get('artifacts')
    if not base_url or not username or not password:
        return jsonify({
            'message': 'miss required params',
            'code': 114002
        }), 400

    vault_pass = config.jenkins.get('vault')
    options = {
        'vault_pss': vault_pass
    }
    encrypt = Vault(options).encrypt_string(password)
    record = {
        'add_by': user.username,
        'setting': {
            'username': username,
            'baseurl': base_url,
            'password': encrypt,
            'artifacts': artifacts,
        },
        'created_at': int(time.time())
    }
