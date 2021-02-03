"""Suprocesses management.

This module provides some functions and classes to ease spawn of
processes in blocking or non blocking mode, redirection of its stdout,
stderr and stdin. It also provides some helpers to check the process
status
"""


from __future__ import annotations

import errno
import logging
import os
import signal
import subprocess
import sys
import time
from typing import TYPE_CHECKING

import e3.env
import e3.log
from e3.os.fs import which
from e3.text import bytes_as_str


if TYPE_CHECKING:
    from typing import cast, Any, IO, List, Literal, NoReturn, Optional, Union

    CmdLine = List[str]
    AnyCmdLine = Union[List[CmdLine], CmdLine]
    STDOUT_VALUE = Literal[-1]
    PIPE_VALUE = Literal[-2]
    DEVNULL_VALUE = Literal[-3]

    # Make STDOUT subprocess constant visible in e3.os.process
    STDOUT = cast(STDOUT_VALUE, subprocess.STDOUT)
    PIPE = cast(PIPE_VALUE, subprocess.PIPE)
    DEVNULL = cast(DEVNULL_VALUE, subprocess.DEVNULL)
else:
    STDOUT = subprocess.STDOUT
    PIPE = subprocess.PIPE
    DEVNULL = subprocess.DEVNULL

logger = e3.log.getLogger("os.process")

# Special logger used for command line logging.
# This allow user to filter easily the command lines log from the rest
CMD_LOGGER_NAME = "os.process.cmdline"

cmdlogger = e3.log.getLogger(CMD_LOGGER_NAME)


# Use psutil.Popen when available to get psutil.Process properties and
# methods available in Run.internal
try:
    import psutil
    from psutil import Popen
except ImportError:  # defensive code
    from subprocess import Popen

    psutil = None


def subprocess_setup() -> None:
    """Reset SIGPIPE handler.

    Python installs a SIGPIPE handler by default. This is usually not
    what non-Python subprocesses expect.
    """
    # Set sigpipe only when set_sigpipe is True
    # This should fix HC16-020 and could be activated by default
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)  # all: no cover


def get_rlimit(platform: Optional[str] = None) -> str:
    if platform is None:
        platform = e3.env.Env().build.platform
    if platform == "x86_64-windows64":
        platform = "x86_64-windows"

    from pkg_resources import resource_filename

    return resource_filename(__name__, os.path.join("data", f"rlimit-{platform}"))


def quote_arg(arg: str) -> str:
    """Return the quoted version of the given argument.

    Returns a human-friendly representation of the given argument, but with all
    extra quoting done if necessary.  The intent is to produce an argument
    image that can be copy/pasted on a POSIX shell command (at a shell prompt).
    :param arg: argument to quote
    """
    # The empty argument is a bit of a special case, as it does not
    # contain any character that might need quoting, and yet still
    # needs to be quoted.
    if arg == "":
        return "''"

    need_quoting = (
        "|",
        "&",
        ";",
        "<",
        ">",
        "(",
        ")",
        "$",
        "`",
        "\\",
        '"',
        "'",
        " ",
        "\t",
        "\n",
        # The POSIX spec says that the following
        # characters might need some extra quoting
        # depending on the circumstances.  We just
        # always quote them, to be safe (and to avoid
        # things like file globbing which are sometimes
        # performed by the shell). We do leave '%' and
        # '=' alone, as I don't see how they could
        # cause problems.
        "*",
        "?",
        "[",
        "#",
        "~",
    )
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
            arg = arg.replace("\n", r"'\n'")
            return f"'{arg}'"
    # No quoting needed.  Return the argument as is.
    return arg


def to_cmd_lines(cmds: AnyCmdLine) -> List[CmdLine]:
    if isinstance(cmds[0], str):
        # Turn the simple command into a special case of
        # the multiple-commands case.  This will allow us
        # to treat both cases the same way.
        return [cmds]  # type: ignore
    else:
        return cmds  # type: ignore


