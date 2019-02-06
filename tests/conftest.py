from __future__ import absolute_import, division, print_function

import logging
import tempfile

import e3.log
import yaml
from e3.env import Env
from e3.fs import rm
from e3.os.fs import cd, which

import pytest

# Activate full debug logs
e3.log.activate(level=logging.DEBUG, e3_debug=True)


class RequirementCoverage(object):
    """Track requirements <-> tests."""

    output_filename = None
    results = {}

    @classmethod
    def dump(cls):
        if cls.output_filename:
            with open(cls.output_filename, 'w') as f:
                yaml.dump(cls.results, f)


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
    parser.addoption('--requirement-coverage-report',
                     help='Report requirement coverage')


def require_vcs(prog, request):
    """Require svn or git to run the test.

    When in "CI" mode, a missing svn or git generates an error. In other
    modes the test is just skipped.
    :param prog: either "svn" or "git"
    """
    if not which(prog):
        if request.config.getoption('ci'):
            pytest.fail('{} not available'.format(prog))
        else:
            pytest.skip('{} not available'.format(prog))


@pytest.fixture(autouse=True)
@pytest.mark.usefixtures("git")
def require_git(request):
    """Require git."""
    marker = request.node.get_closest_marker('git')
    if marker:
        return require_vcs('git', request)


@pytest.fixture
def git(request):
    """Require git."""
    return require_vcs('git', request)


@pytest.fixture(autouse=True)
@pytest.mark.usefixtures("svn")
def require_svn(request):
    """Require svn."""
    marker = request.node.get_closest_marker('svn')
    if marker:
        return require_vcs('svn', request)


def pytest_configure(config):
    RequirementCoverage.output_filename = config.getoption(
        'requirement_coverage_report')


def pytest_itemcollected(item):
    """Keep track of all test linked to a requirement."""
    doc = item.obj.__doc__
    if RequirementCoverage.output_filename and doc:
        for line in item.obj.__doc__.splitlines():
            line = line.strip().strip('.')
            if line.startswith('REQ-'):
                RequirementCoverage.results[item.obj.__name__] = line


def pytest_collectreport(report):
    """Output requirement coverage report."""
    RequirementCoverage.dump()
