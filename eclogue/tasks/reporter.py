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
        return '\n'.join(self.store.lrange(self.key, 0, -1))

    def close(self, force=False):
        if force:
            self.store.delete(self.key)
        else:
            self.flush()

    def getvalue(self):
        return self.read()


class Sentinel:

    def __init__(self):
        self.stdout = sys.stdout
        self.stderr = sys.stderr
        self.stdout_reporter = Reporter(StringIO())
        # self.stderr_reporter = Reporter(StringIO())

    def report(self):
        sys.stdout = self.stdout_reporter
        # sys.stderr = self.stderr_reporter

    def close(self):
        sys.stdout = self.stdout
        sys.stderr = self.stderr
        self.stdout_reporter.close()
        # self.stderr_reporter.close()

    def dump(self):
        return {
            'stdout': self.stdout_reporter.read(),
            # 'stderr': self.stderr_reporter.read(),
        }

    def __del__(self):
        self.close()
