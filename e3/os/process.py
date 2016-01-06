"""Suprocesses management.

This module provides some functions and classes to ease spawn of processes
in blocking or non blocking mode, redirection of its stdout, stderr and stdin.
It also provides some helpers to check the process status
"""
from __future__ import absolute_import
import errno
import itertools
import logging
import os
import re
import subprocess
import sys
import time

import e3.log
import e3.env

logger = e3.log.getLogger('os.process')

# Special logger used for command line logging.
# This allow user to filter easily the command lines log from the rest
CMD_LOGGER_NAME = 'os.process.cmdline'
cmdlogger = e3.log.getLogger(CMD_LOGGER_NAME)


def subprocess_setup():
    """Reset SIGPIPE handler.

    Python installs a SIGPIPE handler by default. This is usually not
    what non-Python subprocesses expect.
    """
    # Set sigpipe only when set_sigpipe is True
    # This should fix HC16-020 and could be activated by default
    import signal
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)


def get_rlimit(platform=None):
    if platform is None:
        platform = e3.env.Env().build.platform

    from pkg_resources import resource_filename
    return resource_filename(
        __name__, os.path.join(
            'data', 'rlimit-%s' % platform))


def quote_arg(arg):
    """Return the quoted version of the given argument.

    Returns a human-friendly representation of the given argument, but with all
    extra quoting done if necessary.  The intent is to produce an argument
    image that can be copy/pasted on a POSIX shell command (at a shell prompt).
    :param arg: argument to quote
    :type arg: str
    """
    # The empty argument is a bit of a special case, as it does not
    # contain any character that might need quoting, and yet still
    # needs to be quoted.
    if arg == '':
        return "''"

    need_quoting = ('|', '&', ';', '<', '>', '(', ')', '$',
                    '`', '\\', '"', "'", ' ', '\t', '\n',
                    # The POSIX spec says that the following
                    # characters might need some extra quoting
                    # depending on the circumstances.  We just
                    # always quote them, to be safe (and to avoid
                    # things like file globbing which are sometimes
                    # performed by the shell). We do leave '%' and
                    # '=' alone, as I don't see how they could
                    # cause problems.
                    '*', '?', '[', '#', '~')
    for char in need_quoting:
        if char in arg:
            # The way we do this is by simply enclosing the argument
            # inside single quotes.  However, we have to be careful
            # of single-quotes inside the argument, as they need
            # to be escaped (which we cannot do while still inside.
            # a single-quote string).
            arg = arg.replace("'", r"'\''")
            # Also, it seems to be nicer to print new-line characters
            # as '\n' rather than as a new-line...
            arg = arg.replace('\n', r"'\n'")
            return "'%s'" % arg
    # No quoting needed.  Return the argument as is.
    return arg


def command_line_image(cmds):
    """Return a string image of the given command(s).

    :param cmds: Same as the cmds parameter in the Run.__init__ method.
    :type: list[str] | list[list[str]]

    :rtype: str

    This method also handles quoting as defined for POSIX shells.
    This means that arguments containing special characters
    (such as a simple space, or a backslash, for instance),
    are properly quoted.  This makes it possible to execute
    the same command by copy/pasting the image in a shell
    prompt.

    The result is expected to be a string that can be sent verbatim
    to a shell for execution.
    """
    if isinstance(cmds[0], basestring):
        # Turn the simple command into a special case of
        # the multiple-commands case.  This will allow us
        # to treat both cases the same way.
        cmds = (cmds, )
    return ' | '.join((' '.join((quote_arg(arg) for arg in cmd))
                       for cmd in cmds))


def enable_commands_handler(filename, mode='a'):
    """Add a handler that log all commands launched with Run in a file.

    :param filename: path to log the commands
    :type filename: str
    :param mode: mode used to open the file (default is 'a')
    :type mode: str
    """
    class CmdFilter(logging.Filter):
        """Keep only e3.os.process.cmdline records."""

        def filter(self, record):
            return 1 if record.name == CMD_LOGGER_NAME else 0

    # Here we don't attach the handler directly to the cmdline logger. Indeed
    # in class like e3.Main we do attach handlers to the root logger. In that
    # case only the handlers attached to root logger are called.
    rootlog = logging.getLogger()
    fh = logging.FileHandler(filename, mode=mode)
    fh.addFilter(CmdFilter())
    fh.setLevel(logging.DEBUG)
    rootlog.addHandler(fh)


