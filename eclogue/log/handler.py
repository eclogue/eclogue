import sys
import logging
import logging.config

from eclogue.model import db
from eclogue.log.formatter import MongoFormatter


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
