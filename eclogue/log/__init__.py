import datetime
import logging
import logging.config
import socket
import sys
import os

from eclogue.config import config
from eclogue.middleware import login_user
from eclogue.model import db


def get_logger(name='eclogue'):
    log_obj = logging.getLogger(name)

    return log_obj


class MongoFormatter(logging.Formatter):

    DEFAULT_PROPERTIES = logging.LogRecord(
        '', '', '', '', '', '', '', '').__dict__.keys()

    def format(self, record):
        """Formats LogRecord into python dictionary."""
        # Standard document
        # pprint.pprint(record.__dict__)
        message = record.getMessage()
        hostname = socket.gethostname()
        if record.name == 'ansible':
            message = record.getMessage()
            for lp in sys.path:
                message = message.replace(lp, os.path.relpath(lp, config.home_path))

        document = {
            'hostname': hostname,
            'ip': socket.gethostbyname(hostname),
            'timestamp': datetime.datetime.utcnow(),
            'level': record.levelname,
            'thread': record.thread,
            'threadName': record.threadName,
            'message': message,
            'loggerName': record.name,
            'fileName': record.pathname,
            'module': record.module,
            'method': record.funcName,
            'lineNumber': record.lineno,
            'processName': record.processName,
            'currentUser': None if not login_user else login_user.get('username')
        }

        # Standard document decorated with exception info
        if record.exc_info is not None:
            document.update({
                'exception': {
                    'message': str(record.exc_info[1]),
                    'code': 0,
                    'stackTrace': self.formatException(record.exc_info)
                }
            })
        # Standard document decorated with extra contextual information
        if len(self.DEFAULT_PROPERTIES) != len(record.__dict__):
            contextual_extra = set(record.__dict__).difference(
                set(self.DEFAULT_PROPERTIES))
            if contextual_extra:
                for key in contextual_extra:
                    document[key] = record.__dict__[key]
        return document


class MongoHandler(logging.Handler):

    def __init__(self, level=logging.INFO):
        logging.Handler.__init__(self, level=level)
        self.formatter = MongoFormatter()

    def emit(self, record):
        """Inserting new logging record to mongo database."""
        try:
            data = self.format(record)
            db.collection('logs').insert_one(data)
        except Exception:
            self.handleError(record)


logger = get_logger()