class Run(object):
    """Class to handle processes.

    :ivar cmds: The ``cmds`` argument passed to the __init__ method
        (a command line passed in a list, or a list of command lines passed as
        a list of list).
    :ivar status: The exit status. As the exit status is only meaningful after
        the process has exited, its initial value is None.  When a problem
        running the command is detected and a process does not get
        created, its value gets set to the special value 127.
    :ivar out: process standard output  (if instanciated with output = PIPE)
    :ivar err: same as out but for standard error
    :ivar pid: PID. Set to -1 if the command failed to run.
    """

    def __init__(self, cmds, cwd=None, output=subprocess.PIPE,
                 error=subprocess.STDOUT, input=None, bg=False, timeout=None,
                 env=None, set_sigpipe=True, parse_shebang=False,
                 ignore_environ=True, python_executable=sys.executable):
        """Spawn a process.

        :param cmds: two possibilities:
            1) a command line: a tool name and its arguments, passed
            in a list. e.g. ['ls', '-a', '.']
            2) a list of command lines (as defined in (1)): the
            different commands will be piped. This means that
            [['ps', '-a'], ['grep', 'vxsim']] will be equivalent to
            the system command line 'ps -a | grep vxsim'.
        :type cmds: list[str] | list[list[str]]
        :param cwd: directory in which the process should be executed (string
            or None). If None then current directory is used
        :type cwd: str | None
        :param output: can be PIPE (default), a filename string, a fd on an
            already opened file, a python file object or None (for stdout).
        :type output: int | str | file | None
        :param error: same as output or STDOUT, which indicates that the
            stderr data from the applications should be captured into the same
            file handle as for stdout.
        :type error: int | str | file | None
        :param input: same as output
        :type input: int | str | file | None
        :param bg: if True then run in background
        :type bg: bool
        :param timeout: limit execution time (in seconds), None means
            unlimited
        :type timeout: int | None
        :param env: dictionary for environment variables (e.g. os.environ)
        :type env: dict
        :param set_sigpipe: reset SIGPIPE handler to default value
        :type set_sigpipe: bool
        :param parse_shebang: take the #! interpreter line into account
        :type parse_shebang: bool
        :param ignore_environ: Applies only when env parameter is not None.
            When set to True (the default), the only environment variables
            passed to the program are the ones provided by the env parameter.
            Otherwise, the environment passed to the program consists of the
            environment variables currently defined (os.environ) augmented by
            the ones provided in env.
        :type ignore_environ: bool
        :param python_executable: name or path to the python executable
        :type python_executable: str

        :raise OSError: when trying to execute a non-existent file.

        If you specify a filename for output or stderr then file content is
        reseted (equiv. to > in shell). If you prepend the filename with '+'
        then the file will be opened in append mode (equiv. to >> in shell)
        If you prepend the input with '|', then the content of input string
        will be used for process stdin.
        """
        def add_interpreter_command(cmd_line):
            """Add the interpreter defined in the #! line to cmd_line.

            If the #! line cannot be parsed, just return the cmd_line
            unchanged

            If the interpreter command line contains /usr/bin/env python it
            will be replaced by the value of python_executable

            On windows, /usr/bin/env will be ignored to avoid a dependency on
            cygwin
            :param cmd_line: command line
            :type cmd_line: list[str]
            """
            if not parse_shebang:
                # nothing to do
                return cmd_line
            prog = which(cmd_line[0], default=None)
            if prog is None:
                # Not found. Do not modify the command line
                return cmd_line

            with open(prog) as f:
                header = f.read()[0:2]
                if header != "#!":
                    # Unknown header
                    return cmd_line
                # Header found, get the interpreter command in the first line
                f.seek(0)
                line = f.readline()
                interpreter_cmds = [l.strip() for l in
                                    line[line.find('!') + 1:].split()]
                # Pass the program path to the interpreter
                if len(cmd_line) > 1:
                    cmd_line = [prog] + list(cmd_line[1:])
                else:
                    cmd_line = [prog]

                # If the interpreter is '/usr/bin/env python', use
                # python_executable instead to keep the same python executable
                if interpreter_cmds[0:2] == ['/usr/bin/env', 'python']:
                    if len(interpreter_cmds) > 2:
                        return [python_executable] + \
                            interpreter_cmds[2:] + cmd_line
                    else:
                        return [python_executable] + cmd_line
                elif sys.platform == 'win32':
                    if interpreter_cmds[0] == '/usr/bin/env':
                        return interpreter_cmds[1:] + cmd_line
                    elif interpreter_cmds[0] in ('/bin/bash', '/bin/sh') and \
                            'SHELL' in os.environ:
                        return [os.environ['SHELL']] + cmd_line
                return interpreter_cmds + cmd_line

        # First resolve output, error and input
        self.input_file = File(input, 'r')
        self.output_file = File(output, 'w')
        self.error_file = File(error, 'w')

        self.status = None
        self.out = ''
        self.err = ''
        self.cmds = []

        if env is not None and not ignore_environ:
            # ignore_environ is False, so get a copy of the current
            # environment and update it with the env dictionnary.
            tmp = os.environ.copy()
            tmp.update(env)
            env = tmp

        rlimit_args = []
        if timeout is not None:
            rlimit = get_rlimit()
            if os.path.exists(rlimit):
                rlimit_args = [rlimit, '%d' % timeout]
            else:
                logger.warning('cannot find rlimit at %s', rlimit)
                rlimit_args = []

        try:
            if isinstance(cmds[0], basestring):
                self.cmds = rlimit_args + list(add_interpreter_command(cmds))
            else:
                self.cmds = [add_interpreter_command(c) for c in cmds]
                self.cmds[0] = rlimit_args + list(self.cmds[0])

            cmdlogger.debug('Run: cd %s; %s' % (
                cwd if cwd is not None else os.getcwd(),
                self.command_line_image()))

            if isinstance(cmds[0], basestring):
                popen_args = {
                    'stdin': self.input_file.fd,
                    'stdout': self.output_file.fd,
                    'stderr': self.error_file.fd,
                    'cwd': cwd,
                    'env': env,
                    'universal_newlines': True}

                if sys.platform != 'win32' and set_sigpipe:
                    # preexec_fn is no supported on windows
                    popen_args['preexec_fn'] = subprocess_setup

                self.internal = subprocess.Popen(self.cmds, **popen_args)

            else:
                runs = []
                for index, cmd in enumerate(self.cmds):
                    if index == 0:
                        stdin = self.input_file.fd
                    else:
                        stdin = runs[index - 1].stdout

                    # When connecting two processes using a Pipe don't use
                    # universal_newlines mode. Indeed commands transmitting
                    # binary data between them will crash
                    # (e.g. gzip -dc foo.txt | tar -xf -)
                    if index == len(self.cmds) - 1:
                        stdout = self.output_file.fd
                        txt_mode = True
                    else:
                        stdout = subprocess.PIPE
                        txt_mode = False

                    popen_args = {
                        'stdin': stdin,
                        'stdout': stdout,
                        'stderr': self.error_file.fd,
                        'cwd': cwd,
                        'env': env,
                        'universal_newlines': txt_mode}

                    if sys.platform != 'win32' and set_sigpipe:
                        # preexec_fn is no supported on windows
                        popen_args['preexec_fn'] = subprocess_setup

                    runs.append(subprocess.Popen(cmd, **popen_args))
                    self.internal = runs[-1]

        except Exception as e:
            self.__error(e, self.cmds)
            raise

        self.pid = self.internal.pid

        if not bg:
            self.wait()

    def command_line_image(self):
        """Get shell command line image of the spawned command(s).

        :rtype: str

        This just a convenient wrapper around the function of the same
        name.
        """
        return command_line_image(self.cmds)

    def close_files(self):
        """Close all file descriptors."""
        self.output_file.close()
        self.error_file.close()
        self.input_file.close()

    def __error(self, error, cmds):
        """Set pid to -1 and status to 127 before closing files."""
        self.pid = -1
        self.status = 127
        self.close_files()
        logger.error(error)

        def not_found(path):
            """Raise OSError.

            :param path: path of the executable
            :type path: str
            """
            logger.error("%s not found", path)
            e3.log.debug('PATH=%s', os.environ['PATH'])
            raise OSError(errno.ENOENT,
                          'No such file or directory, %s not found' % path)

        # Try to send an helpful message if one of the executable has not
        # been found.
        if isinstance(cmds[0], basestring):
            if which(cmds[0], default=None) is None:
                not_found(cmds[0])
        else:
            for cmd in cmds:
                if which(cmd[0], default=None) is None:
                    not_found(cmd[0])

    def wait(self):
        """Wait until process ends and return its status."""
        if self.status == 127:
            return self.status

        self.status = None

        # If there is no pipe in the loop then just do a wait. Otherwise
        # in order to avoid blocked processes due to full pipes, use
        # communicate.
        if self.output_file.fd != subprocess.PIPE and \
                self.error_file.fd != subprocess.PIPE and \
                self.input_file.fd != subprocess.PIPE:
            self.status = self.internal.wait()
        else:
            tmp_input = None
            if self.input_file.fd == subprocess.PIPE:
                tmp_input = self.input_file.get_command()

            (self.out, self.err) = self.internal.communicate(tmp_input)
            self.status = self.internal.returncode

        self.close_files()
        return self.status

    def poll(self):
        """Check the process status and set self.status if available.

        This method checks whether the underlying process has exited
        or not. If it hasn't, then it just returns None immediately.
        Otherwise, it stores the process' exit code in self.status
        and then returns it.

        :return: None if the process is still alive; otherwise, returns
          the process exit status.
        :rtype: int | None
        """
        if self.status == 127:
            # Special value indicating that we failed to run the command,
            # so there is nothing to poll.  Just return that as the exit
            # code.
            return self.status

        result = self.internal.poll()
        if result is not None:
            self.status = result
        return result

    def kill(self):
        """Kill the process."""
        self.internal.kill()


