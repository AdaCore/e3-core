from __future__ import absolute_import, division, print_function

import logging
import tempfile

import e3.log
from e3.env import Env
from e3.fs import rm
from e3.os.fs import cd, which

import pytest

# Activate full debug logs
e3.log.activate(level=logging.DEBUG, e3_debug=True)


@pytest.fixture(autouse=True)
def env_protect(request):
    """Protection against environment change.

    The fixture is enabled for all tests and does the following:

    * store/restore env between each tests
    * create a temporary directory and do a cd to it before each
      test. The directory is automatically removed when test ends
    """
    Env().store()
    tempd = tempfile.mkdtemp()
    cd(tempd)

    def restore_env():
        Env().restore()
        rm(tempd, True)

    request.addfinalizer(restore_env)


def pytest_addoption(parser):
    parser.addoption('--ci', action='store_true',
                     help='Tests are running on a CI server')


@pytest.fixture(autouse=True)
def require_git(request):
    marker = request.node.get_marker('git')
    if marker and not which('git'):
        if request.config.getoption('ci'):
            pytest.fail('git not available')
        else:
            pytest.skip('git not available')
