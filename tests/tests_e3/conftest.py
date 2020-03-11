import os
import tempfile
import yaml

from e3.env import Env
from e3.fs import rm
from e3.os.fs import cd, which

import pytest

# When the variable RESULTS_DIR is set to
# an existing directory, the testsuite will
# generate results file in "anod" format
RESULTS_DIR = os.environ.get("RESULTS_DIR")


class RequirementCoverage(object):
    """Track requirements <-> tests."""

    output_filename = None
    results = {}

    @classmethod
    def dump(cls):
        if cls.output_filename:
            with open(cls.output_filename, "w") as f:
                yaml.safe_dump(cls.results, f)


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


def pytest_configure(config):
    try:
        RequirementCoverage.output_filename = config.getoption(
            "requirement_coverage_report"
        )
    except ValueError:
        # Option not defined.
        pass


def require_vcs(prog, request):
    """Require svn or git to run the test.

    When in "CI" mode, a missing svn or git generates an error. In other
    modes the test is just skipped.
    :param prog: either "svn" or "git"
    """
    if not which(prog):
        if request.config.getoption("ci"):
            pytest.fail("{} not available".format(prog))
        else:
            pytest.skip("{} not available".format(prog))


@pytest.fixture(autouse=True)
@pytest.mark.usefixtures("git")
def require_git(request):
    """Require git."""
    marker = request.node.get_closest_marker("git")
    if marker:
        return require_vcs("git", request)


@pytest.fixture
def git(request):
    """Require git."""
    return require_vcs("git", request)


@pytest.fixture(autouse=True)
@pytest.mark.usefixtures("svn")
def require_svn(request):
    """Require svn."""
    marker = request.node.get_closest_marker("svn")
    if marker:
        return require_vcs("svn", request)


def pytest_itemcollected(item):
    """Keep track of all test linked to a requirement."""
    doc = item.obj.__doc__
    if RequirementCoverage.output_filename and doc:
        for line in item.obj.__doc__.splitlines():
            line = line.strip().strip(".")
            if line.startswith("REQ-"):
                RequirementCoverage.results[item.obj.__name__] = line


def pytest_collectreport(report):
    """Output requirement coverage report."""
    RequirementCoverage.dump()


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Generate results file that can be used by anod."""
    # execute all other hooks to obtain the report object
    outcome = yield
    rep = outcome.get_result()

    if not RESULTS_DIR or not os.path.isdir(RESULTS_DIR):
        return

    # we only look at actual test calls, not setup/teardown
    if rep.when == "call":
        outcome = rep.outcome.upper()
        test_name = rep.nodeid.replace("/", ".").replace("::", "--")
        if rep.longreprtext:
            with open(os.path.join(RESULTS_DIR, "{}.diff".format(test_name)), "w") as f:
                f.write(rep.longreprtext)

        with open(os.path.join(RESULTS_DIR, "results"), "a") as f:
            f.write("{}:{}\n".format(test_name, outcome))