class File(object):
    """Can be a PIPE, a file object."""

    def __init__(self, name, mode='r'):
        """Create a new File.

        PARAMETERS
          name: can be PIPE, STDOUT, a filename string, an opened fd, a python
            file object, or a command to pipe (if starts with |)
          mode: can be 'r' or 'w' if name starts with + the mode will be a+
        """
        assert mode in 'rw', 'Mode should be r or w'

        self.name = name
        self.to_close = False
        if isinstance(name, str) or isinstance(name, unicode):
            # can be a pipe or a filename
            if mode == 'r' and name.startswith('|'):
                self.fd = subprocess.PIPE
            else:
                if mode == 'w':
                    if name.startswith('+'):
                        open_mode = 'a+'
                        name = name[1:]
                    else:
                        open_mode = 'w+'
                else:
                    open_mode = 'r'

                self.fd = open(name, open_mode)
                if open_mode == 'a+':
                    self.fd.seek(0, 2)
                self.to_close = True

        else:
            # this is a file descriptor
            self.fd = name

    def get_command(self):
        """Return the command to run to create the pipe."""
        if self.fd == subprocess.PIPE:
            return self.name[1:]

    def close(self):
        """Close the file if needed."""
        if self.to_close:
            self.fd.close()


class WaitError(Exception):
    pass


