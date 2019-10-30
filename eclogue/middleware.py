from flask import request, jsonify, _request_ctx_stack
from werkzeug.local import LocalProxy
from functools import wraps
from eclogue.jwt import jws, get_claims
from authlib.specs.rfc7519 import JWTError

# from eclogue.models.user import User
# from eclogue.routes import routes


login_user = LocalProxy(lambda: getattr(_request_ctx_stack.top, 'login_user', None))


class Middleware(object):

    def __init__(self, app=None):
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        if not hasattr(app, 'extensions'):
            app.extensions = {}

        app.extensions['jwt'] = self


def _jwt_required():
    try:
        authorization = request.headers.get('Authorization', None)
        if not authorization:
            return 0

        parts = authorization.split()
        if len(parts) < 2 or parts[0] != 'Bearer':
            return 0

        token = parts[1]
        claims = jws.verify(token)
        if claims is False:
            return 0

        _request_ctx_stack.top.login_user = claims
        return True
    except JWTError:
        return False


def jwt_required(fn):
    """
    @todo user permission menus
    :param fn:
    :return:
    """

    @wraps(fn)
    def wrapper(*args, **kwargs):
        claims = get_claims()
        if claims is 0:
            return jsonify({
                'message': 'auth failed',
                'code': 401401,
            }), 401

        if claims == -1:
            return jsonify({
                'message': 'permission deny',
                'code': 4031,
            }), 403

        _request_ctx_stack.top.login_user = claims

        return fn(*args, **kwargs)

    return wrapper


def return_json(status=200, code=0, message='', data=None):
    return jsonify({
        'code': code,
        'message': message,
        'data': data

    }), status
