import datetime
import logging
import logging.config
import socket
import sys
import os

from eclogue.config import config
from eclogue.middleware import login_user


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

