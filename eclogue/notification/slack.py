import time
import datetime
from slack import WebClient
from eclogue.model import db
from flask_log_request_id import current_request_id


class Nexmo(object):

    def __init__(self):
        self.enable, self.config = self.get_config()

    @property
    def client(self):
        token = self.config.get('token')

        return WebClient(token=token)

    @staticmethod
    def get_config():
        record = db.collection('setting').find_one({'slack.enable': True})
        if not record:
            return False, {}

        return record.get('slack'), True

    def send(self, text, channel=None):
        channel = channel or self.config.get('channel')
        params = {
            'channel': channel,
            'text': text,
        }
        result = self.client.chat_postMessage(channel=channel, text=text)
        data = params.copy()
        data['request_id'] = current_request_id
        data['created_at'] = time.time()
        if not result:
            raise Exception('send nexmo message with uncaught exception')
        else:
            # @todo
            db.collection('alerts').insert_one(data)

            return True
