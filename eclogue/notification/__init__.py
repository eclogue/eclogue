import abc
from flask_log_request_id import current_request_id

from eclogue.model import db

class BaseSender(metaclass=abc.ABCMeta):
    name = ''

    def __init__(self, task_id=None, config=None):
        self.task_id = task_id or str(current_request_id)
        if config:
            self.config = config
            self.enable = bool(config.get('enable'))
        else:
            self.enable, self.config = self.get_config()

    def get_config(self):
        field = self.name + '.enable'
        record = db.collection('setting').find_one({field: True})
        if not record:
            return False, {}

        return True, record.get(self.name)

    @abc.abstractmethod
    def send(self, *args, **kwargs):
        pass
