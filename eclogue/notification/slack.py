import time
import traceback
import requests
from eclogue.model import db
from eclogue.notification import BaseSender


class Slack(BaseSender):

    name = 'slack'

    @property
    def webhook(self):
        return self.config.get('webhook')

    def send(self, text, channel=None):
        if not self.enable:
            return False

        channel = channel or self.config.get('channel')
        params = {
            'channel': channel,
            'text': text,
        }
        data = params.copy()
        data['task_id'] = self.task_id
        data['created_at'] = time.time()
        try:
            header = {
                'Content-type': 'application/json'
            }
            body = {
                'text': text
            }
            response = requests.post(url=self.webhook, json=body, headers=header)
            if not response:
                raise Exception('send slack message with uncaught exception')
            else:
                # @todo
                result = response.text
                status_code = response.status_code
                data['result'] = result
                if response.ok:
                    data['code'] = status_code
                    data['error'] = True
                else:
                    data['code'] = 0
                    data['error'] = False

                db.collection('alerts').insert_one(data)

                return response
        except Exception as err:
            data['code'] = err.args[0] if type(err.args[0]) == int else -1
            data['error'] = True
            data['result'] = str(err)
            data['trace'] = traceback.format_exc()
            db.collection('alerts').insert_one(data)

            return False
