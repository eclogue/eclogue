from flask import Blueprint
# from eclogue.routes import routes
# from eclogue.model import db

main = Blueprint('profile', __name__)


def router(rules):
    bucket = []
    for route in rules:
        rule, func, methods = route
        endpoint = rule + '@' + func.__name__
        bucket.append(endpoint)

        main.add_url_rule(rule, endpoint=None, view_func=func, methods=methods)
    return main


# def dispatch(app):
#     for item in routes:
#         name = item.get('name')
#         rules = item.get('api')
#         bp = Blueprint(name, __name__)
#         for route in rules:
#             rule, func, methods = route
#             endpoint = rule + '@' + func.__name__
#             bp.add_url_rule(rule, endpoint=endpoint, view_func=func, methods=methods)
#         app.register_blueprint(bp)
#
#     return app
#
#
# def init():
#     for item in routes:
#         name = item.get('name')
#         rules = item.get('api')
#         bp = Blueprint(name, __name__)
#         for route in rules:
#             rule, func, methods = route
#             endpoint = rule + '@' + func.__name__
#             bp.add_url_rule(rule, endpoint=endpoint, view_func=func, methods=methods)
#             data = {
#                 'rule': rule,
#                 'methods': methods,
#                 'endpoint': endpoint,
#                 'module': name,
#             }
#
#             db.collection('permissions').update_one(data, update=data, upsert=True)
#
