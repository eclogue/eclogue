import time

from authlib.specs.rfc7519 import jwt, JWTError
from eclogue.config import config
from flask import request
from eclogue.models.user import User
from eclogue.model import db
from eclogue.routes import routes


class JWTAuth(object):

    def __init__(self, conf=None):
        self.config = conf or config.jwt
        self.header = self.config['header'] or {
            'alg': 'HS256'
        }

    def encode(self, payload):
        data = {
            'iss': self.config['iss'],
            'aud': self.config['aud'],
            'jwi': 'eclogue',
            # 'exp': int(time.time()) + 10000,
            'exp': int(time.time()) + int(self.config.get('exp'))

        }
        if payload:
            data.update(payload)

        key = self.config['key']
        return jwt.encode(self.header, data, key)

    def decode(self, token):
        key = self.config['key']
        options = {
            "iss": {
                "essential": True,
                "values": [self.config['iss']]
            },
            "aud": {
                "essential": True,
                "value": self.config['aud']
            },
            # "jti": {
            #     "essential": True,
            #     "value": self.config['jti']
            # }
        }
        return jwt.decode(token, key, None, options)

    def verify(self, token):
        try:
            claims = self.decode(token)
            claims.validate()

            return claims
        except JWTError:
            return False


def get_claims():
    try:
        authorization = request.headers.get('Authorization', None)
        if not authorization:
            return 0

        parts = authorization.split()
        if len(parts) < 2 or parts[0] != 'Bearer':
            return 0

        token = parts[1]
        claims = jws.verify(token)
        url_rule = str(request.url_rule)
        if config.api.get('force_check_binding'):
            found = _force_check_menu_apis(url_rule)
            if not found:
                return -1

        if claims is False:
            return 0

        if claims.get('is_admin'):
            return claims

        method = request.method.lower()
        if url_rule in routes.get('Default'):
            return claims

        username = claims.get('username')
        user_id = claims.get('user_id')
        user = User()
        if not user_id:
            user_info = User.find_one({'username': username})
            user_id = str(user_info['_id'])

        menus, roles = user.get_permissions(user_id)
        if not menus:
            return -1

        is_allow = -1
        for menu in menus:
            apis = menu.get('apis')
            actions = menu.get('actions')
            if not apis:
                continue

            if url_rule in apis and method in actions:
                is_allow = 1
                break

        return claims if is_allow == 1 else is_allow
    except JWTError:
        return False


def _force_check_menu_apis(url):
    menus = db.collection('menus').find({})
    found = False
    for menu in menus:
        apis = menu.get('apis')
        if not apis:
            continue

        if url in apis:
            found = True
            break

    return found


jws = JWTAuth()
