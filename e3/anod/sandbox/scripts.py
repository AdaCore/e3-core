from __future__ import absolute_import
from __future__ import print_function

from e3.anod.error import AnodError
from e3.main import Main


def anod_cmdline(subparsers, action_name, action_help):
    parser = subparsers.add_parser(action_name, help=action_help)
    parser.set_defaults(action_name=action_name)
    parser.add_argument('spec', metavar="SPEC",
                        help='The specification file name')
    parser.add_argument('--qualifier')


def anod():
    """bin/anod script entry point.

    This script is installed in the sandbox.
    """
    import os
    import sys

    import e3.anod.driver
    import e3.anod.loader
    import e3.anod.sandbox
    import e3.env
    import e3.store
    import e3.store.cache

    sandbox_dir = os.path.abspath(os.path.join(os.path.dirname(
        sys.modules['__main__'].__file__), os.pardir))

    sandbox = e3.anod.sandbox.SandBox()
    sandbox.root_dir = sandbox_dir

    # Configure the sandbox for other specs
    e3.anod.loader.sandbox = sandbox

    # Load the cache
    cache = e3.store.cache.load_cache(
        'file-cache',
        {'cache_dir': sandbox.tmp_cache_dir})

    store = e3.store.load_store(
        'http-simple-store', {}, cache)

    m = Main()
    subparsers = m.argument_parser.add_subparsers()
    anod_cmdline(subparsers, 'download', 'download a binary package')
    m.parse_args()

    action = m.args.action_name
    spec = m.args.spec
    qualifier = m.args.qualifier

    anod_cls = e3.anod.loader.spec(name=spec, from_sandbox=sandbox)
    driver = e3.anod.driver.AnodDriver(
        anod_instance=anod_cls(qualifier=qualifier,
                               kind=action,
                               jobs=1,
                               env=e3.env.BaseEnv.from_env()),
        store=store)

    try:
        driver.call(action)
    except AnodError as err:
        sys.exit(err)
