from __future__ import absolute_import

import logging
import logging.handlers

from e3.anod.error import AnodError
from e3.env import Env
from e3.fs import mkdir

import e3.error
import e3.os.process

import os
import sys


class SandBoxError(e3.error.E3Error):
    pass


class SandBox(object):

    def __init__(self):
        self.__root_dir = None
        self.config = {}
        self.build_id = None
        self.build_date = None
        self.build_version = None

        # Required directories for a sandbox
        self.dirs = ('meta', 'bin', 'tmp', os.path.join('tmp', 'cache'),
                     'src', 'log', 'etc', 'vcs', 'lib', 'patch')

        self.spec_dir = None
        self.meta_dir = None
        self.bin_dir = None
        self.tmp_dir = None
        self.tmp_cache_dir = None
        self.src_dir = None
        self.log_dir = None
        self.etc_dir = None
        self.vcs_dir = None
        self.lib_dir = None
        self.patch_dir = None
        self.conf = None

    @property
    def root_dir(self):
        """Root path of the sandbox.

        :raise SandBoxError: when the sandbox is not initialized
        :rtype: str
        """
        if self.__root_dir is None:
            raise SandBoxError('root_dir',
                               'Sandbox not loaded. Please call load()')
        return self.__root_dir

    @root_dir.setter
    def root_dir(self, d):
        new_dir = os.path.realpath(d)
        if new_dir == self.__root_dir:
            return  # nothing to do

        self.__root_dir = new_dir

        self.spec_dir = os.path.join(new_dir, 'specs')

        # For each directory create an attribute containing its path
        for d in self.dirs:
            setattr(self, ('%s_dir' % d).replace(os.path.sep, '_'),
                    os.path.join(self.root_dir, d))

    def create_dirs(self):
        """Create all required sandbox directories."""
        for d in self.dirs:
            mkdir(getattr(self, ('%s_dir' % d).replace(os.path.sep, '_')))

    def get_build_space(self, name, primitive, platform=None):
        """Get build space.

        :param name: build space name
        :type name: str
        :param primitive: the primitive name (e.g. build, install...)
        :type primitive: str
        :param platform: platform name (if None use the default platform)
        :type platform: str | None

        :return: A BuildSpace object
        :rtype: BuildSpace
        """
        if platform is None:
            platform = Env().platform
        return BuildSpace(
            root_dir=os.path.join(self.root_dir, platform, name),
            primitive=primitive)


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

        self.meta_dir = os.path.join(self.root_dir, 'meta')
        self.install_dir = os.path.join(self.root_dir, 'install')
        self.tmp_dir = os.path.join(self.root_dir, 'tmp')
        self.src_dir = os.path.join(self.root_dir, 'src')
        self.binary_dir = os.path.join(self.root_dir, 'binary')
        self.build_dir = os.path.join(self.root_dir, 'build')
        self.test_dir = os.path.join(self.root_dir, 'test')
        self.pkg_dir = os.path.join(self.root_dir, 'pkg')
        self.log_dir = os.path.join(self.root_dir, 'log')
        self.results_dir = os.path.join(self.root_dir, 'results')

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

    def create(self, quiet=False):
        """Create a build space.

        The function create all the necessary directories and files to have
        a valid empty build space

        :param quiet: do not print info messages
        :type quiet: bool
        """
        for d in self.dirs:
            mkdir(getattr(self, '%s_dir' % d))

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
            e3.fs.rm(os.path.join(self.root_dir, d), True)

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
                            print line.rstrip()
                        print log_file.read()

                try:
                    from threading import Thread, Event
                    self.stop_event = Event()
                    self.tail_thread = Thread(target=follow, args=(
                        self.stop_event, self.log_file,))
                    self.tail_thread.start()
                except ImportError:
                    if not info_msg:
                        print '-v not supported on this machine'
                        print 'output redirected to %s' % self.log_file
            elif not info_msg:
                self.main_log_handler.setLevel(logging.DEBUG)
                self.main_log_handler.setFormatter(
                    logging.Formatter(
                        '[%(levelname)s %(asctime)s %(name)-24s] %(message)s',
                        datefmt='%H:%M:%S'))
                logging.getLogger('').addHandler(self.main_log_handler)
                logging.debug('Running {}'.format(
                    e3.os.process.command_line_image(sys.argv)))
                logging.debug('anod primitive: {name} ({pid})'.format(
                    name=self.primitive_name,
                    pid=os.getpid()))

    def __del__(self):
        """Call self.end() if not already done."""
        self.end()

    def end(self):
        """Kill the tail thread if running."""
        if self.stop_event is not None:
            self.stop_event.set()
            self.tail_thread.join()
            self.stop_event = None
            print 'output redirected to %s' % self.log_file

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
        raise AnodError(
            '%s failed with %s\n(see %s)' % (
                msg if '.anod' in msg else spec_name,
                sys.exc_value, tb_filename)), None, sys.exc_traceback