def wait_for_processes(process_list, timeout):
    """Wait for several processes spawned with Run.

    :param process_list: a list of Run objects
    :type process_list: list[Run]
    :param timeout: a timeout in seconds. If 0 block until a process ends.
    :type timeout: int

    :return: None in case of timeout or the index in process Run corresponding
        to the first process that end
    :rtype: None | int
    """
    if len(process_list) == 0:
        return None

    if sys.platform == 'win32':
        import ctypes
        from ctypes.wintypes import HANDLE, DWORD
        from ctypes import byref

        plen = len(process_list)
        WAIT_OBJECT = 0x0
        WAIT_ABANDONED = 0x80
        WAIT_TIMEOUT = 0x102
        WAIT_FAILED = 0xFFFFFFFF
        INFINITE = DWORD(0xFFFFFFFF)

        # Compute timeout
        if timeout == 0:
            win_timeout = INFINITE
        else:
            win_timeout = DWORD(int(timeout * 1000))

        start = time.time()
        # Build the handler array c structure
        handle_arr = HANDLE * len(process_list)
        handles = handle_arr(*[int(p.internal._handle) for p in process_list])

        while True:
            result = ctypes.windll.kernel32.WaitForMultipleObjects(
                DWORD(plen),
                handles, 0,
                win_timeout)
            if (WAIT_OBJECT <= result < WAIT_OBJECT + plen) or \
                    (WAIT_ABANDONED <= result < WAIT_ABANDONED + plen):
                # One process has been signaled. Check we have an exit code
                if result >= WAIT_ABANDONED:
                    result -= WAIT_ABANDONED
                exit_code = DWORD()
                ctypes.windll.kernel32.GetExitCodeProcess(handles[result],
                                                          byref(exit_code))
                if exit_code == DWORD(259):
                    # Process is still active so loop
                    # Update windows timeout
                    if timeout == 0:
                        win_timeout = INFINITE
                    else:
                        remain_seconds = timeout - time.time() + start
                        if remain_seconds <= 0:
                            return None
                        else:
                            win_timeout = DWORD(int(remain_seconds * 1000))
                else:
                    # At the stage we need to set the process status and close
                    # related handles. Indeed we will not be able to use the
                    # wait method afterwards and retrieve it.
                    process_list[result].status = exit_code
                    process_list[result].close_files()
                    return result
            elif result == WAIT_TIMEOUT:
                return None
            elif result == WAIT_FAILED:
                raise WaitError
    else:
        start = time.time()
        remain_seconds = timeout

        wait3_option = os.WNOHANG
        if timeout == 0:
            wait3_option = 0

        while remain_seconds >= 0.0 or timeout == 0:

            pid, exit_status, resource_usage = os.wait3(wait3_option)
            if (pid, exit_status) != (0, 0):
                # We have a result
                result = [(index, p) for index, p in
                          enumerate(process_list) if p.pid == pid]
                if len(result) > 0:
                    # At the stage we need to set the process status and close
                    # related handles. Indeed we will not be able to use the
                    # wait method afterwards and retrieve it.
                    process_list[result[0][0]].status = exit_status
                    process_list[result[0][0]].close_files()
                    return result[0][0]
            time.sleep(1.0)
            remain_seconds = timeout - time.time() + start
        return None


