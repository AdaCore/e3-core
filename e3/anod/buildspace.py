from __future__ import absolute_import, division, print_function

import logging
import logging.handlers
import os
import sys
from datetime import datetime as dt

import e3.error
import e3.log
import e3.os.process
from e3.anod.error import AnodError
from e3.anod.status import ReturnValue
from e3.fingerprint import Fingerprint
from e3.fs import mkdir, rm

logger = e3.log.getLogger('buildspace')


class BuildSpace(object):
    """Build space located inside a sandbox."""

    def __init__(self, root_dir, primitive):
        """Initialise a build space.

        :param root_dir: build space root dir
        :type root_dir: str
        :param primitive: the primitive name (e.g. build, install). This is
          used to create the log file
        :type primitive: str
        """
        self.root_dir = os.path.abspath(root_dir)
        self.dirs = ('meta', 'install', 'tmp', 'src', 'binary',
                     'build', 'test', 'pkg', 'log', 'results')

        self.meta_dir = self.get_subdir('meta')
        self.install_dir = self.get_subdir('install')
        self.tmp_dir = self.get_subdir('tmp')
        self.src_dir = self.get_subdir('src')
        self.binary_dir = self.get_subdir('binary')
        self.build_dir = self.get_subdir('build')
        self.test_dir = self.get_subdir('test')
        self.pkg_dir = self.get_subdir('pkg')
        self.log_dir = self.get_subdir('log')
        self.results_dir = self.get_subdir('results')

        # Initialize attributes that are keeping track of the logger handlers
        self.main_log_handler = None
        self.primitive_name = primitive
        self.log_file = None
        self.log_stream = None
        self.tail_thread = None

        # Initialize a few other attributes
        self.source_list_file = os.path.join(self.meta_dir,
                                             '%s_source_list.yaml')
        self.config = {}

        # Flag used to communicate with the tail thread in verbose mode
        self.stop_event = None

    def get_subdir(self, name):
        """Get path to the subdirectory named ``name``.

        :param name: name of the subdirectory
        :type name: str
        :raise: ValueError when the subdirectory is not in self.dirs
        """
        if name not in self.dirs:
            raise ValueError('%s not in self.dirs' % name)
        return os.path.join(self.root_dir, name)

    def create(self, quiet=False):
        """Create a build space.

        The function create all the necessary directories and files to have
        a valid empty build space

        :param quiet: do not print info messages
        :type quiet: bool
        """
        # Always clean the temp directory
        rm(self.get_subdir(name='tmp'), recursive=True)
        for d in self.dirs:
            mkdir(self.get_subdir(name=d), quiet=quiet)

    def reset(self, keep=None):
        """Reset build space.

        The function delete the complete buildspace. The only elements that
        are not deleted are the logs and the testsuite results.

        A call to self.create() is needed after calling this function.

        :param keep: a list of directory to keep in addition
            to results and log
        :type keep: list[str] | None
        """
        keep = set(keep) if keep is not None else set()
        keep.update(('results', 'log'))
        for d in (d for d in self.dirs if d not in keep):
            rm(self.get_subdir(name=d), True)

    def fingerprint_filename(self, kind):
        """Return the absolute path to the fingerprint of the given primitive.

        :param kind: the primitive name
        :type kind: str
        :rtype: str
        """
        return os.path.join(self.meta_dir, kind + '_fingerprint.json')

    def update_status(self, kind, status=ReturnValue.failure,
                      fingerprint=None):
        """Update meta information on disk.

        :param kind: the primitive name
        :type kind: str
        :param status: the last action return code
        :type status: ReturnValue
        :param fingerprint: the fingerprint
        :type fingerprint: Fingerprint
        """
        if fingerprint is None:
            fingerprint = Fingerprint()
        self.save_fingerprint(kind, fingerprint)
        self.save_last_status(kind, status)

        if kind == 'build':
            self.update_status('install', status, fingerprint)

    def load_fingerprint(self, kind):
        """Load the content of the fingerprint from disc.

        :param kind: the primitive name
        :type kind: str

        :return: Returns a Fingerprint object (the content of the fingerprint
            file or an empty Fingerprint when the fingerprint is invalid
            or does not exist).
        :rtype: Fingerprint
        """
        fingerprint_file = self.fingerprint_filename(kind)
        result = None
        if os.path.exists(fingerprint_file):
            try:
                result = Fingerprint.load_from_file(fingerprint_file)
            except Exception as e:
                logger.warning(e)
                # Invalid fingerprint
                logger.warning('invalid fingerprint, discarding it')
                result = None

        if not isinstance(result, Fingerprint):
            # The fingerprint file did not exist or was invalid
            # returns an empty fingerprint
            result = Fingerprint()
        return result

    def save_fingerprint(self, kind, fingerprint):
        """Save a fingerprint object to disk.

        :param kind: the primitive name
        :type kind: str
        :param fingerprint: the fingerprint object to save
        :type fingerprint: Fingerprint
        """
        fingerprint.save_to_file(self.fingerprint_filename(kind))

    def get_last_status(self, kind):
        """Return the last status for a primitive.

        :param kind: the primitive name
        :type kind: str

        :return: a tuple contanining: the last status (and ReturnValue.missing
            if nothing found), and the last modification time or None if
            missing.
        :rtype: (ReturnValue, datetime | None)
        """
        status_file = os.path.join(
            self.meta_dir, kind + '_last_status')
        if os.path.exists(status_file):
            with open(status_file) as f:
                status_name = f.read().strip()
                return ReturnValue[status_name], dt.fromtimestamp(
                    os.path.getmtime(status_file))
        return ReturnValue.missing, None

    def save_last_status(self, kind, status):
        """Save last status.

        :param kind: the primitive name
        :type kind: str
        :param status: the last status
        :type status: ReturnValue
        """
        status_file = os.path.join(
            self.meta_dir, kind + '_last_status')
        with open(status_file, 'wb') as f:
            if isinstance(status.name, unicode):  # py3-only
                f.write(status.name.encode('utf-8'))
            else:
                f.write(status.name)
        return None

    def set_logging(self, stdout_logs=False, info_msg=False):
        """Set logging if needed and add new primitive marker.

        :param stdout_logs: whether the log content should be displayed live
            on the console (but still written in the build space)
        :type stdout_logs: bool
        :param info_msg: do not print info messages
        :type info_msg: bool
        """
        if self.main_log_handler is None:

            self.log_file = os.path.join(self.log_dir,
                                         '{}.log'.format(
                                             self.primitive_name))
            self.main_log_handler = logging.handlers.RotatingFileHandler(
                self.log_file, backupCount=5)
            # force a rollover
            self.main_log_handler.doRollover()
            self.log_stream = self.main_log_handler.stream
            if stdout_logs:
                # Remove all handlers
                logging.getLogger('').handlers = []

                def follow(stop, log_filename):
                    import time
                    with open(log_filename) as log_file:
                        while not stop.isSet():
                            line = log_file.readline()
                            if not line:
                                time.sleep(0.1)
                                continue
                            print(line.rstrip())
                        print(log_file.read())

                try:
                    from threading import Thread, Event
                except ImportError:  # defensive code
                    Thread = None
                    Event = None

                if Event is not None and Thread is not None:
                    self.stop_event = Event()
                    self.tail_thread = Thread(target=follow, args=(
                        self.stop_event, self.log_file,))
                    self.tail_thread.start()
                else:  # defensive code
                    if not info_msg:
                        print('-v not supported on this machine')
                        print('output redirected to %s' % self.log_file)
            elif not info_msg:
                self.main_log_handler.setLevel(logging.DEBUG)
                self.main_log_handler.setFormatter(
                    logging.Formatter(
                        '[%(levelname)s %(asctime)s %(name)-24s] %(message)s',
                        datefmt='%H:%M:%S'))
                logging.getLogger('').addHandler(self.main_log_handler)
                logging.debug(
                    'Running %s', e3.os.process.command_line_image(sys.argv))
                logging.debug(
                    'anod primitive: %s (%s)',
                    self.primitive_name, os.getpid())

    def __del__(self):
        """Call self.end() if not already done."""
        self.end()

    def end(self):
        """Kill the tail thread if running."""
        if self.main_log_handler is not None:
            logging.getLogger('').removeHandler(
                self.main_log_handler)
            self.main_log_handler.close()
            self.main_log_handler = None
        if self.stop_event is not None:
            self.stop_event.set()
            self.tail_thread.join()
            self.stop_event = None
            print('output redirected to %s' % self.log_file)

    def dump_traceback(self, spec_name, kind):
        """Dump traceback in log dir and raise an AnodError with the last line.

        Traceback info is collected using the information returned by
        sys.exc_info().

        :param spec_name: name of the anod spec
        :type spec_name: str
        :param kind: anod action ('build', 'test', 'install', ...)
        :type kind: str
        :raise: AnodError
        """
        import traceback
        tb_filename = os.path.join(
            self.log_dir, 'traceback_%s' % kind)
        _, _, exc_traceback = sys.exc_info()
        with open(tb_filename, 'w') as f_tb:
            for l in traceback.format_tb(exc_traceback):
                f_tb.write(l + '\n')
        msg = traceback.format_tb(exc_traceback)[-1]
        raise AnodError('%s failed with %s\n(see %s)' % (
            msg if '.anod' in msg else spec_name,
            sys.exc_value, tb_filename)), None, sys.exc_traceback
