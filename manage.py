#!/usr/bin/env python
# coding=utf-8
from gevent import monkey
monkey.patch_all()

import click
import os
from eclogue import create_app, socketio
from migrate import Migration
from eclogue.tasks.system import register_schedule
from eclogue.config import config
from gevent.pywsgi import WSGIServer
from circus import get_arbiter

app = create_app(schedule=False)


@click.group()
def eclogue():
    pass


@click.command()
@click.argument('action')
def migrate(action):
    migration = Migration()
    if action == 'generate':
        migration.generate()
    elif action == 'rollback':
        migration.rollback()
    elif action == 'setup':
        migration.setup()


@click.command()
@click.option('--username', default='', prompt='Please input admin username', help='Admin username')
@click.option('--password', default='', prompt='Please input admin password', help='Admin password')
def bootstrap(username=None, password=None):
    migration = Migration()
    migration.setup()
    if username and password:
        migration.add_admin(username, password)


@click.command()
def start():
    debug = config.debug
    # register_schedule()
    app.debug = debug
    socketio.run(app=app, host='0.0.0.0', port=5000)


@click.command()
def server():
    http_server = WSGIServer(('0.0.0.0', 5000), app)
    http_server.serve_forever()


@click.command()
def worker():
    cwd = os.path.abspath('.')
    program = {
        'name': 'worker',
        'use': 'circus.plugins.redis_observer.RedisObserver',
        'loop_rate': 5,
        'cmd': '.venv/bin/python worker.py',
        'working_dir': cwd,
        'sample_rate': 2.0,
        'application_name': 'eclogue-worker',
    }
    arbiter = get_arbiter(watchers=[program])
    arbiter.start()


eclogue.add_command(migrate)
eclogue.add_command(bootstrap)
eclogue.add_command(start)
eclogue.add_command(worker)
eclogue.add_command(server)

if __name__ == '__main__':
    eclogue()
