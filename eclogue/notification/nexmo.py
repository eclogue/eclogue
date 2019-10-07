import time
import traceback
from nexmo import Client
from eclogue.model import db
from eclogue.notification import BaseSender


class Nexmo(BaseSender):

    name = 'nexmo'

    @property
    def client(self):
        api_key = self.config.get('key')
        api_secret = self.config.get('secret')

        return Client(key=api_key, secret=api_secret)

    @property
    def sender(self):
        return self.config.get('from') or 'eclogue'

    def send(self, phone, text):
        params = {
            'phone': phone,
            'from': self.sender,
            'text': text,
        }
        data = params.copy()
        data['task_id'] = self.task_id
        data['created_at'] = time.time()
        try:
            result = self.client.send_message(params)
            if not result.get('messages'):
                raise Exception('send nexmo message with uncaught exception')
            else:
                response = result['messages'][0]
                status = response.get('status')
                data['status'] = status
                if response.get('status') == '0':
                    data['result'] = result
                    data['code'] = 0
                    data['error'] = False
                else:
                    data['error'] = True
                    data['result'] = response
                    data['code'] = response.get('status')

                db.collection('alerts').insert_one(data)

                return response
        except Exception as err:
            data['code'] = err.args[0] if type(err.args[0]) == int else -1
            data['error'] = True
            data['result'] = str(err)
            data['trace'] = traceback.format_exc()
            db.collection('alerts').insert_one(data)

            return False


