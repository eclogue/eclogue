import sys
import errno
import fcntl
import getpass
import locale
import os
import random
import subprocess
import sys
import textwrap
import time

from struct import unpack, pack
from termios import TIOCGWINSZ
import ansible.constants as C
from ansible.utils.display import Display as AnsibleDisplay
from ansible.errors import AnsibleError
from ansible.utils.color import stringc
from ansible.module_utils._text import to_bytes, to_text
from eclogue.lib.logger import get_logger
from ansible.utils.unsafe_proxy import wrap_var

logger = get_logger('console')


class Display(AnsibleDisplay):
    """
    extend from ansible.utils.display
    """
    def __init__(self, verbosity=2, task_id=None):
        AnsibleDisplay.__init__(self, verbosity=verbosity)
        self.task_id = task_id

    def display(self, msg, color=None, stderr=False, screen_only=False, log_only=False):
        """ Display a message to the user
        Note: msg *must* be a unicode string to prevent UnicodeError tracebacks.
        function extend from ansible.utils.display
        """
        message = msg
        if color:
            message = stringc(msg, color)

        if not log_only:
            if not msg.endswith('\n'):
                message = msg + '\n'
            else:
                message = msg
            if not stderr:
                fileobj = sys.stdout
            else:
                fileobj = sys.stderr

            fileobj.write(message)

            try:
                fileobj.flush()
            except IOError as e:
                # Ignore EPIPE in case fileobj has been prematurely closed, eg.
                # when piping to "head -n1"
                if e.errno != errno.EPIPE:
                    raise

        if logger and not screen_only:
            message = msg.lstrip('\n')

            if color == C.COLOR_ERROR:
                logger.error(message, extra={'task_id': self.task_id})
            else:
                logger.info(message, extra={'task_id': self.task_id})

        return message

    def v(self, msg, host=None):
        return self.verbose(msg, host=host, caplevel=0)

    def vv(self, msg, host=None):
        return self.verbose(msg, host=host, caplevel=1)

    def vvv(self, msg, host=None):
        return self.verbose(msg, host=host, caplevel=2)

    def vvvv(self, msg, host=None):
        return self.verbose(msg, host=host, caplevel=3)

    def vvvvv(self, msg, host=None):
        return self.verbose(msg, host=host, caplevel=4)

    def vvvvvv(self, msg, host=None):
        return self.verbose(msg, host=host, caplevel=5)

    def debug(self, msg, host=None):
        if C.DEFAULT_DEBUG:
            if host is None:
                self.display("%6d %0.5f: %s" % (os.getpid(), time.time(), msg), color=C.COLOR_DEBUG)
            else:
                self.display("%6d %0.5f [%s]: %s" % (os.getpid(), time.time(), host, msg), color=C.COLOR_DEBUG)

    def verbose(self, msg, host=None, caplevel=2):

        to_stderr = C.VERBOSE_TO_STDERR
        if self.verbosity > caplevel:
            if host is None:
                self.display(msg, color=C.COLOR_VERBOSE, stderr=to_stderr)
            else:
                self.display("<%s> %s" % (host, msg), color=C.COLOR_VERBOSE, stderr=to_stderr)

    def deprecated(self, msg, version=None, removed=False):
        ''' used to print out a deprecation message.'''

        if not removed and not C.DEPRECATION_WARNINGS:
            return

        if not removed:
            if version:
                new_msg = "[DEPRECATION WARNING]: %s. This feature will be removed in version %s." % (msg, version)
            else:
                new_msg = "[DEPRECATION WARNING]: %s. This feature will be removed in a future release." % (msg)
            new_msg = new_msg + " Deprecation warnings can be disabled by setting deprecation_warnings=False in ansible.cfg.\n\n"
        else:
            raise AnsibleError("[DEPRECATED]: %s.\nPlease update your playbooks." % msg)

        wrapped = textwrap.wrap(new_msg, self.columns, drop_whitespace=False)
        new_msg = "\n".join(wrapped) + "\n"

        if new_msg not in self._deprecations:
            self.display(new_msg.strip(), color=C.COLOR_DEPRECATE, stderr=True)
            self._deprecations[new_msg] = 1

    def warning(self, msg, formatted=False):

        if not formatted:
            new_msg = "\n[WARNING]: %s" % msg
            wrapped = textwrap.wrap(new_msg, self.columns)
            new_msg = "\n".join(wrapped) + "\n"
        else:
            new_msg = "\n[WARNING]: \n%s" % msg

        if new_msg not in self._warns:
            self.display(new_msg, color=C.COLOR_WARN, stderr=True)
            self._warns[new_msg] = 1

    def system_warning(self, msg):
        if C.SYSTEM_WARNINGS:
            self.warning(msg)

    def banner(self, msg, color=None, cows=True):
        '''
        Prints a header-looking line with cowsay or stars with length depending on terminal width (3 minimum)
        '''
        if self.b_cowsay and cows:
            try:
                self.banner_cowsay(msg)
                return
            except OSError:
                self.warning("somebody cleverly deleted cowsay or something during the PB run.  heh.")

        msg = msg.strip()
        star_len = self.columns - len(msg)
        if star_len <= 3:
            star_len = 3
        stars = u"*" * star_len
        self.display(u"\n%s %s" % (msg, stars), color=color)

    def banner_cowsay(self, msg, color=None):
        if u": [" in msg:
            msg = msg.replace(u"[", u"")
            if msg.endswith(u"]"):
                msg = msg[:-1]
        runcmd = [self.b_cowsay, b"-W", b"60"]
        if self.noncow:
            thecow = self.noncow
            if thecow == 'random':
                thecow = random.choice(list(self.cows_available))
            runcmd.append(b'-f')
            runcmd.append(to_bytes(thecow))
        runcmd.append(to_bytes(msg))
        cmd = subprocess.Popen(runcmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (out, err) = cmd.communicate()
        self.display(u"%s\n" % to_text(out), color=color)

    def error(self, msg, wrap_text=True):
        if wrap_text:
            new_msg = u"\n[ERROR]: %s" % msg
            wrapped = textwrap.wrap(new_msg, self.columns)
            new_msg = u"\n".join(wrapped) + u"\n"
        else:
            new_msg = u"ERROR! %s" % msg
        if new_msg not in self._errors:
            self.display(new_msg, color=C.COLOR_ERROR, stderr=True)
            self._errors[new_msg] = 1

    @staticmethod
    def prompt(msg, private=False):
        prompt_string = to_bytes(msg, encoding=Display._output_encoding())
        if sys.version_info >= (3,):
            # Convert back into text on python3.  We do this double conversion
            # to get rid of characters that are illegal in the user's locale
            prompt_string = to_text(prompt_string)

        if private:
            return getpass.getpass(prompt_string)
        else:
            return input(prompt_string)

    def do_var_prompt(self, varname, private=True, prompt=None, encrypt=None, confirm=False, salt_size=None, salt=None,
                      default=None, unsafe=None):

        result = None
        if sys.__stdin__.isatty():

            do_prompt = self.prompt

            if prompt and default is not None:
                msg = "%s [%s]: " % (prompt, default)
            elif prompt:
                msg = "%s: " % prompt
            else:
                msg = 'input for %s: ' % varname

            if confirm:
                while True:
                    result = do_prompt(msg, private)
                    second = do_prompt("confirm " + msg, private)
                    if result == second:
                        break
                    self.display("***** VALUES ENTERED DO NOT MATCH ****")
            else:
                result = do_prompt(msg, private)
        else:
            result = None
            self.warning("Not prompting as we are not in interactive mode")

        # if result is false and default is not None
        if not result and default is not None:
            result = default

        if encrypt:
            # Circular import because encrypt needs a display class
            from ansible.utils.encrypt import do_encrypt
            result = do_encrypt(result, encrypt, salt_size, salt)

        # handle utf-8 chars
        result = to_text(result, errors='surrogate_or_strict')

        if unsafe:
            result = wrap_var(result)
        return result

    @staticmethod
    def _output_encoding(stderr=False):
        encoding = locale.getpreferredencoding()
        # https://bugs.python.org/issue6202
        # Python2 hardcodes an obsolete value on Mac.  Use MacOSX defaults
        # instead.
        if encoding in ('mac-roman',):
            encoding = 'utf-8'
        return encoding

    def _set_column_width(self):
        if os.isatty(0):
            tty_size = unpack('HHHH', fcntl.ioctl(0, TIOCGWINSZ, pack('HHHH', 0, 0, 0, 0)))[1]
        else:
            tty_size = 0
        self.columns = max(79, tty_size - 1)
