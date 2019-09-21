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
        if claims.get('is_admin'):
            return True
        username = claims.get('username')
        user_id = claims.get('user_id')
        # user = User()
        # if not user_id:
        #     user_info = user.collection.find_one({'username': username})
        #     user_id = str(user_info['_id'])

        # user_team = db.collection('team_members').find_one({'user_id': user_id})
        # team = Team().find_by_id(str(user_team['team_id']))
        # where = {
        #     'name': team.get('name'),
        #     'type': 'team',
        # }
        # team_role = db.collection('roles').find_one(where)
        # relations = db.collection('user_roles').find({
        #     'user_id': user_id,
        # })
        # role_ids = map(lambda i: i['role_id'], relations)
        # role_ids = set(role_ids)
        # role_ids.add(team_role['_id'])
        # where = {
        #     'role_id': {
        #         '$in': list(role_ids)
        #     }
        # }
        # menus = db.collection('menus').find(where)
        # menus = list(menus)
        # menus, roles = user.get_permissions(user_id)
        # if not menus:
        #     return False
        #
        # blocks = filter(lambda i: int(i['bpid']) < 1, menus)
        # url_rule = request.url_rule
        # method = request.method
        # is_allow = -1
        # for block in blocks:
        #     menu_name = block.get('name')
        #     actions = block.get('actions', [])
        #     if menu_name not in routes:
        #         continue
        #     rules = routes.get(menu_name)
        #     for route in rules:
        #         rule, func, methods = route
        #         if url_rule == rule and method in actions:
        #             is_allow = 1
        #             break
        #
        #     if is_allow != -1:
        #         break
        #
        # return is_allow
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
