from __future__ import absolute_import

import abc
import argparse
import logging
import logging.handlers

from datetime import datetime as dt

from pkg_resources import get_distribution

from e3.anod.error import AnodError
from e3.anod.fingerprint import Fingerprint
from e3.anod.status import ReturnValue
from e3.env import Env
from e3.fs import mkdir, rm

import e3.error
import e3.log
import e3.os.process

import os
import stevedore
import sys
import yaml
from yaml.reader import ReaderError

from e3.hash import sha1
from e3.main import Main
from e3.os.fs import chmod
from e3.vcs.git import GitRepository


logger = e3.log.getLogger('sandbox')


class SandBoxError(e3.error.E3Error):
    pass


class SandBox(object):

    def __init__(self):
        self.__root_dir = None
        self.build_id = None
        self.build_date = None
        self.build_version = None

        # Required directories for a sandbox
        self.dirs = ('meta', 'bin', 'tmp', os.path.join('tmp', 'cache'),
                     'src', 'log', 'etc', 'vcs', 'patch')

        self.spec_dir = None
        self.meta_dir = None
        self.tmp_dir = None
        self.tmp_cache_dir = None
        self.src_dir = None
        self.log_dir = None
        self.etc_dir = None
        self.vcs_dir = None
        self.patch_dir = None
        self.bin_dir = None
        self.conf = None

    @property
    def root_dir(self):
        """Root path of the sandbox.

        :raise SandBoxError: when the sandbox is not initialized
        :rtype: str
        """
        if self.__root_dir is None:
            raise SandBoxError(
                origin='root_dir',
                message='sandbox not loaded. Please call load()')
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

    def dump_configuration(self):
        # Compute command line for call to e3-sandbox create. Ensure that the
        # paths are made absolute (path to sandbox, script).
        cmd_line = [sys.executable, os.path.abspath(__file__)]
        cmd_line += sys.argv[1:]
        sandbox_conf = os.path.join(self.meta_dir, "sandbox.yaml")
        with open(sandbox_conf, 'wb') as f:
            yaml.dump({'cmd_line': cmd_line}, f)

    def get_configuration(self):
        sandbox_conf = os.path.join(self.meta_dir, "sandbox.yaml")
        with open(sandbox_conf, 'rb') as f:
            return yaml.load(f)

    def write_scripts(self):
        from setuptools.command.easy_install import get_script_args
        import pkg_resources

        # Retrieve sandbox_scripts entry points
        for ep in pkg_resources.iter_entry_points(group='sandbox_scripts'):
            print ep

        e3_distrib = get_distribution('e3-core')

        class SandboxDist(object):
            def get_entry_map(self, group):
                if group != 'console_scripts':
                    return {}
                return e3_distrib.get_entry_map('sandbox_scripts')

            def as_requirement(self):
                return e3_distrib.as_requirement()

        for script in get_script_args(dist=SandboxDist()):
            script_name = script[0]
            script_content = script[1]
            target = os.path.join(self.bin_dir, script_name)
            rm(target)
            if not script_name.endswith('.exe'):
                script_content = script_content.replace(
                    'console_scripts', 'sandbox_scripts')
            with open(target, 'wb') as f:
                f.write(script_content)
            chmod('a+x', target)


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
            mkdir(getattr(self, '%s_dir' % d), quiet=quiet)

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

    def update_status(self, kind, status=ReturnValue.failure,
                      fingerprint=None):
        """Update meta information on disk.

        :param kind: the primitive name
        :type kind: str
        :param status: the last action return code
        :type status: ReturnValue
        :param fingerprint: the anod fingerprint
        :type fingerprint: Fingerprint
        """
        if fingerprint is None:
            fingerprint = Fingerprint()
        self.save_fingerprint(kind, fingerprint)
        self.save_last_status(kind, status)

        if kind == 'build':
            self.update_status('install', status, fingerprint)

    def load_fingerprint(self, kind, sha1_only=False):
        """Load the content of the fingerprint from disc.

        :param kind: the primitive name
        :type kind: str
        :param sha1_only: if true returns only the checksum of the
            fingerprint file
        :type sha1_only: bool

        :return: if sha1_only is True, returns a sha1 hexdigest else returns
            a Fingerprint object (the content of the fingerprint file or an
            empty Fingerprint when the fingerprint is invalid or does not
            exist)
        :rtype: str | Fingerprint
        """
        fingerprint_file = os.path.join(
            self.meta_dir, kind + '_fingerprint.yaml')
        if sha1_only:
            return sha1(fingerprint_file)

        result = None
        if os.path.exists(fingerprint_file):
            with open(fingerprint_file) as f:
                try:
                    result = yaml.load(f)
                except ReaderError as e:
                    logger.warning(e)
                    # Invalid fingerprint
                    logger.warning('invalid fingerprint, discard it')
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
        fingerprint_file = os.path.join(
            self.meta_dir, kind + '_fingerprint.yaml')
        with open(fingerprint_file, 'wb') as f:
            yaml.dump(fingerprint, f)

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
        return ReturnValue.missing

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
                            print line.rstrip()
                        print log_file.read()

                try:
                    from threading import Thread, Event
                except ImportError:
                    Thread = None
                    Event = None

                if Event is not None and Thread is not None:
                    self.stop_event = Event()
                    self.tail_thread = Thread(target=follow, args=(
                        self.stop_event, self.log_file,))
                    self.tail_thread.start()
                else:
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
        raise AnodError('%s failed with %s\n(see %s)' % (
            msg if '.anod' in msg else spec_name,
            sys.exc_value, tb_filename)), None, sys.exc_traceback


