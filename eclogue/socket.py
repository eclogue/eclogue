import functools
from flask_socketio import emit, disconnect
from flask import request
from eclogue import socketio
from flask import request, _request_ctx_stack
from werkzeug.local import LocalProxy
from eclogue.jwt import jws, get_claims
from eclogue.redis import redis_client
from authlib.specs.rfc7519 import JWTError


current_user = LocalProxy(lambda: getattr(_request_ctx_stack.top, 'current_user', {}))


def authenticated(f):
    @functools.wraps(f)
    def wrapped(*args, **kwargs):
        try:
            authorization = request.headers.get('Authorization', None)
            sid = request.headers.get('t')
            if not authorization:
                return disconnect()
            parts = authorization.split()
            if len(parts) < 2 or parts[0] != 'Bearer':
                return disconnect()
            token = parts[1]
            claims = jws.verify(token)
            if not claims:
                return disconnect()
            else:
                claims['sid'] = sid
                print(claims)
                _request_ctx_stack.top.current_user = claims
                return f(*args, **kwargs)
        except JWTError:
            return disconnect()
    return wrapped


@socketio.on('test', namespace='/chat')
@authenticated
def test(message):
    # print('======', message, current_user)
    emit('test', {'msg': ' has entered the room.'})


@socketio.on('connect')
def connect(*args, **kwargs):
    print(*args, **kwargs)


def get_auth_key(username):
    return 'ece:ss:auth:' + username
