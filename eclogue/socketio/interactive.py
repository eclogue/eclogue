import socket
import sys
from paramiko.py3compat import u

try:
    import termios
    import tty

    has_termios = True
except ImportError:
    has_termios = False


def interactive_shell(chan):
    if has_termios:
        posix_shell(chan)
    else:
        windows_shell(chan)


def posix_shell(chan, input, output):
    import select
    try:
        tty.setraw(sys.stdin.fileno())
        tty.setcbreak(sys.stdin.fileno())
        chan.settimeout(0.0)

        while True:
            r, w, e = select.select([chan, sys.stdin], [], [])
            if chan in r:
                try:
                    x = u(chan.recv(1024))
                    if len(x) == 0:
                        sys.stdout.write("\r\n*** EOF\r\n")
                        break
                    sys.stdout.write(x)
                    sys.stdout.flush()
                except socket.timeout:
                    pass
            if sys.stdin in r:
                x = sys.stdin.read(1)
                if len(x) == 0:
                    break
                chan.send(x)

    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, oldtty)


# thanks to Mike Looijmans for this code
def windows_shell(chan):
    import threading

    sys.stdout.write(
        "Line-buffered terminal emulation. Press F6 or ^Z to send EOF.\r\n\r\n"
    )

    def writeall(sock):
        while True:
            data = sock.recv(256)
            if not data:
                sys.stdout.write("\r\n*** EOF ***\r\n\r\n")
                sys.stdout.flush()
                break
            sys.stdout.write(data)
            sys.stdout.flush()

    writer = threading.Thread(target=writeall, args=(chan,))
    writer.start()

    try:
        while True:
            d = sys.stdin.read(1)
            if not d:
                break
            chan.send(d)
    except EOFError:
        # user hit ^Z or F6
        pass
