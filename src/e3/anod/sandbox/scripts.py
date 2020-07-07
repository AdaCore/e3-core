from __future__ import annotations

from e3.anod.error import AnodError
from e3.main import Main


def anod_cmdline(subparsers, action_name, action_help):
    parser = subparsers.add_parser(action_name, help=action_help)
    parser.set_defaults(action_name=action_name)
    parser.add_argument("spec", metavar="SPEC", help="The specification file name")
    parser.add_argument("--qualifier")


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

    sandbox_dir = os.path.abspath(
        os.path.join(os.path.dirname(sys.modules["__main__"].__file__), os.pardir)
    )

    sandbox = e3.anod.sandbox.SandBox(root_dir=sandbox_dir)

    # Load the local specs
    spec_repo = e3.anod.loader.AnodSpecRepository(sandbox.specs_dir)

    # Load the cache
    cache = e3.store.cache.load_cache(
        "file-cache", {"cache_dir": sandbox.tmp_cache_dir}
    )

    store = e3.store.load_store("http-simple-store", {}, cache)

    m = Main()
    subparsers = m.argument_parser.add_subparsers()
    anod_cmdline(subparsers, "download", "download a binary package")
    m.parse_args()

    action = m.args.action_name
    spec = m.args.spec
    qualifier = m.args.qualifier

    anod_cls = spec_repo.load(name=spec)
    anod_instance = anod_cls(
        qualifier=qualifier, kind=action, jobs=1, env=e3.env.BaseEnv.from_env()
    )

    # ??? inject the sandbox
    anod_instance.sandbox = sandbox

    driver = e3.anod.driver.AnodDriver(anod_instance=anod_instance, store=store)

    try:
        driver.activate(sandbox, spec_repo)
        driver.call(action)
    except AnodError as err:
        print(err, file=sys.stderr)
        sys.exit(1)
