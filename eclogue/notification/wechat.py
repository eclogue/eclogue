import time
import datetime
import traceback
from wechatpy.enterprise import WeChatClient
from eclogue.model import db
from eclogue.notification import BaseSender


class Wechat(BaseSender):
    name = 'wechat'

    @property
    def client(self):
        corp_id = self.config.get('corp_id')
        secret = self.config.get('secret')

        return WeChatClient(corp_id, secret)

    @property
    def agent_id(self):

        return self.config.get('agent_id')

    def send(self, text, user=None):
        user = user or '@all'
        params = {
            'agent_id': self.agent_id,
            'text': text,
            'user': user,
        }
        data = params.copy()
        data['task_id'] = self.task_id
        data['created_at'] = time.time()
        try:
            result = self.client.message.send_text(self.agent_id, user, text)
            if not result:
                raise Exception('send nexmo message with uncaught exception')
            else:
                data['code'] = 0
                data['error'] = False
                data['result'] = result

            db.collection('alerts').insert_one(data)

            return result
        except Exception as err:
            data['code'] = err.args[0] if type(err.args[0]) == int else -1
            data['error'] = True
            data['result'] = str(err.args[1])
            data['trace'] = traceback.format_exc(limit=20)
            db.collection('alerts').insert_one(data)

            return False


