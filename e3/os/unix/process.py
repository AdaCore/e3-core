import os
import sys
from ctypes import Structure, pointer, c_int, POINTER
from e3.os.unix.constant import WNOWAIT


def wait(blocking=False):
    """Wait for a child process to exit.

    Note that the function lets the process in waitable state

    :param blocking: if True block until one process finish.
    :type blocking: bool
    :return: pid of the terminated process or 0
    :rtype: int
    """
    options = WNOWAIT
    if not blocking:
        options |= os.WNOHANG

    if sys.platform.startswith('linux'):
        import ctypes

        # Wait only for exited processes
        WEXITED = 4
        options |= WEXITED

        libc = ctypes.CDLL("libc.so.6", use_errno=True)

        class Siginfo_t(Structure):
            _fields_ = [('signo', c_int),
                        ('errno', c_int),
                        ('code', c_int),
                        ('padding', c_int),
                        ('pid', c_int),
                        ('uid', c_int),
                        ('status', c_int),
                        ('pad2', c_int * 64)]

        # Allocate a buffer to old the siginfo_t structure
        siginfo_t = Siginfo_t()
        waitid = libc.waitid
        waitid.restype = c_int
        waitid.argtype = [c_int, c_int, POINTER(Siginfo_t), c_int]

        status = waitid(0, 0, pointer(siginfo_t), options)
        if status != 0:
            raise OSError("waitid error")

        return siginfo_t.pid
    else:
        pid, _, _ = os.wait3(options)
        return pid
