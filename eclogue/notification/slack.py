import time
import traceback
from slack import WebClient
from eclogue.model import db
from eclogue.notification import BaseSender


class Nexmo(BaseSender):

    name = 'slack'

    @property
    def client(self):
        token = self.config.get('token')

        return WebClient(token=token)

    def send(self, text, channel=None):
        channel = channel or self.config.get('channel')
        params = {
            'channel': channel,
            'text': text,
        }
        data = params.copy()
        data['task_id'] = self.task_id
        data['created_at'] = time.time()
        try:
            result = self.client.chat_postMessage(channel=channel, text=text)
            if not result:
                raise Exception('send nexmo message with uncaught exception')
            else:
                # @todo
                data['result'] = result
                data['code'] = 0
                data['error'] = False
                db.collection('alerts').insert_one(data)

                return result
        except Exception as err:
            data['code'] = err.args[0] if type(err.args[0]) == int else -1
            data['error'] = True
            data['result'] = str(err)
            data['trace'] = traceback.format_exc()
            db.collection('alerts').insert_one(data)

            return False
