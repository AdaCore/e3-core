"""Extensions to the standard Python logging system."""
from __future__ import absolute_import
from __future__ import print_function

import logging
import types
import sys
import time

# Define a new log level for which level number is lower then DEBUG. This is
# used to log output from a spawned subprocess
RAW = 5

# Register the new level name
logging.addLevelName(RAW, 'RAW')

# Define default format for StreamHandler and FileHandler
DEFAULT_STREAM_FMT = '%(levelname)-8s %(message)s'
DEFAULT_FILE_FMT = '%(asctime)s: %(name)-24s: %(levelname)-8s %(message)s'

# Default output stream (sys.stdout by default, or a file descriptor if
# activate() is called with a filename.
default_output_stream = sys.stdout

# Pretty cli UI
pretty_cli = True


def no_progress_bar(it, **kwargs):
    del kwargs
    return it

if sys.platform != 'win32':
    try:
        from clint.textui.progress import bar as clint_progress_bar
    except ImportError:
        clint_progress_bar = no_progress_bar


def progress_bar(it, expected_size=None, **kwargs):
    if pretty_cli and expected_size != 0:
        return clint_progress_bar(it, expected_size=expected_size, **kwargs)
    else:
        return no_progress_bar(it, expected_size=expected_size, **kwargs)


class RawFilter(logging.Filter):
    """Filters out non RAW level records.

    Filter all records that have a level higher than RAW. This is
    to avoid duplicates in the final logs.
    """

    def __init__(self):
        """Initialize a RawFilter."""
        super(RawFilter, self).__init__()

    def filter(self, record):
        """Filter implementation (internal).

        :param record: a record to be filtered

        :return: 1 if we keep the record, 0 otherwise
        :rtype: int
        """
        return 1 if record.levelno <= RAW else 0


# Define handlers for our RAW format
class RawStreamHandler(logging.StreamHandler):
    """Logging system handler for 'raw' logging on streams."""

    def flush(self):
        """Flush the stream."""
        # In some cases instances of RawStreamHandler might share the same fd
        # as other StreamHandler. As we don't control the order in which these
        # objects will be finalized, we might try to flush an already closed
        # stream. That's why we protect the flush call with a try/except
        # statement
        try:
            self.stream.flush()
        except ValueError:
            return

    def emit(self, record):
        """Emit a record.

        If a formatter is specified, it is used to format the record.
        The record is then written to the stream with a trailing newline
        [N.B. this may be removed depending on feedback]. If exception
        information is present, it is formatted using
        traceback.print_exception and appended to the stream.

        :param record:
        :type record:
        """
        try:
            msg = self.format(record)
            if not hasattr(types, "UnicodeType"):  # if no unicode support...
                self.stream.write(str(msg))
            else:
                try:
                    self.stream.write(str(msg))
                except UnicodeError:
                    self.stream.write(str(msg.encode("UTF-8")))
            self.flush()
        except Exception:
            self.handleError(record)


__null_handler_set = set()


def getLogger(name=None, prefix='e3'):
    """Get a logger with a default handler doing nothing.

    Calling this function instead of logging.getLogger will avoid warnings
    such as::

        'No handler could be found for logger...'

    :param name: logger name, if not specified return the root logger
    :type name: str
    :param prefix: application prefix, will be prepended to the name
    :type prefix:  str
    :rtype: logging.Logger
    """
    class NullHandler(logging.Handler):
        """Handler doing nothing."""

        def emit(self, _):
            pass

    logger = logging.getLogger('%s.%s' % (prefix, name))

    if prefix not in __null_handler_set:
        # Make sure that the root logger has at least an handler attached to
        # it to avoid warnings.
        logging.getLogger(prefix).addHandler(NullHandler())
        __null_handler_set.add(prefix)
    return logger


def __add_handlers(level, fmt, filename=None):
    """Add handlers with support for 'RAW' logging.

    :param level: set the root logger level to the specified level
    :type level: int
    :param fmt: log formatter
    :type fmt: logging.Formatter
    :param filename: use of a FileHandler, using the specified filename,
        instead of a StreamHandler. Set default_output_stream to write in this
        file.
    :type filename: str
    """
    global default_output_stream
    if filename is None:
        handler = logging.StreamHandler()
    else:
        handler = logging.FileHandler(filename)
        default_output_stream = handler.stream

    fmt.converter = time.gmtime
    handler.setFormatter(fmt)

    if level <= RAW:
        handler.setLevel(logging.DEBUG)
        if filename is None:
            raw_handler = RawStreamHandler()
        else:
            raw_handler = RawStreamHandler(handler.stream)
        raw_handler.setLevel(RAW)
        raw_handler.addFilter(RawFilter())
        logging.getLogger('').addHandler(raw_handler)
    else:
        handler.setLevel(level)

    logging.getLogger('').addHandler(handler)


def activate(
        stream_format=DEFAULT_STREAM_FMT,
        file_format=DEFAULT_FILE_FMT,
        datefmt=None,
        level=logging.INFO,
        filename=None,
        e3_debug=False):
    """Activate default E3 logging.

    :param level: set the root logger level to the specified level
    :type level: int
    :param datefmt: date/time format for the log handler
    :type datefmt: str
    :param stream_format: format string for the stream handler
    :type stream_format: str
    :param file_format: format string for the file handler
    :type file_format: str
    :param filename: redirect logs to a file in addition to the StreamHandler
    :type filename: str
    :param e3_debug: activate full debug of the e3 library
    :type e3_debug: bool
    """
    # By default do not filter anything. What is effectively logged
    # will be defined by setting/unsetting handlers
    logging.getLogger('').setLevel(RAW)
    fmt = logging.Formatter(stream_format, datefmt)

    # Set logging handlers
    __add_handlers(level=level, fmt=fmt)

    # Log to a file if necessary
    if filename is not None:
        __add_handlers(
            level=min(level, RAW),
            fmt=logging.Formatter(file_format, datefmt),
            filename=filename)

    if e3_debug:
        getLogger('debug').setLevel(RAW)


# Provide a logger than will provides full debug information when a program
# using e3.main.Main is called with -v -v

e3_debug_logger = getLogger('debug')
e3_debug_logger.setLevel(logging.CRITICAL + 1)

debug = e3_debug_logger.debug
