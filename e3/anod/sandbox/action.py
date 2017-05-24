from __future__ import absolute_import, division, print_function

import abc
import argparse
import os

import e3.log
from e3.anod.context import AnodContext
from e3.anod.loader import AnodSpecRepository
from e3.anod.sandbox import SandBox, SandBoxError
from e3.anod.sandbox.main import main
from e3.anod.spec import check_api_version
from e3.electrolyt.plan import Plan, PlanContext
from e3.electrolyt.run import ElectrolytJobFactory
from e3.env import BaseEnv
from e3.fs import mkdir
from e3.vcs.git import GitRepository

logger = e3.log.getLogger('e3.anod.SandBox')


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
            g = GitRepository(sandbox.specs_dir)
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


class SandBoxExec(SandBoxCreate):

    name = 'exec'
    help = 'Execute anod action in an sandbox'

    def add_parsers(self):
        super(SandBoxExec, self).add_parsers()
        self.parser.add_argument(
            '--spec-dir',
            help='Alternate spec directory to use')
        self.parser.add_argument(
            '--create-sandbox',
            action='store_true',
            help='Create the sandbox if needed')
        self.parser.add_argument(
            '--plan', metavar='FILE', help='Path to the plan')
        self.parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show action item without any execution')
        self.parser.add_argument(
            '--resolver',
            help='Use specific resolver')

    def run(self, args):
        sandbox = SandBox()
        sandbox.root_dir = args.sandbox

        if args.spec_dir:
            sandbox_spec_dir = args.spec_dir
        else:
            sandbox_spec_dir = os.path.join(
                sandbox.root_dir,
                'specs')

        if args.create_sandbox:
            sandbox.create_dirs()

        if args.create_sandbox and args.spec_git_url:
            mkdir(sandbox_spec_dir)
            g = GitRepository(sandbox_spec_dir)
            if e3.log.default_output_stream is not None:
                g.log_stream = e3.log.default_output_stream
            g.init()
            g.update(args.spec_git_url, args.spec_git_branch, force=True)

        sandbox.dump_configuration()
        sandbox.write_scripts()

        asr = AnodSpecRepository(sandbox_spec_dir)

        # asr.prolog_dict should now contain the API Version
        if asr.api_version is None:
            raise SandBoxError(
                'api_version should be set in prolog.py')

        check_api_version(asr.api_version)

        # Load plan content if needed
        if args.plan:
            if not os.path.isfile(args.plan):
                raise SandBoxError(
                    'plan file %s does not exist' % args.plan,
                    origin='SandBoxExec.run')
            with open(args.plan, 'r') as plan_fd:
                plan_content = ['def main_entry_point():']
                plan_content += ['    %s' % line
                                 for line in plan_fd.read().splitlines()]
                plan_content = "\n".join(plan_content)

            env = BaseEnv()
            cm = PlanContext(server=env)
            store = None
            resolver = getattr(
                AnodContext,
                str(args.resolver),
                AnodContext.always_create_source_resolver)
            logger.debug('Using resolver %s', resolver.__name__)

            # Declare available actions and their signature
            def anod_action(module,
                            build=None,
                            host=None,
                            target=None,
                            qualifier=None):
                pass

            for a in ('anod_install', 'anod_build', 'anod_test'):
                cm.register_action(a, anod_action)

            # Load the plan and execute
            plan = Plan(data={})
            plan.load_chunk(plan_content)
            actions = cm.execute(plan, 'main_entry_point')

            ac = AnodContext(asr, default_env=env)
            for action in actions:
                ac.add_anod_action(action.module,
                                   action,
                                   action.action.replace('anod_', '', 1),
                                   action.qualifier)

            # Check if machine plan is locally schedulable
            action_list = ac.schedule(resolver)
            e = ElectrolytJobFactory(sandbox, asr, store, dry_run=args.dry_run)
            e.run(action_list)
