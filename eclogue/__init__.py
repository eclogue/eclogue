import json
import datetime

from logging.config import dictConfig
from bson import ObjectId
from flask import Flask, request, jsonify
from werkzeug.exceptions import HTTPException
from flask_log_request_id import RequestID
from eclogue.config import config
from eclogue.middleware import Middleware
from eclogue.api import router_v1
from eclogue.api.routes import routes
from eclogue.scheduler import scheduler
from eclogue.lib.logger import get_logger
from eclogue.model import Model


class JSONEncoder(json.JSONEncoder):
    # extend json-encoder class
    def default(self, o):
        if isinstance(o, Model):
            print('mmmmmmmmmmmmmm', type(o))
            return o.__dict__()
        if isinstance(o, ObjectId):
            return str(o)
        if isinstance(o, datetime.datetime):
            return str(o)
        if isinstance(o, bytes):
            return o.decode('utf8')

        return json.JSONEncoder.default(self, o)


def create_app(schedule=True):
    dictConfig(config.logging)
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
        return jsonify({
            'message': 'not found',
            'code': 404,
            'error': str(error)
        }), 404

    @instance.errorhandler(500)
    def server_error(error):

        return jsonify({
            'message': 'server error',
            'code': 500,
            'error': str(error)
        }), 500

    @instance.errorhandler(405)
    def metho_not_allow(error):
        return jsonify({
            'message': 'method not allow',
            'code': 405,
            'error': str(error)
        }), 405

    @instance.errorhandler(HTTPException)
    def handle_exception(e):
        """Return JSON instead of HTML for HTTP errors."""
        # start with the correct headers and status code from the error
        # replace the body with JSON
        log_info = {
            "code": e.code,
            "title": e.name,
            "description": e.description,
        }
        get_logger().error('api server error %s' % e.description, extra=log_info)

        return jsonify({
            'code': 500,
            'message': 'api server error'
        })

    return instance


__version__ = '0.0.1'
