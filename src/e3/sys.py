from __future__ import annotations

import ast
import os
import re
import struct
import sys
from enum import Enum
from dataclasses import asdict
from pprint import pformat
from typing import TYPE_CHECKING

import e3.log

if TYPE_CHECKING:
    from typing import List, Optional

logger = e3.log.getLogger("e3.sys")


class RewriteNodeError(Exception):
    pass


class RewriteImportRule:
    """Rewrite Import node from AST.

    Skip or reject names imported by::

        from <module> import <names>

    or directly::

        import <module>
    """

    class RuleAction(Enum):
        reject = 0
        skip = 1

    def __init__(
        self, module: str, name: str = ".*", action: Optional[RuleAction] = None
    ):
        """Initialize the object.

        :param module: regexp suitable for re.match() to match against the
            module name (note that the string is automatically surrounded by
            ^ and $)
        :param name: regexp suitable for re.match() to match against the names
            imported via "from <module> import <names>" (note that the
            string is automatically surrounded by ^ and $)
        :param action: skip (default) to avoid importing the name, or reject
            to raise a RewriteNodeError
        :raise: RewriteNodeError
        """
        self.module = module
        self.name = name
        self.action = action if action is not None else self.RuleAction.skip

    def rewrite_node(self, node: ast.stmt) -> ast.stmt:
        """Rewrite a node.

        :param node: ast node
        :return: a modified ast node
        """
        check_in_names = None

        if isinstance(node, ast.ImportFrom):

            # node: ImportFrom(module, names)
            # first check whether the module match our rule

            if TYPE_CHECKING:
                assert node.module is not None
            if re.match("^" + self.module + "$", node.module):

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
            for _, var in enumerate(node.names):  # type: ignore
                if re.match("^" + check_in_names + "$", var.name):
                    if self.action == self.RuleAction.skip:
                        # don't import this name
                        pass
                    elif self.action == self.RuleAction.reject:
                        raise RewriteNodeError(
                            f"Rejected import found in ast: {ast.dump(node)}"
                        )
                    else:  # defensive code
                        raise ValueError("unknown action %s", self.action)
                else:
                    new_names.append(var)
            node.names = new_names  # type: ignore
        return node


class RewriteImportNodeTransformer(ast.NodeTransformer):
    """Walk the AST applying a set of rules.

    Currently only the RewriteImportRule are supported.
    """

    def __init__(self, rules: List[RewriteImportRule]):
        """Load a set of rules.

        :param rules: list of rule objects
        """
        self.rules = rules

    def visit_ImportFrom(self, node: ast.stmt) -> ast.stmt:
        for rule in self.rules:
            node = rule.rewrite_node(node)
        return node

    def visit_Import(self, node: ast.stmt) -> ast.stmt:
        for rule in self.rules:
            node = rule.rewrite_node(node)
        return node


def version() -> str:
    import pkg_resources

    return pkg_resources.get_distribution("e3-core").version


def sanity_check() -> int:
    """Sanity check the E3 install."""
    errors = 0
    print("YAMLCheck:", end=" ")
    try:
        import yaml

        yaml.safe_dump({"Yaml": "works"})
        print("PASSED")
    except Exception:  # defensive code
        print("FAILED")
        errors += 1

    print("HashlibCheck:", end=" ")
    try:
        from e3.hash import sha1, md5

        sha1(__file__)
        md5(__file__)
        print("PASSED")
    except Exception:  # defensive code
        print("FAILED")
        errors += 1

    print("Version:", end=" ")
    try:
        print(version())
    except Exception:  # defensive code
        errors += 1
    return errors


