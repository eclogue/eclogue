import os
import json
import datetime
import logging.config

from flask import Flask, request, jsonify
from bson import ObjectId
from flask_log_request_id import RequestID
from eclogue.config import config
from eclogue.middleware import Middleware
# sys.modules['ansible.utils.display'] = importlib.import_module('eclogue.ansible.display')
from eclogue.api import router_v1
from eclogue.api.routes import routes
from eclogue.scheduler import scheduler
from eclogue.logger.formatter import MongoFormatter


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


def create_app(schedule=True):
    # dictConfig(config.logging)
    # root_path = os.path.join(config.home_path, 'public')
    root_path = config.home_path

    instance = Flask(__name__, root_path=root_path, static_folder='public', static_url_path='')
    instance.json_encoder = JSONEncoder
    instance.config.from_object(config)
    instance.config['LOG_REQUEST_ID_LOG_ALL_REQUESTS'] = True
    RequestID(app=instance)
    Middleware(instance)
    bp = router_v1(routes)
    instance.register_blueprint(bp)
    # instance.register_blueprint(static())
    if schedule:
        scheduler.start()
    # api.add_resource(Menus, '/menus')

    @instance.route('/', methods=['get'])
    def index():
        return instance.send_static_file('index.html')

    @instance.errorhandler(404)
    def not_found(error):
        print('4444400000444', error, request.full_path)
        return jsonify({
            'message': 'not found',
            'code': 404
        }), 404

    @instance.errorhandler(500)
    def server_error(error):

        return jsonify({
            'message': 'server error',
            'code': 500
        }), 500

    return instance


