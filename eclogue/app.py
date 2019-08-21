import json
import datetime
import importlib
import sys
from flask import Flask
from flask_log_request_id import RequestID
from eclogue.config import config
from eclogue.middleware import Middleware
from bson.objectid import ObjectId
sys.modules['ansible.utils.display'] = importlib.import_module('eclogue.ansible.display')


class JSONEncoder(json.JSONEncoder):
    # extend json-encoder class
    def default(self, o):
        if isinstance(o, ObjectId):
            return str(o)
        if isinstance(o, datetime.datetime):
            return str(o)
        return json.JSONEncoder.default(self, o)


def create_app():
    from eclogue.api import router
    from eclogue.api.routes import routes
    instance = Flask(__name__)
    instance.json_encoder = JSONEncoder
    instance.config.from_object(config)
    instance.config['LOG_REQUEST_ID_LOG_ALL_REQUESTS'] = True
    RequestID(app=instance)
    Middleware(instance)
    bp = router(routes)
    instance.register_blueprint(bp)
    # api.add_resource(Menus, '/menus')

    return instance
