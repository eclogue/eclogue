import time
import datetime
import smtplib
from email.mime.text import MIMEText
from email.header import Header

from wechatpy.enterprise import WeChatClient
from eclogue.model import db
from flask_log_request_id import current_request_id


class SMTP(object):

    def __init__(self):
        self.enable, self.config = self.get_config()

    @property
    def client(self):
        host = self.config.get('server')
        port = self.config.get('port')
        tls = self.config.get('tls')
        user = self.config.get('user')
        password = self.config.get('password')
        client = smtplib.SMTP(host=host, port=int(port))
        client.connect(host=host, port=int(port))
        if tls:
            client.starttls()

        if user and password:
            client.login(user, password)

        return client

    @property
    def sender(self):

        return self.config.get('sender')

    @staticmethod
    def get_config():
        record = db.collection('setting').find_one({'smtp.enable': True})
        if not record:
            return False, {}

        return True, record.get('smtp')

    def send(self, text, from_user, receivers, subject=''):
        subject = subject or 'eclogue system notification'
        params = {
            'sender': self.sender,
            'text': text,
            'from': from_user,
            'receivers': receivers,
        }

        message = MIMEText(text, 'plain', 'utf-8')
        message['From'] = Header(self.sender, 'utf-8')
        message['to'] = Header(from_user, 'utf-8')
        message['Subject'] = Header(subject, 'utf-8')
        data = params.copy()
        data['request_id'] = str(current_request_id)
        data['created_at'] = time.time()
        try:
            result = self.client.sendmail(self.sender, receivers, message.as_string())
            data['result'] = result
            data['code'] = 0

            db.collection('alerts').insert_one(data)

            return result
        except smtplib.SMTPException as e:
            data['code'] = e.args[0]
            data['error'] = str(e)
            db.collection('alerts').insert_one(data)

            return False


