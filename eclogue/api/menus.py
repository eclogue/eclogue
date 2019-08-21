import pymongo
from flask_restful import Resource
from eclogue.model import db
from eclogue.middleware import jwt_required, login_user
from flask import jsonify, request
from eclogue.models.user import User
from eclogue.lib.logger import logger


class Menus(Resource):

    @staticmethod
    @jwt_required
    def get_menus():
        username = login_user.get('username')
        is_admin = login_user.get('is_admin')
        if not is_admin:
            user = User()
            user_info = user.collection.find_one({'username': username})
            permissions = user.get_permissions(user_info['_id'])
            menus = permissions[0]
        else:
            def add_actions(item):
                item['actions'] = ['get', 'post', 'delete', 'put', 'patch']
                return item

            menus = db.collection('menus').find({}).sort('id', 1)
            menus = map(add_actions, menus)

        return jsonify({
            'message': 'ok',
            'code': 0,
            'data': list(menus)
        })

    @staticmethod
    @jwt_required
    def add():
        params = request.get_json()
        if not params:
            return jsonify({
                'message': 'param required',
                'code': 4000
            }), 400

        print(params)
        check = True
        if 'name' not in params:
            check = False
        if 'route' not in params:
            check = False
        if 'id' not in params:
            check = False

        if check is False:
            return jsonify({
                'message': 'param incorrect',
                'code': 4001
            }), 400

        data = {
            'name': params['name'],
            'route': params['route'],
            'id': params['id'],
            'icon': params.get('icon', ''),
            'bpid': params.get('bpid', 0),
            'description': params.get('description', ''),
        }
        db.collection('menus').insert_one(data)
        logger.info('add menu', extra={'record': data})

        return jsonify({
            'message': 'ok',
            'code': 0,
        })

