"""Extensions to the standard Python logging system."""

from __future__ import annotations
from dataclasses import dataclass

import logging
import os
import re
import sys
import time
import json
from typing import TYPE_CHECKING, ClassVar

from colorama import Fore, Style
from tqdm import tqdm

from e3.config import ConfigSection

if TYPE_CHECKING:
    from typing import (
        Any,
        IO,
        Optional,
        Iterator,
        Sequence,
        TextIO,
        List,
        TypeVar,
        Tuple,
        Mapping,
    )
    from logging import _ExcInfoType
    from argparse import ArgumentParser, _ArgumentGroup, Namespace

    T = TypeVar("T")


@dataclass
class LogConfig(ConfigSection):
    title: ClassVar[str] = "log"

    pretty: bool = True
    stream_fmt: str = "%(levelname)-8s %(message)s"
    file_fmt: str = "%(asctime)s: %(name)-24s: %(levelname)-8s %(message)s"


log_config = LogConfig.load()


# Default output stream (sys.stdout by default, or a file descriptor if
# activate() is called with a filename.
default_output_stream: TextIO | IO[str] = sys.stdout

# If sys.stdout is a terminal then enable "pretty" output for user
# This includes progress bars and colors
if sys.stdout.isatty():  # all: no cover (not used in production!)
    pretty_cli = log_config.pretty
else:
    pretty_cli = False

console_logs: Optional[str] = None


class JSONFormatter(logging.Formatter):
    """Logging formatter for creating JSON logs.

    It will print some standard attributes defined in STD_ATTR
    plus application extra attributes defined in _extra_attr
    """

    # standard attributes that will always be printed
    STD_ATTR = ["asctime", "levelname", "name", "message", "module", "exc_text"]
    # custom attributes
    _extra_attr: List[str] = ["anod_uui"]

    def __init__(
        self,
        date_fmt: Optional[str] = None,
        context: Optional[Mapping[str, Any]] = None,
    ):
        """Initialize formatter with context.

        :param date_fmt: see logging module
        :param context: dict to add context information to log records
        """
        # We need to pass fmt and datefmt parameters for
        # asctime atribute to be created
        super(JSONFormatter, self).__init__(fmt="%(asctime)s", datefmt=date_fmt)

        if context is None:
            context = {}
        self.context = context

    def format(self, record: logging.LogRecord) -> str:
        """convert record into JSON."""
        # Parent's format is called in order to setup additional attributes
        super(JSONFormatter, self).format(record)

        json_record = {
            attr: getattr(record, attr, None)
            for attr in self.STD_ATTR + list(self._extra_attr)
        }
        # we add context information
        json_record.update(self.context)
        # we delete empty values
        json_record = {attr: val for attr, val in json_record.items() if val}

        return json.dumps(json_record)


class E3LoggerAdapter(logging.LoggerAdapter):
    """LoggerAdapter to add custom keywords."""

    def process(self, msg: Any, kwargs: Any) -> Tuple[Any, Any]:
        """Allow to handle extra parameter.

        It is called by super method log. It is overwritten here because
        the standard process method will get rid of extra attribute
        """
        return msg, kwargs

    def log(
        self, level: int, msg: Any, *args: Any, anod_uui: int = 0, **kwargs: Any
    ) -> None:
        """Integrate additional keywords using standard interface.

        :param level: see logging module
        :param args: see logging module
        :param anod_uui: Anod UUI
        :param kwargs: other parameter supported by std logger._log method
        """
        extra_attrs = {"anod_uui": anod_uui}
        extra = kwargs.setdefault("extra", {})
        # we use the standard 'extra' parameter to pass additional keywords
        extra.update(extra_attrs)
        super(E3LoggerAdapter, self).log(level, msg, *args, **kwargs)

    def info(self, msg: Any, *args: Any, anod_uui: int = 0, **kwargs: Any) -> None:
        """Wrap standard logger.info method.

        It allows adding extra keyword parameters
        """
        self.log(logging.INFO, msg, *args, anod_uui=anod_uui, **kwargs)

    def debug(self, msg: Any, *args: Any, anod_uui: int = 0, **kwargs: Any) -> None:
        """Wrap standard logger.debug method.

        It allows adding extra keyword parameters
        """
        self.log(logging.DEBUG, msg, *args, anod_uui=anod_uui, **kwargs)

    def warning(self, msg: Any, *args: Any, anod_uui: int = 0, **kwargs: Any) -> None:
        """Wrap standard logger.warning method.

        It allows adding extra keyword parameters
        """
        self.log(logging.WARNING, msg, *args, anod_uui=anod_uui, **kwargs)

    def error(self, msg: Any, *args: Any, anod_uui: int = 0, **kwargs: Any) -> None:
        """Wrap standard logger.error method.

        It allows adding extra keyword parameters
        """
        self.log(logging.ERROR, msg, *args, anod_uui=anod_uui, **kwargs)

    def critical(self, msg: Any, *args: Any, anod_uui: int = 0, **kwargs: Any) -> None:
        """Wrap of standard logger.critical method.

        It allows adding extra keyword parameters
        """
        self.log(logging.CRITICAL, msg, *args, anod_uui=anod_uui, **kwargs)

    def exception(
        self,
        msg: Any,
        *args: Any,
        exc_info: _ExcInfoType = True,
        anod_uui: int = 0,
        **kwargs: Any,
    ) -> None:
        """Wrap standard logger.exception method.

        It allows adding extra keyword parameters
        """
        self.log(
            logging.ERROR, msg, *args, exc_info=exc_info, anod_uui=anod_uui, **kwargs
        )


