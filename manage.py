#!/usr/bin/env python
# coding=utf-8

import click
from eclogue import create_app
from migrate import Migration

app = create_app(schedule=False)


@app.cli.command()
@click.argument('action')
def test(action):
    migration = Migration()
    if action == 'generate':
        migration.generate()
    elif action == 'rollback':
        migration.rollback()
    elif action == 'run':
        migration.run()

    print('this isxxxxxxxxxxxxxxxx', action)
