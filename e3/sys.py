from __future__ import absolute_import

import os
import sys


def version():
    import pkg_resources
    return pkg_resources.get_distribution('e3-core').version


def sanity_check():
    """Sanity check the E3 install."""
    errors = 0
    sys.stdout.write('YAMLCheck: ')
    try:
        import yaml
        yaml.dump({'Yaml': 'works'})
        sys.stdout.write('PASSED\n')
    except Exception:
        sys.stdout.write('FAILED\n')
        errors += 1

    sys.stdout.write('HashlibCheck: ')
    try:
        from e3.hash import sha1, md5
        sha1(__file__)
        md5(__file__)
        sys.stdout.write('PASSED\n')
    except Exception:
        sys.stdout.write('FAILED\n')
        errors += 1

    try:
        revision = version()
        major, num, git_rev = revision.split('-')
        sys.stdout.write('MajorVersion: %s\n' % major)
        sys.stdout.write('ChangeNumber: %s\n' % num)
    except Exception:
        sys.stdout.write('MajorVersion: FAILED\n')
        sys.stdout.write('ChangeNumber: FAILED\n')
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
        print version()
        return
    elif m.args.check:
        errors = sanity_check()
        if errors:
            sys.exit('sanity checking failed!')
        else:
            print 'Everything OK!'
            return
    elif m.args.platform_info:
        print getattr(Env(), m.args.platform_info)


def set_python_env(prefix):
    """Set environment for a Python distribution.

    :param prefix: root directory of the python distribution
    :type prefix: str
    """
    import e3.env
    env = e3.env.Env()
    if sys.platform == 'win32':
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
    if sys.platform == 'win32':
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
        if sys.platform == 'win32':
            prefix = os.path.dirname(sys.executable)
        else:
            prefix = os.path.dirname(os.path.dirname(sys.executable))

    if sys.platform == 'win32':
        script = os.path.join(prefix, 'Scripts', name)
        if os.path.isfile(script + '.exe'):
            return [script + '.exe']
        else:
            return [interpreter(prefix), script]
    else:
        return [interpreter(prefix), os.path.join(prefix, 'bin', name)]
