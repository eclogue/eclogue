import functools
from flask_socketio import emit, disconnect
from eclogue import socketio
from flask import request, _request_ctx_stack
from werkzeug.local import LocalProxy
from eclogue.jwt import jws
from authlib.specs.rfc7519 import JWTError
from eclogue.models.book import Book
import subprocess
import paramiko
from eclogue.lib.workspace import Workspace

import os

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
                _request_ctx_stack.top.current_user = claims
                return f(*args, **kwargs)
        except JWTError:
            return disconnect()

    return wrapped


@socketio.on('health', namespace='/socket')
@authenticated
def ping(msg):
    emit('test', {'message': 'ok', 'code': 0, 'msg': msg})


@socketio.on('playbook', namespace='/socket')
def playbook(payload):
    try:
        print('???---', payload)
        payload = payload or {}
        book_id = payload.get('book_id')
        cmd = payload.get('cmd')
        if not book_id and not cmd:
            pass
            # emit('playbook', {
            #     'code': 1404,
            #     'message': 'invalid params'
            # })
        book = Book.find_by_id(book_id)
        if not book:
            pass
            # emit('playbook', {
            #     'code': 1404,
            #     'message': 'book not found'
            # })
        args = cmd.lstrip().split()
        allow_cmd = ['ls', 'cat', 'ansible-playbook', 'cd', 'pwd']
        if args[0] not in allow_cmd:
            return emit('playbook', {
                'code': 1403,
                'message': 'invalid command'
            })

        # with build_book_from_db(book.get('name')) as cwd:
        cwd = payload.get('cwd') or ''
        cwd = cwd.strip('/')
        wk = Workspace()
        book_space = wk.load_book_from_db(book['name'])
        # base_dir = os.path.dirname(book_space)
        cwd = os.path.join(book_space, cwd)
        if args[0] == 'cd':
            if not args[1]:
                return emit({
                    'code': 1400,
                    'message': 'invalid args'
                })
            cwd = os.path.join(cwd, args[1])
            args = ['ls', '-a']
        print('cwd', book_space, cwd, args)
        process = subprocess.Popen(args,
                                   cwd=cwd,
                                   stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE,
                                   )
        stdout, stderr = process.communicate()
        print('-----??????>>>>>>>>', cwd)
        emit('playbook', {
            'code': 0,
            'result': {
                'stdout': stdout.decode().replace(book_space, ''),
                'stderr': stdout.decode().replace(book_space, ''),
                'cwd': cwd.replace(book_space, '')
            }
        })
    except Exception as err:
        emit('playbook', {
            'code': 1500,
            'message': str(err)
        })


@socketio.on('ssh', namespace='/socket')
def ssh(payload):
    username = 'tommy'
    hostname = 'localhost'
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    # p_key = paramiko.RSAKey.from_private_key_file("./id_rsa")
    # client.set_missing_host_key_policy(paramiko.WarningPolicy())
    try:
        client.connect(hostname=hostname, username=username, port=22)
    except Exception as err:
        return emit('ssh', {
            'code': 4401,
            'message': str(err)
        })
    # chan.send('ls -a')
    # chan.close()


def get_auth_key(username):
    return 'ece:ss:auth:' + username
