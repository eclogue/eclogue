import sys
from io import StringIO


class Reporter(object):
    def __init__(self, fp):
        self.fp = fp

    def write(self, s):
        self.fp.write(s)

    def writeline(self, line):
        self.fp.writeline(line)

    def writelines(self, lines):
        self.fp.writelines(lines)

    def flush(self):
        self.fp.flush()

    def read(self):
        return self.fp.getvalue()

    def close(self, force=False):
        self.fp.flush()
        if force:
            self.fp.close()

    def getvalue(self):
        if hasattr(self.fp, 'getvalue'):
            return self.fp.getvalue()


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