def main() -> None:
    from e3.env import Env
    import e3.main

    m = e3.main.Main(platform_args=True)
    m.argument_parser.add_argument(
        "--platform-info",
        choices={"build", "host", "target"},
        help="Show build/host/target platform info",
    )
    m.argument_parser.add_argument(
        "--version", help="Show E3 version", action="store_true"
    )
    m.argument_parser.add_argument(
        "--check", help="Run e3 sanity checking", action="store_true"
    )
    m.argument_parser.add_argument(
        "--show-config", action="store_true", help="Show e3 config"
    )
    m.parse_args()

    if TYPE_CHECKING:
        assert m.args is not None

    if m.args.version:
        print(version())
        return
    elif m.args.check:
        errors = sanity_check()
        if errors:  # defensive code
            logger.error("sanity checking failed!")
            sys.exit(1)
        else:
            print("Everything OK!")
            return
    elif m.args.platform_info:
        print(getattr(Env(), m.args.platform_info))

    if m.args.show_config:
        print("[log]")
        for k, v in asdict(e3.log.log_config).items():
            print("{}: {}".format(k, pformat(v)))


def set_python_env(prefix: str) -> None:
    """Set environment for a Python distribution.

    :param prefix: root directory of the python distribution
    """
    import e3.env

    env = e3.env.Env()
    if sys.platform == "win32":  # unix: no cover
        env.add_path(prefix)
        env.add_path(os.path.join(prefix, "Scripts"))
    else:
        env.add_path(os.path.join(prefix, "bin"))
        env.add_dll_path(os.path.join(prefix, "lib"))


def interpreter(prefix: Optional[str] = None) -> str:
    """Return location of the Python interpreter.

    When there are both a python3 and python binary file return the path to
    the python3 binary.

    :param prefix: root directory of the python distribution. if None location
        of the current interpreter is returned
    :return: python executable path
    """
    if prefix is None:
        return sys.executable
    if sys.platform == "win32":  # unix: no cover
        python3 = os.path.join(prefix, "python3.exe")
        if os.path.exists(python3):
            return python3
        else:
            # Might be the python location when in a venv
            python3 = os.path.join(prefix, "Scripts", "python.exe")
            if os.path.exists(python3):
                return python3
            else:
                return os.path.join(prefix, "python.exe")
    else:  # windows: no cover
        python3 = os.path.join(prefix, "bin", "python3")
        if os.path.exists(python3):
            return python3
        else:
            return os.path.join(prefix, "bin", "python")


def python_script(name: str, prefix: Optional[str] = None) -> List[str]:
    """Return path to scripts contained in this Python distribution.

    :param name: the script name
    :param prefix: root directory of the Python distribution. if None the
        distribution currently used by this script will be used
    :return: a list that will be the prefix of your command line
    """

    def has_relative_python_shebang(file_script: str) -> bool:  # unix: no cover
        """Return True if the script contains #!python shebang.

        When producing relocatable python distribution we change the shebang
        to #!python. In that case prefix the command line with the current
        python interpreter.

        #!/path/to/python shebang should return false, as we don't need to
        return interpreter path.
        """
        with open(file_script, "rb") as f:
            content = f.read()
        return re.search(b"#!python", content, flags=re.MULTILINE) is not None

    if prefix is None:
        if sys.platform == "win32":  # unix: no cover
            prefix = os.path.dirname(sys.executable)
        else:
            prefix = os.path.dirname(os.path.dirname(sys.executable))

    if sys.platform == "win32":  # unix: no cover
        # On Windows a script present in a distribution might be installed
        # using different mechanisms:
        #
        # 1- the python file itself in the Scripts subdirectory
        # 2- a .exe with the same basename as the original python script which
        #    which call a python script called <basename>-script.py
        # 3- a .exe without a side python script
        script = (
            os.path.join(prefix, name)
            if os.path.basename(prefix) == "scripts"
            else os.path.join(prefix, "Scripts", name)
        )

        if script.endswith(".exe"):
            script_exe = script
            script_py = script[:-4] + "-script.py"
        else:
            script_exe = script + ".exe"
            script_py = script + "-script.py"

        if os.path.isfile(script_py):
            # If we have a side <basename>-script.py always use it, instead of
            # the .exe
            return [interpreter(prefix), script_py]
        elif os.path.isfile(script_exe):
            # A .exe without side python script
            if has_relative_python_shebang(script_exe):  # all: no cover
                # relocatable python distribution
                return [interpreter(prefix), script_exe]
            return [script_exe]
        else:
            # Case in which the script is probably a Python file
            return [interpreter(prefix), script]
    else:
        return [interpreter(prefix), os.path.join(prefix, "bin", name)]


