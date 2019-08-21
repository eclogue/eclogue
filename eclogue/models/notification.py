import time
from eclogue.model import Model


class Notification(Model):
    name = 'notifications'

    def add_notify(self, payload):
        if not payload:
            return {
                       'message': 'invalid params',
                       'code': 104000,
                   }, 400

        user_id = payload.get('user_id')
        msg_type = payload.get('type', 'common')
        title = payload.get('title')
        content = payload.get('content')
        action = payload.get('action')
        params = payload.get('params')
        url = payload.get('url')
        if not user_id:
            return {
                       'message': 'invalid user_id',
                       'code': 104001,
                   }, 400

        if not msg_type:
            return {
                       'message': 'invalid type',
                       'code': 104001,
                   }, 400

        if not title:
            return {
                       'message': 'invalid title',
                       'code': 104001,
                   }, 400

        data = {
            'user_id': user_id,
            'type': msg_type,
            'title': title,
            'content': content,
            'url': url,
            'action': action,
            'params': params,
            'created_at': time.time(),
        }

        self.collection.insert_one(data)

        return {
                   'message': 'ok',
                   'code': 0,
               }, 200
