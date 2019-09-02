import sys
import errno
import ansible.constants as C
from ansible.utils.display import Display as AnsibleDisplay
from ansible.utils.color import stringc
from eclogue.lib.logger import get_logger

logger = get_logger('console')


class Display(AnsibleDisplay):

    def __init__(self,  verbosity=2):
        AnsibleDisplay.__init__(self, verbosity=verbosity)

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

            # msg2 = to_bytes(msg2)
            # if sys.version_info >= (3,):
            #     # Convert back to text string on python3
            #     # We first convert to a byte string so that we get rid of
            #     # characters that are invalid in the user's locale
            #     msg2 = to_text(msg2, self._output_encoding(stderr=stderr))

            if color == C.COLOR_ERROR:
                logger.error(message)
            else:
                logger.info(message)

        return message
