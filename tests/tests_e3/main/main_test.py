import re
import sys

import e3.env
import e3.os.process

import pytest


def test_main():
    assert (
        e3.env.Env().build.platform
        in e3.os.process.Run(["e3", "--platform-info=build"]).out
    )


def test_mainprog():
    with open("mymain.py", "w") as f:
        f.write(
            "\n".join(
                (
                    "#!/usr/bin/env python",
                    "from e3.main import Main",
                    "import os",
                    'm = Main(name="testmain")',
                    "m.parse_args()",
                    "m.argument_parser.print_usage()",
                )
            )
        )
    p = e3.os.process.Run([sys.executable, "mymain.py", "--nocolor"])
    assert "testmain" in p.out


# TODO:: Rework this test. It ends up creating a 1600 seconds long test on
#        linux (probably due to a timeout since we are offline), and about 250
#        seconds on Windows.
#
# In a first time, simply remove (by renaming) the test so that no other MR is
# impacted by timeout issue.
def to_rework_modules_logging_limitations():
    """Ensure that by default DEBUG logging info is not enabled for some modules."""
    with open("mymain.py", "w") as f:
        f.write(
            "\n".join(
                (
                    "#!/usr/bin/env python",
                    "from e3.main import Main",
                    "import requests",
                    "import logging",
                    'm = Main(name="testmain")',
                    "m.argument_parser.add_argument('--force-debug', "
                    "action='store_true')",
                    "m.parse_args()",
                    "if m.args.force_debug:",
                    "    logging.getLogger('requests').setLevel(logging.DEBUG)",
                    "    logging.getLogger('urllib3').setLevel(logging.DEBUG)",
                    "try:",
                    "    r = requests.get('https://www.google.com')",
                    "except Exception:",
                    "    pass",
                )
            )
        )

    p = e3.os.process.Run(
        [sys.executable, "mymain.py", "-v", "--nocolor"], error=e3.os.process.STDOUT
    )
    p2 = e3.os.process.Run(
        [sys.executable, "mymain.py", "-v", "--nocolor", "--force-debug"],
        error=e3.os.process.STDOUT,
    )
    assert p2.out != p.out
    assert "DEBUG" in p2.out


def test_mainprog_with_console_logs():
    with open("mymain.py", "w") as f:
        f.write(
            "\n".join(
                (
                    "#!/usr/bin/env python",
                    "from e3.main import Main",
                    "import os",
                    'm = Main(name="testmain")',
                    "m.parse_args()",
                    "import logging",
                    'logging.debug("this is an info line")',
                    'logging.debug("this is a debug line")',
                )
            )
        )
    p = e3.os.process.Run(
        [sys.executable, "mymain.py", "-v", "--console-logs=mymain", "--nocolor"]
    )

    assert re.search(
        r"^mymain:.*:.*: DEBUG +this is an info line\r?\n"
        "mymain:.*:.* DEBUG +this is a debug line",
        p.out,
        re.MULTILINE,
    )


@pytest.mark.skipif(
    sys.platform not in ("win32",),
    reason="This test is only for windows platform",
)
def test_x86_64_windows_default():
    with open("mymain.py", "w") as f:
        f.write(
            "\n".join(
                (
                    "#!/usr/bin/env python",
                    "from e3.main import Main",
                    "m = Main(platform_args=True, default_x86_64_on_windows=True)",
                    "m.parse_args()",
                    "print(m.args.build)",
                )
            )
        )
    p = e3.os.process.Run([sys.executable, "mymain.py", "--nocolor"], timeout=10)
    assert "x86_64-windows64" in p.out


def test_default_env_callback():
    with open("mymain.py", "w") as f:
        f.write(
            "\n".join(
                (
                    "#!/usr/bin/env python",
                    "from e3.main import Main",
                    "from e3.env import Env",
                    "def cb(args):",
                    "   Env().set_build('ppc-linux')",
                    "m = Main(platform_args=True)",
                    "m.parse_args(pre_platform_args_callback=cb)",
                    "print(Env().build)",
                )
            )
        )
    p = e3.os.process.Run([sys.executable, "mymain.py", "--nocolor"], timeout=10)
    assert "ppc-linux" in p.out

    p = e3.os.process.Run(
        [sys.executable, "mymain.py", "--nocolor", "--build=x86_64-linux"], timeout=10
    )
    assert "x86_64-linux" in p.out


@pytest.mark.skipif(
    sys.platform in ("win32", "sunos5"),
    reason="Signal handler not set on windows. Bug in signal handling in solaris",
)
def test_sigterm():
    with open("mymain.py", "w") as f:
        f.write(
            "\n".join(
                (
                    "#!/usr/bin/env python",
                    "from e3.main import Main",
                    "import os",
                    "import signal",
                    "m = Main()",
                    "m.parse_args()",
                    "import time",
                    "time.sleep(10)",
                )
            )
        )
    p = e3.os.process.Run([sys.executable, "mymain.py", "--nocolor"], timeout=1)
    assert "SIGTERM received" in p.out
