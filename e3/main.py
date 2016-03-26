"""Main program initialization.

This package provides a class called Main used to initialize a python script
invoked from command line. The main goal is to ensure consistency in term of
interface, documentation and logging activities for all scripts using e3.

The script will support by default the following switches::

    -v|--verbose to enable verbose mode (a console logger is added)
    -h|--help    display command line help
    --log-file FILE
                 to redirect logs to a given file (this is independent from
                 verbose option

In addition, if the add_targets_options parameter is set to True
when instantiating an object of class Main, the following switches
will also be provided::

    --build      to set the build
    --host       to set the host
    --target     to set the target
"""
from __future__ import absolute_import
from __future__ import print_function
import logging
import os
import sys
import signal
import e3
import e3.log
from e3.env import Env


class Main(object):
    """Class that implement argument parsing.

    :ivar args: list of positional parameters after processing options
    """

    def __init__(self, name=None,
                 platform_args=False):
        """Initialize Main object.

        :param name: name of the program (if not specified the filename without
            extension is taken)
        :type name: str | None
        :param platform_args: add --build, --host, --target support
        :type platform_args: bool
        """
        # Set a signal handler for SIGTERM that will raise SystemExit
        # This is to let an e3 application enough time to perform
        # cleanup steps when killed by rlimit. rlimit first send a SIGTERM
        # then a SIGKILL 5 seconds later

        main = sys.modules['__main__']

        if name is not None:
            self.name = name
        else:
            self.name = os.path.splitext(os.path.basename(main.__file__))[0]

        from argparse import ArgumentParser
        argument_parser = ArgumentParser()

        log_group = argument_parser.add_argument_group(
            title='Logging arguments')
        log_group.add_argument(
            '-v', '--verbose',
            action='count',
            default=0,
            help='make the log outputted on the console more verbose (this '
                 'sets the log level to RAW)')
        log_group.add_argument(
            '--log-file',
            metavar='FILE',
            default=None,
            help='store all the logs into the specified file')
        log_group.add_argument(
            '--loglevel',
            default=logging.INFO,
            help='set the console log level',
            choices={
                'RAW': e3.log.RAW,
                'DEBUG': logging.DEBUG,
                'INFO': logging.INFO,
                'ERROR': logging.ERROR,
                'CRITICAL': logging.CRITICAL})

        if platform_args:
            plat_group = argument_parser.add_argument_group(
                title='Platform arguments')
            plat_group.add_argument(
                '--build',
                default='',  # to force autodetection
                help='Set the build platform and build os version')
            plat_group.add_argument(
                '--host',
                default='',  # to force autodetection
                help='Set the host platform, host os version',
                metavar='HOST[,HOST_VERSION]')
            plat_group.add_argument(
                '--target',
                default='',  # to force autodetection
                help='Set the target platform, target os version, '
                     'target machine, and target mode',
                metavar='TARGET[,TARGET_VERSION[,TARGET_MACHINE[,'
                        'TARGET_MODE]]]')
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

        self.args = None
        self.argument_parser = argument_parser
        self.__log_handlers_set = False

        def sigterm_handler(signal, frame):
            """Automatically convert SIGTERM to SystemExit exception.

            This is done to give enough time to an application killed by
            rlimit to perform the needed cleanup steps
            :param signal: signal action
            :param frame: the interrupted stack frame
            """
            del signal, frame
            logging.critical('SIGTERM received')
            raise SystemExit('SIGTERM received')

        signal.signal(signal.SIGTERM, sigterm_handler)

    def parse_args(self, args=None):
        """Parse options and set console logger.

        :param args: the list of positional parameters. If None then
            ``sys.argv[1:]`` is used
        :type: list[str] | None
        """
        # log_stream_format=e3.log.DEFAULT_STREAM_FMT,
        # log_file_format=e3.log.DEFAULT_FILE_FMT,
        # log_datefmt=None,
        # log_filename=None,
        self.args = self.argument_parser.parse_args(args)

        if not self.__log_handlers_set:
            # First set level of verbosity
            if self.args.verbose:
                level = e3.log.RAW
            else:
                level = self.args.loglevel

            e3.log.activate(level=level, filename=self.args.log_file,
                            e3_debug=self.args.verbose > 1)
            self.__log_handlers_set = True

        # Export options to env
        e = Env()
        e.main_options = self.args

        if hasattr(self.args, 'e3_main_platform_args_supported'):
            e3.log.debug('parsing --build/--host/--target')
            # Handle --build, --host, and --target arguments
            e.set_env(self.args.build,
                      self.args.host,
                      self.args.target)
