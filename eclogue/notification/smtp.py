import time
import smtplib
import traceback
from email.mime.text import MIMEText
from email.header import Header
from eclogue.model import db
from eclogue.notification import BaseSender
from eclogue.middleware import login_user


class SMTP(BaseSender):

    name = 'smtp'

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

    @property
    def from_user(self):
        return self.config.get('from')

    def send(self, text, to, subject='', subtype='plain'):
        if not self.enable:
            return False

        subject = subject or 'eclogue system notification'
        receivers = [to]
        params = {
            'sender': self.sender,
            'text': text,
            'from': self.from_user,
            'receivers': receivers,
        }

        message = MIMEText(text, _subtype=subtype, _charset='utf-8')
        message['From'] = Header(self.sender, 'utf-8')
        message['to'] = Header(to, 'utf-8')
        message['Subject'] = Header(subject, 'utf-8')
        data = params.copy()
        data['task_id'] = self.task_id
        data['created_at'] = time.time()
        try:
            result = self.client.sendmail(self.sender, receivers, message.as_string())
            data['result'] = result
            data['code'] = 0
            data['error'] = False
            db.collection('alerts').insert_one(data)

            return result
        except smtplib.SMTPException as e:
            data['code'] = e.args[0] if type(e.args[0]) == int else -1
            data['error'] = True
            data['result'] = str(e)
            data['trace'] = traceback.format_exc()
            db.collection('alerts').insert_one(data)

            return False


