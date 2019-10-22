import os

from flask import Blueprint
from eclogue.config import config

main = Blueprint('apiv1', __name__, url_prefix='/api/v1')


def router_v1(rules):
    bucket = []
    for route in rules:
        rule, func, methods = route
        endpoint = rule + '@' + func.__name__
        bucket.append(endpoint)

        main.add_url_rule(rule, endpoint=None, view_func=func, methods=methods)

    return main


# def static():
#     root_path = os.path.join(config.home_path)
#     print(root_path)
#     bp = Blueprint('static', __name__, url_prefix='', root_path=root_path, static_folder='public')
#
#     @bp.route('/')
#     def index():
#         return bp.send_static_file('index.html')
#
#     return bp
