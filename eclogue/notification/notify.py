import time
from collections.abc import Iterable

from eclogue.notification.slack import Slack
from eclogue.notification.smtp import SMTP
from eclogue.notification.nexmo import Nexmo
from eclogue.notification.wechat import Wechat

from eclogue.models.user import User
from eclogue.model import db


class Notify(object):

    def slack(self, text):
        slack = Slack()
        return slack.send(text)

    def smtp(self, user, text):
        if not user or not user.get('email_status'):
            return False

        to = user.get('email')
        subject = text[:50]
        smtp = SMTP()

        return smtp.send(text=text, to=to, subject=subject)

    def wechat(self, text, user=None):
        wechat = Wechat()

        return wechat.send(text, user)

    def sms(self, user, text):
        phone = user.get('phone')
        phone_status = user.get('phone_status')
        if not phone_status:
            return False

        return Nexmo().send(phone, text)

    def web(self, user_id, msg_type, content):
        record = {
            'title': content[:20],
            'content': content,
            'user_id': user_id,
            'action': None,
            'params': None,
            'read': 0,
            'type': msg_type,
            'created_at': time.time()
        }
        db.collection('notifications').insert_one(record)

    def dispatch(self, user_id, msg_type, content, channel=None):
        user = User().find_by_id(user_id)
        if not user:
            return False

        alerts = user.get('alerts')
        if not alerts or not alerts.get(msg_type):
            return False

        items = alerts.get(msg_type)
        if not items:
            return False

        if channel and isinstance(channel, Iterable):
            items = [i for i in channel if i in items]

        if not items:
            self.web(user_id, msg_type, content)

            return True

        if 'slack' in items:
            self.slack(content)

        if 'wechat' in items:
            self.wechat(content)

        if 'smtp'in items:
            self.smtp(user, content)

        if 'sms' in items:
            self.sms(user, content)

        if 'web' in items:
            self.web(user_id, msg_type, content)

        return True

