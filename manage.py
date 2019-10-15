#!/usr/bin/env python
# coding=utf-8

import click
from eclogue import create_app
from migrate import Migration
from eclogue.tasks.system import register_schedule
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
def bootstrap():
    migration = Migration()
    migration.setup()
    register_schedule()
    print('this isxxxxxxxxxxxxxxxx---')


@click.command()
def server():
    debug = config.debug
    app.run(debug=debug)
    print('sssserver')


eclogue.add_command(migrate)
eclogue.add_command(bootstrap)
eclogue.add_command(server)

if __name__ == '__main__':
    eclogue()
