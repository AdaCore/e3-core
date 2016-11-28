from __future__ import absolute_import, division, print_function

import e3.log
import stevedore
from e3.main import Main


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