def command_line_image(cmds: AnyCmdLine) -> str:
    """Return a string image of the given command(s).

    :param cmds: Same as the cmds parameter in the Run.__init__ method.

    This method also handles quoting as defined for POSIX shells.
    This means that arguments containing special characters
    (such as a simple space, or a backslash, for instance),
    are properly quoted.  This makes it possible to execute
    the same command by copy/pasting the image in a shell
    prompt.

    The result is expected to be a string that can be sent verbatim
    to a shell for execution.
    """
    return " | ".join(
        " ".join(quote_arg(arg) for arg in cmd) for cmd in to_cmd_lines(cmds)
    )


def enable_commands_handler(filename: str, mode: str = "a") -> logging.Handler:
    """Add a handler that log all commands launched with Run in a file.

    :param filename: path to log the commands
    :param mode: mode used to open the file (default is 'a')
    :return: the added handler
    """

    class CmdFilter(logging.Filter):
        """Keep only e3.os.process.cmdline records."""

        def filter(self, record: logging.LogRecord) -> bool:
            return True if record.name == "e3." + CMD_LOGGER_NAME else False

    # Here we don't attach the handler directly to the cmdline logger. Indeed
    # in class like e3.Main we do attach handlers to the root logger. In that
    # case only the handlers attached to root logger are called.
    rootlog = logging.getLogger()
    fh = logging.FileHandler(filename, mode=mode)
    fh.addFilter(CmdFilter())
    fh.setLevel(logging.DEBUG)
    rootlog.addHandler(fh)
    return fh


def disable_commands_handler(handler: logging.Handler) -> None:
    """Disable special handler for commands.

    :param handler: Handler returned by enable_commands_handler
    """
    logging.getLogger().removeHandler(handler)
    handler.flush()
    handler.close()


