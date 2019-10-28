#!/usr/bin/env python
# coding=utf-8

import click
from eclogue import create_app
from migrate import Migration
from eclogue.tasks.system import register_schedule, scheduler
from eclogue.config import config

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
    register_schedule()
    app.run(debug=debug, host='0.0.0.0', port=5000)
    print('sssserver')


eclogue.add_command(migrate)
eclogue.add_command(bootstrap)
eclogue.add_command(start)

if __name__ == '__main__':
    eclogue()
