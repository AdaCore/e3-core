from __future__ import absolute_import, division, print_function

import abc
import argparse

import e3.log
from e3.anod.sandbox import SandBox, SandBoxError
from e3.anod.sandbox.main import main
from e3.fs import mkdir
from e3.vcs.git import GitRepository


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
            print('the configuration is invalid, the argument parser got the'
                  'following error:')
            print(msg)
        for k, v in vars(args).iteritems():
            if k in self.keys:
                print('%s = %s' % (k, v))
