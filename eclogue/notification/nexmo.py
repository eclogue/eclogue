import time
import datetime
from nexmo import Client
from eclogue.model import db
from flask_log_request_id import current_request_id


class Nexmo(object):

    def __init__(self):
        self.enable, self.config = self.get_config()

    @property
    def client(self):
        api_key = self.config.get('key')
        api_secret = self.config.get('secret')

        return Client(key=api_key, secret=api_secret)

    @property
    def sender(self):
        return self.config.get('from') or 'eclogue'

    @staticmethod
    def get_config():
        record = db.collection('setting').find_one({'nexmo.enable': True})
        if not record:
            return False, {}

        return record.get('nexmo'), True

    def send(self, phone, text):
        params = {
            'phone': phone,
            'from': self.sender,
            'text': text,
        }
        result = self.client.send_message(params)
        data = params.copy()
        data['request_id'] = current_request_id
        data['created_at'] = time.time()
        if not result.get('messages'):
            raise Exception('send nexmo message with uncaught exception')
        else:
            response = result['messages'][0]
            print(response)
            status = response.get('status')
            data['status'] = status
            if response.get('status') == '0':
                data['message_id'] = response.get('message-id')
            else:
                data['error'] = response['error-text']

            db.collection('alerts').insert_one(data)

            return True

