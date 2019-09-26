import time
import datetime
from wechatpy.enterprise import WeChatClient
from eclogue.model import db
from flask_log_request_id import current_request_id


class Wechat(object):

    def __init__(self):
        self.enable, self.config = self.get_config()

    @property
    def client(self):
        corp_id = self.config.get('corp_id')
        secret = self.config.get('secret')

        return WeChatClient(corp_id, secret)

    @property
    def agent_id(self):

        return self.config.get('agent_id')

    @staticmethod
    def get_config():
        record = db.collection('setting').find_one({'wechat.enable': True})
        if not record:
            return False, {}

        return True, record.get('wechat')

    def send(self, text, user=None):
        user = user or '@all'
        params = {
            'agent_id': self.agent_id,
            'text': text,
            'user': user,
        }

        result = self.client.message.send_text(self.agent_id, user, text)
        data = params.copy()
        data['request_id'] = str(current_request_id)
        data['created_at'] = time.time()
        if not result:
            raise Exception('send nexmo message with uncaught exception')
        else:
            data['result'] = result
            db.collection('alerts').insert_one(data)

        return result
