from ..middleware import jwt_required,return_json
from flask import request
from ..model import db
import time


class Permission(object):
    @staticmethod
    @jwt_required
    def add_action():
        params = request.get_json()
        if not params:
            return return_json(400, 10400, 'illegal param')

        action = params.get('action')
        desc = params.get('desc')
        if not action or not desc:
            return return_json(400, 10400, 'action and desc required')

        perm = db.collection('permission').find_one({'action': action})
        if perm:
            return return_json(400, 10400, 'this action has exist')

        count = db.collection('permission').count()
        group = {
            'id': count + 1,
            'action': action,
            'desc': desc,
            'status': 1,
            'created_at': time.time()
        }

        res = db.collection('permission').insert_one(group)
        if res:
            return return_json(200, 10000, 'ok', {
                'action': action,
                'desc': desc
            })
        return return_json(400, 10500, 'failed')