def progress_bar(it: Iterator[T] | Sequence[T], **kwargs: Any) -> Iterator[T]:
    """Create a tqdm progress bar.

    :param it: an interator
    :param kwargs: see tqdm documentation
    :return: a tqdm progress bar iterator
    """
    if pretty_cli:  # all: no cover
        return tqdm(it, file=sys.stderr, **kwargs)
    else:
        # When pretty cli is disabled return a progress bar that do nothing.
        # returning just the iterator will break calls to tqdm method
        # otherwise.
        return tqdm(it, disable=True, file=sys.stderr, **kwargs)


__null_handler_set = set()


class TqdmHandler(logging.StreamHandler):  # all: no cover
    """Logging handler when used when progress bars are enabled."""

    # Color the log status at the beginning of most log lines
    color_subst = (
        (re.compile(r"^(DEBUG)"), Fore.CYAN),
        (re.compile(r"^(INFO)"), Style.DIM),
        (re.compile(r"^(WARNING)"), Fore.YELLOW),
        (re.compile(r"^(ERROR)"), Fore.RED),
        (re.compile(r"^(CRITICAL)"), Fore.RED + Style.BRIGHT),
    )

    def __init__(self) -> None:
        logging.StreamHandler.__init__(self)

    def emit(self, record: logging.LogRecord) -> None:
        msg = self.format(record)

        # Handle logging on several lines: indent all lines after the first one
        # to be aligned with the first one.
        msg_first_line = msg.split("\n")[0]
        msg = msg.replace(
            "\n", "\n_" + " " * (len(msg_first_line) - len(record.message) - 1)
        )

        # Add color
        for reg, color in self.color_subst:
            msg = re.sub(reg, color + r"\1" + Fore.RESET + Style.RESET_ALL, msg)

        tqdm.write(msg, file=sys.stderr)


def getLogger(name: Optional[str] = None, prefix: str = "e3") -> E3LoggerAdapter:
    """Get a logger with a default handler doing nothing.

    Calling this function instead of logging.getLogger will avoid warnings
    such as::

        'No handler could be found for logger...'

    :param name: logger name, if not specified return the root logger
    :param prefix: application prefix, will be prepended to the name
    """

    class NullHandler(logging.Handler):
        """Handler doing nothing."""

        def emit(self, _: logging.LogRecord) -> None:
            pass

    logger = logging.getLogger(f"{prefix}.{name}")

    if prefix not in __null_handler_set:
        # Make sure that the root logger has at least an handler attached to
        # it to avoid warnings.
        logging.getLogger(prefix).addHandler(NullHandler())
        __null_handler_set.add(prefix)
    return E3LoggerAdapter(logger, {})


