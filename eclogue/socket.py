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
from eclogue.config import config
from eclogue.tasks.book import dispatch
from eclogue.models.perform import Perform
from eclogue.tasks.reporter import Reporter

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
    payload = payload or {}
    print(payload)
    book_id = payload.get('book_id')
    cmd = payload.get('cmd')
    if not book_id and not cmd:
        emit('playbook', {
            'code': 1404,
            'message': 'invalid params'
        })
    book = Book.find_by_id(book_id)
    if not book:
        emit('playbook', {
            'code': 1404,
            'message': 'book not found'
        })
    args = cmd.lstrip().split()
    allow_cmd = ['ls', 'll', 'cat', 'ansible-playbook', 'cd', 'pwd']
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
    try:
        if args[0] == 'ansible-playbook':
            task_id = dispatch(book_id, 'entry.yml', {'options': 'ansible-playbook -i hosts entry.yml -t test'})
            if not task_id:
                return emit('playbook', {
                    'message': ''
                })
            print('fuckkkkkkkkkkkkkk', task_id)
            return emit('book_task', {
                'code': 0,
                'type': 'task',
                'message': 'waiting for task launch...',
                'data': {
                    'state': 'pending',
                    'taskId': str(task_id),
                }
            })
        cwd = os.path.join(book_space, cwd)
        if args[0] == 'cd':
            if not args[1]:
                return emit({
                    'code': 1400,
                    'message': 'invalid args'
                })
            cwd = os.path.join(cwd, './' + args[1])
            cwd = os.path.realpath(cwd)
            if len(cwd) < len(book_space):
                cwd = book_space
            args = ['ls', '-a']
        process = subprocess.Popen(args,
                                   cwd=cwd,
                                   stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE,
                                   )
        stdout, stderr = process.communicate()
        emit('playbook', {
            'code': 0,
            'result': {
                'stdout': stdout.decode().replace(book_space, ''),
                'stderr': stdout.decode().replace(book_space, ''),
                'cwd': cwd.replace(book_space, '')
            }
        })
    except Exception as err:
        print(err)
        emit('playbook', {
            'code': 1500,
            'message': str(err).replace(book_space, '')
        })


@socketio.on('fetch_task', namespace='/socket')
def fetch_task(payload):
    print('fetch task:++++++', payload)
    payload = payload or {}
    book_id = payload.get('bookId')
    task_id = payload.get('taskId')
    record = Perform.find_by_id(task_id)
    if not record:
        return emit('book_task', {
            'code': 1404,
            'message': 'record not found'
        })

    start = int(payload.get('page', 0))
    end = -1
    reporter = Reporter(task_id=book_id)
    buffer = reporter.get_buffer(start=start, end=end)
    if not buffer and record.get('trace'):
        buffer = [record.get('trace')]
    # record = record.to_dict()
    print('xxx', record.to_json())
    emit('book_task', {
        'message': 'ok',
        'code': 0,
        'data': {
            'bookId': book_id,
            'taskId': task_id,
            'buffer': buffer,
            'page': start,
            'state': record.get('state'),
            'record': record.to_json()
        }
    })
def get_auth_key(username):
    return 'ece:ss:auth:' + username
