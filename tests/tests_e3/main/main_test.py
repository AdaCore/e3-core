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
    assert "mymain" in p.out


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
        r"^mymain:.*:.*: DEBUG    this is an info line\r?\n"
        "mymain:.*:.* DEBUG    this is a debug line",
        p.out,
    )


@pytest.mark.skipif(
    sys.platform in ("win32", "sunos5"),
    reason="Signal handler not set on windows." " Bug in signal handling in solaris",
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
