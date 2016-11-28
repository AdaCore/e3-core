from __future__ import absolute_import, division, print_function

import logging
import tempfile

import e3.log
import pytest
from e3.env import Env
from e3.fs import rm
from e3.os.fs import cd

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