def is_running(pid):
    """Check whether a process with the given pid is running.

    :param pid: an integer (e.g the value of Run().pid)
    :type pid: int

    :rtype: bool
    """
    if sys.platform == 'win32':
        import ctypes
        import ctypes.wintypes
        h = ctypes.windll.kernel32.OpenProcess(1, 0, pid)
        try:
            if h == 0:
                return False

            # Pid exists for the handle, now check whether we can retrieve
            # the exit code
            exit_code = ctypes.wintypes.DWORD()
            if ctypes.windll.kernel32.GetExitCodeProcess(
                    h, ctypes.byref(exit_code)) == 0:
                # GetExitCodeProcess returns 0 when it could not get the value
                # of the exit code
                return True
            if exit_code.value == 259:
                # GetExitCodeProcess returns 259 is the process is still
                # running
                return True

            # Process not running
            return False
        finally:
            ctypes.windll.kernel32.CloseHandle(h)

    else:
        try:
            # We send a null signal to check the validity of pid
            os.kill(pid, 0)
        except OSError as e:
            # If the process is not found, errno will be set to ESRCH
            return e.errno != errno.ESRCH
        return True


def which(prog, paths=None, default=''):
    """Locate executable.

    :param prog: program to find
    :type prog: str
    :param paths: if not None then we use this value instead of PATH to look
        for the executable.
    :type paths: str | None
    :param default: default value to return if not found
    :type default: str | None | T

    :return: absolute path to the program on success, found by searching for an
      executable in the directories listed in the environment variable PATH
      or default value if not found
    :rtype: str | None | T
    """
    def is_exe(exe_fpath):
        return os.path.isfile(exe_fpath) and os.access(exe_fpath, os.X_OK)

    def possible_names(exe_fpath):
        names = [exe_fpath]
        if sys.platform == 'win32':
            names.extend([exe_fpath + ext for ext in
                          os.environ.get('PATHEXT', '').split(';')])
        return names

    fpath, fname = os.path.split(prog)
    if fpath:
        # Full path given, check if executable
        for progname in possible_names(prog):
            if is_exe(progname):
                return progname
    else:
        # Check for all directories listed in $PATH
        if paths is None:
            paths = os.environ["PATH"]

        for pathdir in paths.split(os.pathsep):
            exe_file = os.path.join(pathdir, prog)
            for progname in possible_names(exe_file):
                if is_exe(progname):
                    return progname

    # Not found.
    return default


def kill_processes_with_handle(path):
    """Kill processes with a handle on the selected directory.

    Note: this works only on windows

    :param path: path
    :type path: str
    :return: the output of launched commands (can be used for logging
        purposes)
    :rtype: str
    """
    if sys.platform == 'win32':
        path = re.sub('^[a-zA-Z]:(.*)', r'\1', path).replace('/', '\\')
        mod_dir = os.path.dirname(__file__)
        handle_path = os.path.abspath(
            os.path.join(mod_dir, 'internal', 'data', 'libexec',
                         'x86-windows', 'handle.exe'))
        handle_p = Run([handle_path, '/AcceptEULA', '-a', '-u', path])
        msg = "handle_output:\n%s" % handle_p.out
        logger.debug(msg)
        process_list = set(re.findall(r'pid: *([0-9]+) *', handle_p.out))
        if process_list:
            taskkill_p = Run(['taskkill.exe', '/F'] +
                             list(itertools.chain.from_iterable(
                                 [['/PID', '%s' % k] for k in process_list])),
                             error=subprocess.STDOUT)
            logger.debug("taskkill output:\n%s", taskkill_p.out)
            msg += "taskkill output:\n%s" % taskkill_p.out
        return msg
    else:
        return ''
