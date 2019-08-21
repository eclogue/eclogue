#!/usr/bin/env python
# coding=utf-8

from flask import Flask, current_app
from flask_script import Server, Shell, Manager, Command, prompt_bool
from eclogue.app import create_app, app
from eclogue.api import main
from eclogue.config import config
from eclogue.model import db


manager = Manager(app)


def _make_context():
    return dict(db=db)



@manager.command
def runserver():
    instance = create_app(app)
    instance.register_blueprint(main)


# manager.add_command("runserver", Server('0.0.0.0', port=7000))
manager.add_command("shell", Shell(make_context=_make_context))




@manager.command
def dropall():
    "Drops all database tables"
    if prompt_bool("Are you sure ? You will lose all your data !"):
        db.drop_all()


if __name__ == "__main__":
    manager.run()
