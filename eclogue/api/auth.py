from eclogue.jwt import jws
from eclogue.model import db
from werkzeug.security import check_password_hash, generate_password_hash
from flask import request, jsonify


class Auth(object):
    @staticmethod
    def login():
        params = request.get_json()
        if not params:
            return jsonify({
                'message': 'illegal param',
                'code': 104000,
            }), 400

        username = params.get('username')
        password = params.get('password')
        if not username or not password:
            return jsonify({
                'message': 'username and password required',
                'code': 104001,
            }), 400

        # pwd = generate_password_hash(password)
        user = db.collection('users').find_one({'username': username})
        if user is None:
            return jsonify({
                'message': 'user not found',
                'code': 104002,
            }), 400

        password = str(password)
        verify = check_password_hash(user['password'], password)
        if not verify:
            return jsonify({
                'message': 'password incorrect',
                'code': 104003,
            }), 401

        user_info = {
            'user_id': str(user['_id']),
            'username': user['username'],
            'status': 1,
            'is_admin': user.get('is_admin', True),
        }
        token = jws.encode(user_info)
        # auth_user = user_info.copy()
        # auth_user.update({'token': token})
        user_info['token'] = token.decode('utf-8')

        return jsonify({
            'message': 'ok',
            'code': 0,
            'data': user_info,
        })

