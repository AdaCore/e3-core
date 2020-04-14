"""Extensions to the standard Python logging system."""

from __future__ import annotations

import logging
import re
import sys
import time
from typing import TYPE_CHECKING

from colorama import Fore, Style

from tqdm import tqdm

if TYPE_CHECKING:
    from typing import Any, IO, Optional, Iterator, TextIO, Union


# Define default format for StreamHandler and FileHandler
DEFAULT_STREAM_FMT = "%(levelname)-8s %(message)s"
DEFAULT_FILE_FMT = "%(asctime)s: %(name)-24s: %(levelname)-8s %(message)s"

# Default output stream (sys.stdout by default, or a file descriptor if
# activate() is called with a filename.
default_output_stream: Union[TextIO, IO[str]] = sys.stdout

# If sys.stdout is a terminal then enable "pretty" output for user
# This includes progress bars and colors
if sys.stdout.isatty():  # all: no cover (not used in production!)
    pretty_cli = True
else:
    pretty_cli = False

console_logs: Optional[str] = None


def progress_bar(it: Iterator, **kwargs: Any) -> tqdm:
    """Create a tqdm progress bar.

    :param it: an interator
    :param kwargs: see tqdm documentation
    :return: a tqdm progress bar iterator
    """
    if pretty_cli:  # all: no cover
        return tqdm(it, **kwargs)
    else:
        # When pretty cli is disabled return a progress bar that do nothing.
        # returning just the iterator will break calls to tqdm method
        # otherwise.
        return tqdm(it, disable=True, **kwargs)


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

        tqdm.write(msg)


def getLogger(name: Optional[str] = None, prefix: str = "e3") -> logging.Logger:
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
    return logger


def add_log_handlers(
    level: int,
    log_format: str,
    datefmt: Optional[str] = None,
    filename: Optional[str] = None,
    set_default_output: bool = True,
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
    handler: Union[TqdmHandler, logging.StreamHandler, logging.FileHandler]
    if filename is None:
        if pretty_cli:  # all: no cover
            handler = TqdmHandler()
        else:
            handler = logging.StreamHandler()
    else:
        handler = logging.FileHandler(filename)
        if set_default_output:
            default_output_stream = handler.stream

    fmt = logging.Formatter(log_format, datefmt)
    fmt.converter = time.gmtime  # type: ignore
    handler.setFormatter(fmt)

    handler.setLevel(level)
    logging.getLogger("").addHandler(handler)


def activate(
    stream_format: str = DEFAULT_STREAM_FMT,
    file_format: str = DEFAULT_FILE_FMT,
    datefmt: Optional[str] = None,
    level: int = logging.INFO,
    filename: str = None,
    e3_debug: bool = False,
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
    add_log_handlers(level=level, log_format=stream_format, datefmt=datefmt)

    # Log to a file if necessary
    if filename is not None:
        add_log_handlers(
            level=min(level, logging.DEBUG),
            log_format=file_format,
            datefmt=datefmt,
            filename=filename,
        )

    if e3_debug:
        getLogger("debug").setLevel(logging.DEBUG)


# Provide a logger than will provides full debug information when a program
# using e3.main.Main is called with -v -v

e3_debug_logger = getLogger("debug")
e3_debug_logger.setLevel(logging.CRITICAL + 1)

debug = e3_debug_logger.debug