class Run:
    """Class to handle processes.

    :ivar cmds: The ``cmds`` argument passed to the __init__ method
        (a command line passed in a list, or a list of command lines passed as
        a list of list).
    :ivar status: The exit status. As the exit status is only meaningful after
        the process has exited, its initial value is None.  When a problem
        running the command is detected and a process does not get
        created, its value gets set to the special value 127.
    :ivar raw_out: process standard output as bytes (if instanciated with
        output = PIPE). Use self.out to get a decoded string.
    :ivar raw_err: same as raw_out but for standard error.
    :ivar pid: PID. Set to -1 if the command failed to run.
    """

    def __init__(
        self,
        cmds: AnyCmdLine,
        cwd: Optional[str] = None,
        output: STDOUT_VALUE | DEVNULL_VALUE | PIPE_VALUE | str | IO | None = PIPE,
        error: STDOUT_VALUE | DEVNULL_VALUE | PIPE_VALUE | str | IO | None = STDOUT,
        input: DEVNULL_VALUE | PIPE_VALUE | str | IO | None = None,  # noqa: A002
        bg: bool = False,
        timeout: Optional[int] = None,
        env: Optional[dict] = None,
        set_sigpipe: bool = True,
        parse_shebang: bool = False,
        ignore_environ: bool = True,
    ) -> None:
        """Spawn a process.

        :param cmds: two possibilities:
            1) a command line: a tool name and its arguments, passed
            in a list. e.g. ['ls', '-a', '.']
            2) a list of command lines (as defined in (1)): the
            different commands will be piped. This means that
            [['ps', '-a'], ['grep', 'vxsim']] will be equivalent to
            the system command line 'ps -a | grep vxsim'.
        :param cwd: directory in which the process should be executed (string
            or None). If None then current directory is used
        :param output: can be PIPE (default), a filename string, a fd on an
            already opened file, a python file object or None (for stdout).
        :param error: same as output or STDOUT, which indicates that the
            stderr data from the applications should be captured into the same
            file handle as for stdout.
        :param input: same as output
        :param bg: if True then run in background
        :param timeout: limit execution time (in seconds), None means
            unlimited
        :param env: dictionary for environment variables (e.g. os.environ)
        :param set_sigpipe: reset SIGPIPE handler to default value
        :param parse_shebang: take the #! interpreter line into account
        :param ignore_environ: Applies only when env parameter is not None.
            When set to True (the default), the only environment variables
            passed to the program are the ones provided by the env parameter.
            Otherwise, the environment passed to the program consists of the
            environment variables currently defined (os.environ) augmented by
            the ones provided in env.

        :raise OSError: when trying to execute a non-existent file.

        If you specify a filename for output or stderr then file content is
        reseted (equiv. to > in shell). If you prepend the filename with '+'
        then the file will be opened in append mode (equiv. to >> in shell)
        If you prepend the input with '|', then the content of input string
        will be used for process stdin.
        """

        def add_interpreter_command(cmd_line: CmdLine) -> CmdLine:
            """Add the interpreter defined in the #! line to cmd_line.

            If the #! line cannot be parsed, just return the cmd_line
            unchanged

            On windows, /usr/bin/env will be ignored to avoid a dependency on
            cygwin and /bin/bash & /bin/sh are replaced by $SHELL if defined.
            :param cmd_line: command line
            """
            if not parse_shebang:
                # nothing to do
                return cmd_line
            prog = which(cmd_line[0], default=None)
            if prog is None:
                # Not found. Do not modify the command line
                return cmd_line

            with open(prog) as f:
                try:
                    header = f.read()[0:2]
                except UnicodeDecodeError:
                    # unknown header - cannot decode the first two bytes
                    return cmd_line
                if header != "#!":
                    # Unknown header
                    return cmd_line
                # Header found, get the interpreter command in the first line
                f.seek(0)
                line = f.readline()
                interpreter_cmds = [
                    word.strip() for word in line[line.find("!") + 1 :].split()
                ]
                # Pass the program path to the interpreter
                if len(cmd_line) > 1:
                    cmd_line = [prog] + list(cmd_line[1:])
                else:
                    cmd_line = [prog]

                if sys.platform == "win32":  # unix: no cover
                    if interpreter_cmds[0] == "/usr/bin/env":
                        # On windows be sure that PATH is taken into account by
                        # using which. In some cases involving python
                        # interpreter, the python interpreter used to run this
                        # module has been used rather than the first one on the
                        # path.
                        interpreter_cmds[1] = which(
                            interpreter_cmds[1], default=interpreter_cmds[1]
                        )
                        return interpreter_cmds[1:] + cmd_line
                    elif (
                        interpreter_cmds[0] in ("/bin/bash", "/bin/sh")
                        and "SHELL" in os.environ
                    ):
                        return [os.environ["SHELL"]] + cmd_line
                return interpreter_cmds + cmd_line

        # First resolve output, error and input
        self.input_file = File(input, "r")
        self.output_file = File(output, "w")
        self.error_file = File(error, "w")

        self.status: Optional[int] = None
        self.raw_out = b""
        self.raw_err = b""
        self.cmds = []

        if env is not None:
            if ignore_environ:
                if sys.platform == "win32":
                    # On Windows not all environment variables can be
                    # discarded. At least SYSTEMDRIVE, SYSTEMROOT should be
                    # set. In order to be portable propagate their value in
                    # case the user does not pass them in env when
                    # ignore_environ is set to True.
                    tmp = {}
                    for var in ("SYSTEMDRIVE", "SYSTEMROOT"):
                        if var not in env and var in os.environ:
                            tmp[var] = os.environ[var]
                    tmp.update(env)
                    env = tmp
            else:
                # ignore_environ is False, so get a copy of the current
                # environment and update it with the env dictionary.
                tmp = os.environ.copy()
                tmp.update(env)
                env = tmp

        rlimit_args = []
        if timeout is not None:
            rlimit = get_rlimit()
            if os.path.exists(rlimit):
                rlimit_args = [rlimit, "%d" % timeout]
            else:
                logger.warning("cannot find rlimit at %s", rlimit)
                rlimit_args = []

        try:
            self.cmds = [add_interpreter_command(c) for c in to_cmd_lines(cmds)]
            self.cmds[0] = rlimit_args + list(self.cmds[0])

            cmdlogger.debug(
                "Run: cd %s; %s",
                cwd if cwd is not None else os.getcwd(),
                self.command_line_image(),
            )

            if len(self.cmds) == 1:
                popen_args = {
                    "stdin": self.input_file.fd,
                    "stdout": self.output_file.fd,
                    "stderr": self.error_file.fd,
                    "cwd": cwd,
                    "env": env,
                    "universal_newlines": False,
                }

                if sys.platform != "win32" and set_sigpipe:  # windows: no cover
                    # preexec_fn is no supported on windows
                    popen_args["preexec_fn"] = subprocess_setup  # type: ignore

                if sys.platform == "win32":
                    popen_args["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP

                self.internal = Popen(self.cmds[0], **popen_args)

            else:
                runs: List[subprocess.Popen] = []
                for index, cmd in enumerate(self.cmds):
                    if index == 0:
                        stdin: int | IO[Any] = self.input_file.fd
                    else:
                        previous_stdout = runs[index - 1].stdout
                        assert previous_stdout is not None
                        stdin = previous_stdout

                    # When connecting two processes using a Pipe don't use
                    # universal_newlines mode. Indeed commands transmitting
                    # binary data between them will crash
                    # (e.g. gzip -dc foo.txt | tar -xf -)
                    if index == len(self.cmds) - 1:
                        stdout = self.output_file.fd
                    else:
                        stdout = subprocess.PIPE

                    popen_args = {
                        "stdin": stdin,
                        "stdout": stdout,
                        "stderr": self.error_file.fd,
                        "cwd": cwd,
                        "env": env,
                        "universal_newlines": False,
                    }

                    if sys.platform != "win32" and set_sigpipe:  # windows: no cover
                        # preexec_fn is no supported on windows
                        popen_args["preexec_fn"] = subprocess_setup  # type: ignore

                    if sys.platform == "win32":
                        popen_args[
                            "creationflags"
                        ] = subprocess.CREATE_NEW_PROCESS_GROUP

                    try:
                        runs.append(Popen(cmd, **popen_args))
                    except OSError:
                        logger.error("error when spawning %s", cmd)
                        # We have an error (e.g. file not found), try to kill
                        # all processes already started.
                        for p in runs:
                            p.terminate()
                        raise

                    self.internal = runs[-1]

        except Exception as e:  # defensive code
            self.__error(e, self.cmds)
            raise

        self.pid = self.internal.pid

        if not bg:
            self.wait()

    @property
    def out(self) -> str:
        """Process output as string.

        Attempt is done to decode as utf-8 the output. If the output is not in
        utf-8 a string representation will be returned
        (see e3.text.bytes_as_str).
        """
        return bytes_as_str(self.raw_out)

    @property
    def err(self) -> str:
        """Process error as string.

        Attempt is done to decode as utf-8 the output. If the output is not in
        utf-8 a string representation will be returned
        (see e3.text.bytes_as_str).
        """
        return bytes_as_str(self.raw_err)

    def command_line_image(self) -> str:
        """Get shell command line image of the spawned command(s).

        This just a convenient wrapper around the function of the same
        name.
        """
        return command_line_image(self.cmds)

    def close_files(self) -> None:
        """Close all file descriptors."""
        self.output_file.close()
        self.error_file.close()
        self.input_file.close()

    def __error(self, error: Exception, cmds: List[CmdLine]) -> None:
        """Set pid to -1 and status to 127 before closing files."""
        self.close_files()
        logger.error(error)

        def not_found(path: str) -> NoReturn:
            """Raise OSError.

            :param path: path of the executable
            """
            logger.error("%s not found", path)
            e3.log.debug("PATH=%s", os.environ["PATH"])
            raise OSError(errno.ENOENT, f"No such file or directory, {path} not found")

        # Try to send an helpful message if one of the executable has not
        # been found.
        for cmd in cmds:
            if which(cmd[0], default=None) is None:
                not_found(cmd[0])

    def wait(self) -> int:
        """Wait until process ends and return its status.

        :return: exit code of the process
        """
        if self.status is not None:
            # Wait has already been called
            return self.status

        # If there is no pipe in the loop then just do a wait. Otherwise
        # in order to avoid blocked processes due to full pipes, use
        # communicate.
        if (
            self.output_file.fd != subprocess.PIPE
            and self.error_file.fd != subprocess.PIPE
            and self.input_file.fd != subprocess.PIPE
        ):
            self.status = self.internal.wait()
        else:
            tmp_input: Optional[str | bytes] = None
            if self.input_file.fd == subprocess.PIPE:
                tmp_input = self.input_file.get_command()

            if isinstance(tmp_input, str):
                tmp_input = tmp_input.encode("utf-8")

            (self.raw_out, self.raw_err) = self.internal.communicate(tmp_input)
            self.status = self.internal.returncode

        self.close_files()
        return self.status

    def poll(self) -> Optional[int]:
        """Check the process status and set self.status if available.

        This method checks whether the underlying process has exited
        or not. If it hasn't, then it just returns None immediately.
        Otherwise, it stores the process' exit code in self.status
        and then returns it.

        :return: None if the process is still alive; otherwise, returns
          the process exit status.
        """
        if self.status is not None:
            # Process is already terminated and wait been called
            return self.status

        result = self.internal.poll()

        if result is not None:
            # Process is finished, call wait to finalize it (closing handles,
            # ...)
            return self.wait()
        else:
            return None

    def kill(self, recursive: bool = True, timeout: int = 3) -> None:
        """Kill the process.

        :param recursive: if True, try to kill the complete process tree
        :param timeout: wait timeout (in seconds) after sending the kill
            signal (when recursive=True)
        """
        if recursive:
            kill_process_tree(self.internal, timeout=timeout)
        else:
            self.internal.kill()

    def interrupt(self) -> None:
        """Send SIGINT to the process, kill on Windows."""
        if sys.platform == "win32":
            self.kill()  # Ctrl-C event is unreliable on Windows
        else:
            self.internal.send_signal(signal.SIGINT)

    def is_running(self) -> bool:
        """Check whether the process is running."""
        if psutil is None:  # defensive code
            # psutil not imported, use our is_running function
            return is_running(self.pid)
        else:
            return self.internal.is_running()

    def children(self) -> List[Any]:
        """Return list of child processes (using psutil)."""
        if psutil is None:  # defensive code
            raise NotImplementedError("Run.children() require psutil")
        return self.internal.children()


class File:
    """Can be a PIPE, a file object."""

    def __init__(self, name: Any, mode: str = "r"):
        """Create a new File.

        :param name: can be PIPE, STDOUT, a filename string, an opened fd, a
            python file object, or a command to pipe (if starts with ``|``)
        :param mode: can be 'r' or 'w' if name starts with + the mode will be
            a+
        """
        assert mode in "rw", "Mode should be r or w"
        self.fd: int | IO[str]

        self.name = name
        self.to_close = False
        if isinstance(name, str):
            # can be a pipe or a filename
            if mode == "r" and name.startswith("|"):
                self.fd = subprocess.PIPE
            else:
                if mode == "w":
                    if name.startswith("+"):
                        open_mode = "a+"
                        name = name[1:]
                    else:
                        open_mode = "w+"
                else:
                    open_mode = "r"

                self.fd = open(name, open_mode)
                if open_mode == "a+":
                    self.fd.seek(0, 2)
                self.to_close = True

        else:
            # this is a file descriptor
            self.fd = name

    def get_command(self) -> Optional[str]:
        """Return the command to run to create the pipe."""
        if self.fd == subprocess.PIPE:
            return self.name[1:]
        else:
            return None

    def close(self) -> None:
        """Close the file if needed."""
        if self.to_close:
            fd = self.fd
            fd.close()  # type: ignore


class WaitError(Exception):
    pass


def wait_for_processes(process_list: List[Run], timeout: float) -> Optional[int]:
    """Wait for several processes spawned with Run.

    :param process_list: a list of Run objects
    :param timeout: a timeout in seconds. If 0 block until a process ends.

    :return: None in case of timeout or the index in process Run corresponding
        to the first process that end
    """
    if len(process_list) == 0:
        return None

    start = time.time()
    remain = timeout

    if sys.platform == "win32":  # unix: no cover
        from e3.os.windows.process import process_exit_code, wait_for_objects

        handles = [int(p.internal._handle) for p in process_list]

        while True:
            try:
                idx = wait_for_objects(handles, remain, False)
                if idx is None:
                    return

                if process_exit_code(handles[idx]) is None:
                    # Process is still active so wait after updating timeout
                    remain = timeout - time.time() + start

                    if remain <= 0:
                        # No remaining time
                        return None
                else:
                    # Process is exiting so finalize it by calling wait
                    process_list[idx].wait()
                    return idx
            except OSError:
                raise WaitError

    else:  # windows: no cover
        import select

        # Each time a SIGCHLD signal is received write into pipe. Use
        # then select which support timeout arguments to wait.
        fd_r, fd_w = os.pipe()

        def handler(signum: int, frame: Any) -> None:
            del signum, frame
            os.write(fd_w, b"a")

        signal.signal(signal.SIGCHLD, handler)

        try:
            while remain >= 0.0 or timeout == 0:
                # Do a first check in case a SIGCHLD was emited before the
                # initialisation of the handler.
                for index, p in enumerate(process_list):
                    if p.poll() is not None:
                        return index

                # Wait for a sigchld signal. Note that select might
                # be interrupted by signals thus the loop
                select_args = [[fd_r], [], []]
                if timeout != 0:
                    select_args.append(remain)

                while True:
                    try:
                        l_r, _, _ = select.select(*select_args)  # type: ignore
                        if l_r:
                            os.read(fd_r, 1)
                        break
                    except OSError:
                        pass

                remain = timeout - time.time() + start

            logger.warning(
                "no process ended after %f seconds", time.time() - start
            )  # defensive code

        finally:
            # Be sure to remove signal handler and close pipe
            signal.signal(signal.SIGCHLD, 0)
            os.close(fd_r)
            os.close(fd_w)
    return None


def is_running(pid: int) -> bool:
    """Check whether a process with the given pid is running.

    :param pid: an integer (e.g the value of Run().pid)
    """
    if sys.platform == "win32":  # unix: no cover
        from e3.os.windows.native_api import Access, NT
        from e3.os.windows.process import process_exit_code

        handle = NT.OpenProcess(Access.PROCESS_QUERY_INFORMATION, False, pid)

        try:
            if not handle:
                return False
            return process_exit_code(handle) is None

        finally:
            NT.Close(handle)

    else:  # windows: no cover
        try:
            # We send a null signal to check the validity of pid
            os.kill(pid, 0)
        except OSError as e:
            # If the process is not found, errno will be set to ESRCH
            return e.errno != errno.ESRCH
        return True


def kill_process_tree(pid: int | Any, timeout: int = 3) -> bool:
    """Kill a hierarchy of processes.

    :param pid: pid of the toplevel process
    :param timeout: wait timeout after sending the kill signal
    :return: True if all processes either don't exist or have been killed,
        False if there are some processes still alive.
    """
    if isinstance(pid, psutil.Process):
        parent_process = pid
    else:
        try:
            parent_process = psutil.Process(pid)
        except psutil.NoSuchProcess as err:
            e3.log.debug(err)
            return True

    logger.debug("kill_process_tree %s", parent_process)

    try:
        children = parent_process.children(recursive=True)
    except psutil.NoSuchProcess as err:
        e3.log.debug(err)
        return True

    all_processes = [parent_process] + children
    for p in all_processes:
        try:
            logger.debug("kill process %s (%s)", p, p.cmdline())
            p.kill()
        except psutil.NoSuchProcess:  # defensive code
            pass

    def on_terminate(p: str) -> None:
        """Log info when a process terminate."""
        logger.debug("process %s killed", p)

    try:
        gone, alive = psutil.wait_procs(
            all_processes, timeout=timeout, callback=on_terminate
        )
        e3.log.debug("%d processes killed", len(gone))
        for p in alive:  # defensive code
            logger.warn("process %s survived kill()", p)

        return True
    except psutil.TimeoutExpired as err:  # defensive code
        e3.log.debug(err)
        return False
