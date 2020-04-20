# type: ignore
import logging
import os

import e3.log


def init_testsuite_env():
    """Initialize testsuite environment."""
    # Activate full debug logs
    e3.log.activate(level=logging.DEBUG, e3_debug=True)

    # Force UTC timezone
    os.environ["TZ"] = "UTC"
    os.environ["E3_ENABLE_FEATURE"] = "smtp_ssl"
    os.environ["E3_CONFIG"] = "/dev/null"
    # Ignore E3_HOSTNAME variable
    if "E3_HOSTNAME" in os.environ:
        del os.environ["E3_HOSTNAME"]


init_testsuite_env()


def pytest_addoption(parser):
    parser.addoption(
        "--ci", action="store_true", help="Tests are running on a CI server"
    )
    parser.addoption(
        "--requirement-coverage-report", help="Report requirement coverage"
    )
