import json
import datetime
import logging.config

from flask import Flask
from bson import ObjectId
from flask_log_request_id import RequestID
from eclogue.config import config
from eclogue.middleware import Middleware
# sys.modules['ansible.utils.display'] = importlib.import_module('eclogue.ansible.display')
from eclogue.api import router
from eclogue.api.routes import routes


cfg = config.logging
logging.config.dictConfig(cfg)


class JSONEncoder(json.JSONEncoder):
    # extend json-encoder class
    def default(self, o):
        if isinstance(o, ObjectId):
            return str(o)
        if isinstance(o, datetime.datetime):
            return str(o)
        return json.JSONEncoder.default(self, o)


def create_app():
    # dictConfig(config.logging)
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


