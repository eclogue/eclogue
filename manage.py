#!/usr/bin/env python
# coding=utf-8

import click
import unittest
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
def bootstrap():
    migration = Migration()
    migration.setup()


@click.command()
def start():
    debug = config.debug
    register_schedule()
    app.run(debug=debug)
    print('sssserver')


@click.command()
def test():
    unittest.main('tests')


eclogue.add_command(migrate)
eclogue.add_command(bootstrap)
eclogue.add_command(start)
eclogue.add_command(test)

if __name__ == '__main__':
    eclogue()
