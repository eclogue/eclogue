import time

from ..middleware import jwt_required,return_json
from flask import request
from ..model import db


class Admin(object):
    @staticmethod
    @jwt_required
    def add_role():
        params = request.get_json()
        if not params:
            return return_json(400, 10400, 'illegal param')

        name = params.get('name')
        desc = params.get('desc')
        if not name or not desc:
            return return_json(400, 10400, 'name and desc required')

        role = db.collection('role').find_one({'name': name})
        if role:
            return return_json(400, 10400, 'this action has exist')

        count = db.collection('users').count()
        group = {
            'id': count + 1,
            'name': name,
            'desc': desc,
            'status': 1,
            'created_at': time.time()
        }

        res = db.collection('role').insert_one(group)
        if res:
            return return_json(200, 10000, 'ok', {
                'name': name,
                'desc': desc
            })
        return return_json(400, 10500, 'failed')