def add_log_handlers(
    level: int,
    log_format: str,
    datefmt: Optional[str] = None,
    filename: Optional[str] = None,
    set_default_output: bool = True,
    json_format: bool = False,
) -> None:
    """Add log handlers using GMT.

    :param level: set the root logger level to the specified level
    :param log_format: format stream for the log handler
    :param datefmt: date/time format for the log handler
    :param filename: use of a FileHandler, using the specified filename,
        instead of a StreamHandler. Set default_output_stream to write in this
        file.
    """
    global default_output_stream
    handler: TqdmHandler | logging.StreamHandler | logging.FileHandler
    fmt: logging.Formatter | JSONFormatter

    if filename is None:
        if pretty_cli:  # all: no cover
            handler = TqdmHandler()
        else:
            handler = logging.StreamHandler()
    else:
        handler = logging.FileHandler(filename)
        if set_default_output:
            default_output_stream = handler.stream

    if json_format:
        fmt = JSONFormatter(datefmt, {"context": console_logs})
    else:
        fmt = logging.Formatter(log_format, datefmt)

    fmt.converter = time.gmtime  # type: ignore
    handler.setFormatter(fmt)

    handler.setLevel(level)
    logging.getLogger("").addHandler(handler)


def add_logging_argument_group(
    argument_parser: ArgumentParser, default_level: int = logging.WARNING,
) -> _ArgumentGroup:
    """Add an argument group with logging options to the argument parser.

    To be used with `e3.log.activate_with_args`.

    :param argument_parser: the parser in which the group will be created
    :param default_level: the logging level that will be used by default
    """
    log_group = argument_parser.add_argument_group(title="logging arguments")
    log_group.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="make the log output to the console more verbose",
    )
    log_group.add_argument(
        "--log-file",
        metavar="FILE",
        default=None,
        help="store all the logs into the specified file",
    )
    log_group.add_argument(
        "--loglevel",
        default=default_level,
        help="set the console log level",
        choices={
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL,
        },
    )
    log_group.add_argument(
        "--nocolor",
        default=False,
        action="store_true",
        help="disable color and progress bars",
    )
    log_group.add_argument(
        "--json-logs",
        default="json-logs" in os.environ.get("E3_ENABLE_FEATURE", "").split(","),
        action="store_true",
        help="enable JSON formatted logs. They can be activated as well by"
        " setting the env var E3_ENABLE_FEATURE=json-logs.",
    )
    log_group.add_argument(
        "--console-logs",
        metavar="LINE_PREFIX",
        help="disable color, progress bars, and redirect as much as"
        " possible to stdout, starting lines with the given prefix.",
    )

    return log_group


def activate_with_args(args: Namespace, default_level: int = logging.WARNING) -> None:
    """Activate the e3 log using argument parsed.

    To be used with `e3.log.add_logging_argument_group`.

    :param args: the result of parsing arguments
    :param default_level: the logging level assumed by default
    """
    global console_logs
    global pretty_cli

    if args.verbose > 0:
        level = default_level - 10 * args.verbose
    else:
        level = args.loglevel

    if args.console_logs:
        console_logs = args.console_logs

    if args.nocolor:
        pretty_cli = False

    activate(
        level=level,
        filename=args.log_file,
        json_format=args.json_logs,
        e3_debug=level == logging.DEBUG,
    )


def activate(
    stream_format: str = log_config.stream_fmt,
    file_format: str = log_config.file_fmt,
    datefmt: Optional[str] = None,
    level: int = logging.INFO,
    filename: Optional[str] = None,
    e3_debug: bool = False,
    json_format: bool = False,
) -> None:
    """Activate default E3 logging.

    :param level: set the root logger level to the specified level
    :param datefmt: date/time format for the log handler
    :param stream_format: format string for the stream handler
    :param file_format: format string for the file handler
    :param filename: redirect logs to a file in addition to the StreamHandler
    :param e3_debug: activate full debug of the e3 library
    """
    # By default do not filter anything. What is effectively logged
    # will be defined by setting/unsetting handlers
    logging.getLogger("").setLevel(logging.DEBUG)
    if console_logs:
        stream_format = f"{console_logs}: {file_format}"

    # Set logging handlers
    add_log_handlers(
        level=level, log_format=stream_format, datefmt=datefmt, json_format=json_format
    )

    # Log to a file if necessary
    if filename is not None:
        add_log_handlers(
            level=min(level, logging.DEBUG),
            log_format=file_format,
            datefmt=datefmt,
            filename=filename,
            json_format=json_format,
        )

    if e3_debug:
        getLogger("debug").setLevel(logging.DEBUG)


# Provide a logger than will provides full debug information when a program
# using e3.main.Main is called with -v -v

e3_debug_logger = getLogger("debug")
e3_debug_logger.setLevel(logging.CRITICAL + 1)

debug = e3_debug_logger.debug
