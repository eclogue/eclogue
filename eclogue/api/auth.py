from ..jwt import jws
from ..model import db
from werkzeug.security import check_password_hash, generate_password_hash
from flask import request, jsonify


class Auth(object):
    @staticmethod
    def login():
        # parser = reqparse.RequestParser()
        # parser.add_argument('username', required=True, help='user name require')
        # parser.add_argument('password', required=True, help='password name require')
        # args = parser.parse_args()
        # username = args.username
        # password = args.password
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

        verify = check_password_hash(user['password'], password)
        if not verify:
            return jsonify({
                'message': 'password incorrect',
                'code': 104003,
            }), 401

        # @todo is_admin set False
        # @fixme
        token = jws.encode({
            'user_id': str(user['_id']),
            'username': user['username'],
            'status': 1,
            'is_admin': user.get('is_admin', True),
        })

        return jsonify({
            'message': 'ok',
            'data': {
                'username': user['username'],
                'token': token.decode('utf-8'),
                'user_id': str(user['_id']),
            }
        })

