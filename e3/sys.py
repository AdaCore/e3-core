from __future__ import absolute_import
from __future__ import print_function

import ast
from enum import Enum
import os
import re
import sys


class RewriteNodeError(Exception):
    pass


class RewriteImportRule(object):
    """Rewrite Import node from AST.

    Skip or reject names imported by::

        from <module> import <names>

    or directly::

        import <module>
    """

    class RuleAction(Enum):
        reject = 0
        skip = 1

    def __init__(self, module, name='.*', action=None):
        """Initialize the object.

        :param module: regexp suitable for re.match() to match against the
            module name (note that the string is automatically surrounded by
            ^ and $)
        :type module: str
        :param name: regexp suitable for re.match() to match against the names
            imported via "from <module> import <names>" (note that the
            string is automatically surrounded by ^ and $)
        :type name: str
        :param action: skip (default) to avoid importing the name, or reject
            to raise a RewriteNodeError
        :type action: RewriteImportRule.RuleAction
        :raise: RewriteNodeError
        """
        self.module = module
        self.name = name
        self.action = action if action is not None else self.RuleAction.skip

    def rewrite_node(self, node):
        """Rewrite a node.

        :param node: ast node
        :return: a modified ast node
        """
        check_in_names = None

        if isinstance(node, ast.ImportFrom):

            # node: ImportFrom(module, names)
            # first check whether the module match our rule

            if re.match('^' + self.module + '$', node.module):

                # then we need to check whether our 'name' is in the
                # 'from' list (node.names)

                check_in_names = self.name

        elif isinstance(node, ast.Import):

            # node: Import(names)
            # We need to check whether our 'module' appears in the imported
            # module names

            check_in_names = self.module

        if check_in_names is not None:
            new_names = []
            for idx, var in enumerate(node.names):
                if re.match('^' + check_in_names + '$', var.name):
                    if self.action == self.RuleAction.skip:
                        # don't import this name
                        pass
                    elif self.action == self.RuleAction.reject:
                        raise RewriteNodeError(
                            'Rejected import found in ast: %s' % ast.dump(
                                node))
                    else:
                        raise ValueError('unknown action %s', self.action)
                else:
                    new_names.append(var)
            node.names = new_names
        return node


class RewriteImportNodeTransformer(ast.NodeTransformer):
    """Walk the AST applying a set of rules.

    Currently only the RewriteImportRule are supported.
    """

    def __init__(self, rules):
        """Load a set of rules.

        :param rules: list of rule objects
        :type rules: list[RewriteImportRule]
        """
        self.rules = rules

    def visit_ImportFrom(self, node):
        for rule in self.rules:
            node = rule.rewrite_node(node)
        return node

    def visit_Import(self, node):
        for rule in self.rules:
            node = rule.rewrite_node(node)
        return node


def version():
    import pkg_resources
    return pkg_resources.get_distribution('e3-core').version


def sanity_check():
    """Sanity check the E3 install."""
    errors = 0
    print('YAMLCheck:', end=' ')
    try:
        import yaml
        yaml.dump({'Yaml': 'works'})
        print('PASSED')
    except Exception:  # defensive code
        print('FAILED')
        errors += 1

    print('HashlibCheck:', end=' ')
    try:
        from e3.hash import sha1, md5
        sha1(__file__)
        md5(__file__)
        print('PASSED')
    except Exception:  # defensive code
        print('FAILED')
        errors += 1

    print('Version:', end=' ')
    try:
        print(version())
    except Exception:  # defensive code
        errors += 1
    return errors


def main():
    from e3.env import Env
    import e3.main
    m = e3.main.Main(platform_args=True)
    m.argument_parser.add_argument(
        '--platform-info',
        choices={'build', 'host', 'target'},
        help='Show build/host/target platform info')
    m.argument_parser.add_argument(
        '--version',
        help='Show E3 version',
        action='store_true')
    m.argument_parser.add_argument(
        '--check',
        help='Run e3 sanity checking',
        action='store_true')
    m.parse_args()

    if m.args.version:
        print(version())
        return
    elif m.args.check:
        errors = sanity_check()
        if errors:  # defensive code
            sys.exit('sanity checking failed!')
        else:
            print('Everything OK!')
            return
    elif m.args.platform_info:
        print(getattr(Env(), m.args.platform_info))


def set_python_env(prefix):
    """Set environment for a Python distribution.

    :param prefix: root directory of the python distribution
    :type prefix: str
    """
    import e3.env
    env = e3.env.Env()
    if sys.platform == 'win32':  # unix: no cover
        env.add_path(prefix)
        env.add_path(os.path.join(prefix, 'Scripts'))
    else:
        env.add_path(os.path.join(prefix, 'bin'))
        env.add_dll_path(os.path.join(prefix, 'lib'))


def interpreter(prefix=None):
    """Return location of the Python interpreter.

    :param prefix: root directory of the python distribution. if None location
        of the current interpreter is returned
    :type prefix: None | str
    :return: python executable path
    :rtype: str
    """
    if prefix is None:
        return sys.executable
    if sys.platform == 'win32':  # unix: no cover
        return os.path.join(prefix, 'python.exe')
    else:
        return os.path.join(prefix, 'bin', 'python')


def python_script(name, prefix=None):
    """Return path to scripts contained in this Python distribution.

    :param name: the script name
    :type name: str
    :param prefix: root directory of the Python distribution. if None the
        distribution currently used by this script will be used
    :type prefix: None | str
    :return: a list that will be the prefix of your command line
    :rtype: list[str]
    """
    if prefix is None:
        if sys.platform == 'win32':  # unix: no cover
            prefix = os.path.dirname(sys.executable)
        else:
            prefix = os.path.dirname(os.path.dirname(sys.executable))

    if sys.platform == 'win32':  # unix: no cover
        script = os.path.join(prefix, 'Scripts', name)
        if script.endswith('exe') and os.path.isfile(script):
            return [script]
        elif os.path.isfile(script + '.exe'):
            return [script + '.exe']
        else:
            return [interpreter(prefix), script]
    else:
        return [interpreter(prefix), os.path.join(prefix, 'bin', name)]