def is_console() -> bool:
    """Check if stdin is a console or not.

    :return: True if stdin is an interactive console
    """
    stdin_fd = sys.stdin.fileno()

    # First check using isatty call. On Windows isatty will return True only
    # if in a Win32 console (for example cygwin or msys ptys are not win32
    # consoles).
    is_tty = os.isatty(stdin_fd)
    if is_tty:
        return True

    if sys.platform == "win32":  # unix: no cover

        from msvcrt import get_osfhandle
        from e3.os.windows.object import object_name

        stdin_name = object_name(get_osfhandle(stdin_fd))
        if re.match(r"\\Device\\NamedPipe\\(cygwin|msys).*-pty.*$", stdin_name):
            return True
        else:
            return False
    else:  # win32: no cover
        return False


def relocate_python_distrib(
    python_distrib_dir: Optional[str] = None,
    freeze: bool = False,
    platform: Optional[str] = None,
) -> None:
    """Adjust shebangs to freeze a Python distrib or make it relocatable.

    :param python_distrib_dir: Python distrib prefix. If None the current
        Python is used.
    :param freeze: if True use absolute paths in shebangs. If not use relative paths.
    :param platform: if None use sys.platform. Otherwise should be a platform value
        as returned by sys.platform.
    """
    if platform is None:
        platform = sys.platform

    if python_distrib_dir is None:
        python_distrib_dir = sys.prefix

    if platform == "win32":  # unix: no cover
        script_dir = os.path.join(python_distrib_dir, "Scripts")
    else:  # win32: no cover
        script_dir = os.path.join(python_distrib_dir, "bin")

    # The python interpreter of the selected distribution
    python_binary = interpreter(prefix=python_distrib_dir)

    # Search all scripts
    for fname in os.listdir(script_dir):
        script_path = os.path.join(script_dir, fname)

        if not os.path.isfile(script_path):
            continue

        with open(script_path, "rb") as fd:
            content = fd.read()

        # By default shebang is found in file first line
        shebang_offset = 0

        if not content.startswith(b"#!"):
            if platform != "win32":  # win32: no cover
                continue
            else:  # unix: no cover
                # Check if the file is windows executable with an embedded script.

                # Windows executable starts with a MS-DOS header. Location
                # of PE header can be found at offset 0x3c.
                pe_offset = struct.unpack_from("I", content, offset=0x3C)[0]
                if content[pe_offset : pe_offset + 4] != b"PE\0\0":
                    # Not a PE file
                    continue

                # Does the executable contains a shebang ?
                offsets = [m.start() for m in re.finditer(b"#!.*python", content)]

                if not offsets:
                    # No python shebang
                    continue

                assert len(offsets) == 1

                shebang_offset = offsets[0]

        launcher = content[:shebang_offset]
        payload = content[shebang_offset:]

        script_offset = payload.find(b"\n")
        shebang = payload[:script_offset]
        payload = payload[script_offset:]

        if b"python" not in shebang:
            continue

        # At this stage we are sure that this is a Python script
        if freeze:
            shebang = b"#!" + python_binary.encode("utf-8")
        else:
            shebang = os.path.basename(python_binary).encode("utf-8")
            if platform == "win32":  # unix: no cover
                shebang = b"#!" + shebang
            else:  # win32: no cover
                shebang = b"#!/usr/bin/env " + shebang

        with open(script_path, "wb") as fd:
            fd.write(launcher)
            fd.write(shebang)
            fd.write(payload)