class SandBoxAction(object):

    __metaclass__ = abc.ABCMeta

    def __init__(self, subparsers):
        self.parser = subparsers.add_parser(
            self.name,
            help=self.help)
        self.parser.set_defaults(action=self.name)
        self.add_parsers()
        self.parser.add_argument('sandbox',
                                 help='path to the sandbox root directory')

    @abc.abstractproperty
    def name(self):
        """Return the action name.

        :rtype: str
        """
        pass

    @abc.abstractproperty
    def help(self):
        """Return the help string associated with this action.

        :rtype: str
        """
        pass

    @abc.abstractmethod
    def add_parsers(self):
        """Add new command line argument parsers."""
        pass

    @abc.abstractmethod
    def run(self, args):
        """Run the action.

        :param args: command line arguments gotten with argparse.
        """
        pass


class SandBoxCreate(SandBoxAction):

    name = 'create'
    help = 'Create a new sandbox'

    def add_parsers(self):
        self.parser.add_argument(
            '--spec-git-url',
            help='URL to retrieve Anod specification files, hosted in a git'
                 ' repository')
        self.parser.add_argument(
            '--spec-git-branch',
            default='master',
            help='Name of the branch to checkout to get the Anod '
                 'specification files from the repository defined by '
                 '``--spec-git-url``')

    def run(self, args):
        sandbox = SandBox()
        sandbox.root_dir = args.sandbox

        sandbox.create_dirs()

        if args.spec_git_url:
            mkdir(sandbox.spec_dir)
            g = GitRepository(sandbox.spec_dir)
            if e3.log.default_output_stream is not None:
                g.log_stream = e3.log.default_output_stream
            g.init()
            g.update(args.spec_git_url, args.spec_git_branch, force=True)

        sandbox.dump_configuration()
        sandbox.write_scripts()


class SandBoxShowConfiguration(SandBoxAction):

    name = 'show-config'
    help = 'Display sandbox configuration'

    # List of configuration key to show
    keys = ('spec_git_url', 'spec_git_branch', 'sandbox')

    def add_parsers(self):
        pass

    def run(self, args):
        sandbox = SandBox()
        sandbox.root_dir = args.sandbox

        cmd_line = sandbox.get_configuration()['cmd_line']

        args_namespace = argparse.Namespace()
        args_namespace.python = cmd_line[0]
        argument_parser = main(get_argument_parser=True)

        def error(message):
            raise SandBoxError(message)

        argument_parser.error = error
        try:
            args = argument_parser.parse_args(cmd_line[2:])
        except SandBoxError as msg:
            print 'the configuration is invalid, the argument parser got the' \
                  'following error:'
            print msg
        for k, v in vars(args).iteritems():
            if k in self.keys:
                print '%s = %s' % (k, v)


def main(get_argument_parser=False):
    """Manipulate an Anod sandbox.

    This function creates the main code for the entry-point e3-sandbox. To
    create new actions it is possible to create new sandbox plugins. e.g. to
    add a new plugin ``foo`` from a package ``e3-contrib``, derives the
    class :class:`SandBoxAction` and register the extension by adding in
    :file:`e3-contrib/setup.py`::

        entry_points={
            'e3.anod.sandbox.sandbox_action': [
                'foo = e3_contrib.sandbox_actions.SandBoxFoo']
        }

    :param get_argument_parser: return e3.main.Main argument_parser instead
        of running the action.
    :type get_argument_parser: bool
    """
    m = Main()
    subparsers = m.argument_parser.add_subparsers(
        title="action", description="valid actions")

    # Load all sandbox actions plugins
    ext = stevedore.ExtensionManager(
        namespace='e3.anod.sandbox.sandbox_action',
        invoke_on_load=True,
        invoke_args=(subparsers, ))

    if get_argument_parser:
        return m.argument_parser

    m.parse_args()

    e3.log.debug('sandbox action plugins loaded: %s',
                 ','.join(ext.names()))

    # An action has been selected, run it
    ext[m.args.action].obj.run(m.args)
