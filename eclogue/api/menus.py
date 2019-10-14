import datetime
import time
import uuid
from bson import ObjectId
from flask_restful import Resource
from eclogue.model import db
from eclogue.middleware import jwt_required, login_user
from flask import jsonify, request
from eclogue.models.user import User
from eclogue.models.menu import Menu
from eclogue.lib.logger import logger
from eclogue.utils import md5


class Menus(Resource):

    @staticmethod
    @jwt_required
    def get_menus():
        query = request.args
        user_id = login_user.get('user_id')
        is_admin = login_user.get('is_admin')
        # is_admin = False
        if not is_admin:
            user = User()
            permissions = user.get_permissions(user_id)
            menus = permissions[0]
        else:
            def add_actions(item):
                item['actions'] = ['get', 'post', 'delete', 'put', 'patch']
                return item
            where = {'status': 1}
            if query and query.get('all'):
                where = {}

            menus = db.collection('menus').find(where).sort('id', 1)
            menus = map(add_actions, menus)

        return jsonify({
            'message': 'ok',
            'code': 0,
            'data': list(menus)
        })

    @staticmethod
    @jwt_required
    def add_menu():
        params = request.get_json()
        if not params:
            return jsonify({
                'message': 'param required',
                'code': 4000
            }), 400

        checked = True
        if 'name' not in params:
            checked = False
        if 'route' not in params:
            checked = False
        if 'id' not in params:
            checked = False

        if 'status' in params:
            checked = type(params.get('status')) == int

        if checked is False:
            return jsonify({
                'message': 'param incorrect',
                'code': 104001
            }), 400

        id = str(ObjectId.from_datetime(datetime.datetime.now()))
        data = {
            'name': params['name'],
            'route': params['route'],
            'id': id,
            'apis': params.get('apis') or [],
            'icon': params.get('icon', ''),
            'bpid': params.get('bpid') or '0',
            'mpid': params.get('mpid') or '0',
            'status': params.get('status', 1),
            'add_by': login_user.get('username'),
            'created_at': time.time()
        }
        db.collection('menus').insert_one(data)
        logger.info('add menu', extra={'record': data})

        return jsonify({
            'message': 'ok',
            'code': 0,
        })

    @staticmethod
    @jwt_required
    def edit_menu(_id):
        params = request.get_json()
        if not params:
            return jsonify({
                'message': 'param required',
                'code': 4000
            }), 400

        is_admin = login_user.get('is_admin')
        if not is_admin:
            return jsonify({
                'message': 'permission deny',
                'code': 104010
            }), 401

        obj_id = ObjectId(_id)
        record = db.collection('menus').find_one({'_id': obj_id})
        if not record:
            return jsonify({
                'message': 'record not found',
                'code': 104040
            }), 404

        name = params.get('name')
        route = params.get('route')
        icon = params.get('icon')
        mpid = params.get('mpid')
        bpid = params.get('bpid')
        status = params.get('status', 1)
        apis = params.get('apis') or []
        update = {
            'apis': apis
        }
        if name:
            update['name'] = name

        if route:
            update['route'] = route

        if icon:
            update['icon'] = icon

        if status is not None:
            update['status'] = status

        if mpid:
            if int(mpid) > 0:
                existed = db.collection('menus').find_one({'id': mpid})
                if not existed:
                    return jsonify({
                        'message': 'invalid mpid',
                        'code': 104002
                    }), 400

            elif mpid == record.get('id'):
                return jsonify({
                    'message': 'invalid mpid',
                    'code': 104003
                }), 400

            update['mpid'] = str(mpid)

        if bpid:
            if int(bpid) > 0:
                existed = db.collection('menus').find_one({'id': bpid})
                if not existed:
                    return jsonify({
                        'message': 'invalid bpid',
                        'code': 104002
                    }), 400

            elif bpid == record.get('id'):
                return jsonify({
                    'message': 'invalid bpid',
                    'code': 104003
                }), 400

            update['bpid'] = str(bpid)

        if update:
            update['updated_at'] = datetime.datetime.now()
            db.collection('menus').update_one({'_id': obj_id}, {'$set': update})
            logger.info('update menu', extra={'record': record, 'change': update})

        return jsonify({
            'message': 'ok',
            'code': 0,
        })

    @staticmethod
    @jwt_required
    def delete_menu(_id):
        is_admin = login_user.get('is_admin')
        if not is_admin:
            return jsonify({
                'message': 'permission deny',
                'code': 104010
            }), 401

        record = db.collection('menus').find_one({'_id': ObjectId(_id)})
        if not record:
            return jsonify({
                'message': 'record not found',
                'code': 104040
            }), 404

        db.collection('menus').delete_one({'_id': record['_id']})

        return jsonify({
            'message': 'ok',
            'code': 0,
        })
