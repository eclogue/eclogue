import sys
from io import StringIO
import re

from eclogue.redis import redis_client


class Reporter(object):
    def __init__(self, task_id, color=False):
        self.store = redis_client
        self.task_id = task_id
        self.color = color

    @property
    def key(self):
        return 'ece#reporter#' + self.task_id

    def write(self, line):
        # if not self.color:
        #     conv = Ansi2HTMLConverter()
        #     conv.prepare(line)
        #     line = conv.attrs().get('body')

        self.store.rpush(self.key, str(line))

    def writeline(self, line):
        self.write(line)

    def writelines(self, lines):
        for line in lines:
            self.write(line)

    def flush(self, time=86400):
        self.store.expire(self.key, time)
        pass

    def read(self):
        logs = self.store.lrange(self.key, 0, -1)
        if not logs:
            return ''

        return '\n'.join(logs)

    def close(self, force=False):
        if force:
            self.store.delete(self.key)
        else:
            self.flush()

    def getvalue(self):
        return self.read()

