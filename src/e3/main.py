"""Main program initialization.

This package provides a class called Main used to initialize a python script
invoked from command line. The main goal is to ensure consistency in terms of
interface, documentation and logging activities for all scripts using e3.

The script will support by default the following switches::

    -v|--verbose to enable verbose mode (a console logger is added)
    -h|--help    display command line help
    --log-file FILE
                 to redirect logs to a given file (this is independent of
                 verbose option)
    --console-logs
                 disable color, progress bars, and redirect as much as
                 possible to stdout, starting lines with the given prefix

In addition, if the add_targets_options parameter is set to True
when instantiating an object of class Main, the following switches
will also be provided::

    --build      to set the build
    --host       to set the host
    --target     to set the target
"""

from __future__ import annotations

from argparse import ArgumentParser
import logging
import os
import signal
import sys
import threading

from typing import TYPE_CHECKING

import e3
import e3.log
from e3.env import Env

if TYPE_CHECKING:
    from types import FrameType
    from typing import NoReturn
    from argparse import Namespace
    from collections.abc import Callable


class Main:
    """Class that implement argument parsing.

    :ivar args: list of positional parameters after processing options
    """

    def __init__(
        self,
        name: str | None = None,
        platform_args: bool = False,
        default_x86_64_on_windows: bool = False,
        argument_parser: ArgumentParser | None = None,
    ):
        """Initialize Main object.

        :param name: name of the program (if not specified the filename without
            extension is taken)
        :param platform_args: add --build, --host, --target support
        :param argument_parser: the ArgumentParser to use for parsing
            command-line arguments (if not specified, an ArgumentParser will be
            created by Main)
        :param default_x86_64_on_windows: set the default build platform to
            x86_64-windows64 on Windows.
        """
        # On UNIX set a signal handler for SIGTERM that will raise SystemExit
        # This is to let an e3 application enough time to perform
        # cleanup steps when killed by rlimit. rlimit first send a SIGTERM
        # then a SIGKILL 5 seconds later

        main = sys.modules["__main__"]

        if name is not None:
            self.name = name
        elif hasattr(main, "__file__"):
            assert main.__file__ is not None
            self.name = os.path.splitext(os.path.basename(main.__file__))[0]
        else:
            self.name = "unknown"

        if argument_parser is None:
            argument_parser = ArgumentParser(prog=self.name)

        e3.log.add_logging_argument_group(argument_parser, default_level=logging.INFO)

        if platform_args:
            plat_group = argument_parser.add_argument_group(title="platform arguments")

            plat_group.add_argument(
                "--build",
                default=None,  # to force autodetection
                help="Set the build platform and build os version",
            )
            plat_group.add_argument(
                "--host",
                default=None,  # to force autodetection
                help="Set the host platform, host os version",
                metavar="HOST[,HOST_VERSION]",
            )
            plat_group.add_argument(
                "--target",
                default=None,  # to force autodetection
                help="Set the target platform, target os version, "
                "target machine, and target mode",
                metavar="TARGET[,TARGET_VERSION[,TARGET_MACHINE[,TARGET_MODE]]]",
            )
            # We add a default to a fake option as a way to encode
            # the fact that this parser supports the standard
            # --build/host/target options. That way, after the parser
            # is used to evaluate the command-line arguments, we can
            # determine from the result whether the parser was supporting
            # the standard --host/target options or not, and then process
            # them if we did.
            #
            # To avoid clashes with user-defined options, we use a dest
            # name that is improbable in practice.
            argument_parser.set_defaults(e3_main_platform_args_supported=True)
            e = Env()
            # we set the default build platform for windows if activated by
            # the caller
            if e.build.os.name == "windows" and default_x86_64_on_windows:
                argument_parser.set_defaults(build="x86_64-windows64")

        self.args: Namespace | None = None
        self.argument_parser = argument_parser
        self.__log_handlers_set = False

        def sigterm_handler(sig: int, frame: FrameType | None) -> NoReturn:  # unix-only
            """Automatically convert SIGTERM to SystemExit exception.

            This is done to give enough time to an application killed by
            rlimit to perform the needed cleanup steps
            :param sig: signal action
            :param frame: the interrupted stack frame
            """
            del sig, frame
            logging.critical("SIGTERM received")
            raise SystemExit("SIGTERM received")

        if sys.platform != "win32":  # unix-only
            if threading.current_thread() is threading.main_thread():
                # Signal can only be used in the main thread
                signal.signal(signal.SIGTERM, sigterm_handler)

    def parse_args(
        self,
        args: list[str] | None = None,
        known_args_only: bool = False,
        pre_platform_args_callback: Callable[[Namespace], None] | None = None,
    ) -> None:
        """Parse options and set console logger.

        :param args: the list of positional parameters. If None then
            ``sys.argv[1:]`` is used
        :param known_args_only: does not produce an error when extra
            arguments are present
        :param pre_platform_args_callback: function called after argument parsing
            but before applying the --build, --host and --target to env. The callback
            maybe use to adjust for example the default platform.
        """
        if known_args_only:
            self.args, _ = self.argument_parser.parse_known_args(args)
        else:
            self.args = self.argument_parser.parse_args(args)

        if not self.__log_handlers_set:
            e3.log.activate_with_args(self.args, logging.INFO)
            self.__log_handlers_set = True

        # Export options to env
        e = Env()
        e.main_options = self.args

        # Call adjust_env_callback before applying --build, --host and --target
        if pre_platform_args_callback is not None:
            pre_platform_args_callback(self.args)

        if hasattr(self.args, "e3_main_platform_args_supported"):
            e3.log.debug("parsing --build/--host/--target")
            # Handle --build, --host, and --target arguments
            e.set_env(self.args.build, self.args.host, self.args.target)
