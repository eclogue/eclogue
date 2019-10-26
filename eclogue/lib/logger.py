import datetime
import logging
import logging.config
import socket
import sys
import os

from io import StringIO
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
            'fileName': os.path.relpath(record.pathname, config.home_path),
            'module': record.module,
            'method': record.funcName,
            'lineNumber': record.lineno,
            'processName': record.processName,
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

        user = None
        if not document.get('currentUser') and login_user:
            user = login_user.get('username')

        document['currentUser'] = user

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


class ConsoleHandler(logging.StreamHandler):

    def __init__(self, level=logging.DEBUG):
        logging.Handler.__init__(self, level=level)
        # self.formatter = MongoFormatter()
        self.stream = None

    def emit(self, record):
        try:
            msg = self.format(record)
            stream = sys.stdout
            self.setStream(stream=stream)
            stream.write(msg + self.terminator)
            self.flush()
        except RecursionError:  # See issue 36272
            raise
        except Exception:
            self.handleError(record)

logger = get_logger()
