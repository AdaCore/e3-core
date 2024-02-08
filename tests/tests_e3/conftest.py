# type: ignore
from __future__ import annotations

from os import environ
from os.path import abspath, dirname, join as path_join, isfile, isdir
from functools import partial
from tempfile import mkdtemp
from yaml import safe_dump as yaml_safe_dump
from json import loads as json_loads
from typing import TYPE_CHECKING
from re import compile as regex_compile
from traceback import format_stack as traceback_format_stack

from e3.env import Env
from e3.fs import rm, mkdir
from e3.os.fs import cd, which
from e3.config import Config
from e3.python.wheel import Wheel

import pytest

if TYPE_CHECKING:
    from typing import Any

# When the variable RESULTS_DIR is set to
# an existing directory, the testsuite will
# generate results file in "anod" format
RESULTS_DIR = environ.get("RESULTS_DIR")


class RequirementCoverage:
    """Track requirements <-> tests."""

    output_filename = None
    results = {}

    @classmethod
    def dump(cls):
        if cls.output_filename:
            with open(cls.output_filename, "w") as f:
                yaml_safe_dump(cls.results, f)


@pytest.fixture(autouse=True)
def env_protect(request):
    """Protection against environment change.

    The fixture is enabled for all tests and does the following:

    * store/restore env between each tests
    * create a temporary directory and do a cd to it before each
      test. The directory is automatically removed when test ends
    """
    Env().store()
    tempd = mkdtemp()
    cd(tempd)
    Config.data = {}

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

    # Define this attribute to detect errors (not failures!) in tests.
    # This allows us to return a custom exit code, to differentiate between
    # test *failures* and actual *errors* (like syntactic errors) in the test
    # files themselves.
    pytest.test_errors = False


def require_vcs(prog, request):
    """Require svn or git to run the test.

    When in "CI" mode, a missing svn or git generates an error. In other
    modes the test is just skipped.
    :param prog: either "svn" or "git"
    """
    if not which(prog):
        if request.config.getoption("ci"):
            pytest.fail(f"{prog} not available")
        else:
            pytest.skip(f"{prog} not available")


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


@pytest.fixture
def svn(request):
    """Require svn."""
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

    if not RESULTS_DIR or not isdir(RESULTS_DIR):
        return

    # we only look at actual test calls, not setup/teardown
    if rep.when == "call":
        outcome = rep.outcome.upper()
        test_name = rep.nodeid.replace("/", ".").replace("::", "--")
        if rep.longreprtext:
            with open(path_join(RESULTS_DIR, f"{test_name}.diff"), "w") as f:
                f.write(rep.longreprtext)

        with open(path_join(RESULTS_DIR, "results"), "a") as f:
            f.write(f"{test_name}:{outcome}\n")
    else:
        # If we detect a failure in an item that is not a "proper" test call, it's most
        # likely an error.
        # For example, this could be a failing assertion or a syntax error in a
        # setup/teardown context.
        if rep.outcome == "failed":
            pytest.test_errors = True


@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session, exitstatus):
    """Manage the exit code depending on if errors were detected or not."""
    if pytest.test_errors:
        # Return with an exit code of `3` if we encountered errors (not failures).
        # This is the exit code that corresponds to an "internal error" according to the
        # pytest docs, which is the closest thing to having an actual Python error in
        # test code.
        session.exitstatus = 3


class PypiSimulator:
    PYPI_URL = "https://pypi.org"
    MATCHER = regex_compile(f"{PYPI_URL}/pypi/(?P<package>.*)/json")
    DATA_DIR = path_join(dirname(abspath(__file__)), "pypi_data")

    def __init__(self, requests_mock: Any) -> None:
        self.mocked_download_urls = set()
        self.requests_mock = requests_mock

        self.requests_mock.stop()

    def download_file(
        self, name: str, version: str, request: Any, context: Any
    ) -> bytes:
        if not isdir(name):
            mkdir(name)

        with open(path_join(name, "setup.py"), "w") as fd:
            fd.write("from setuptools import setup, find_packages\n")
            fd.write(f"setup(name='{name}',\n")
            fd.write(f"      version='{version}',\n")
            fd.write("       packages=find_packages())\n")

        mkdir(path_join(name, name))

        with open(path_join(name, name, "__init__.py"), "w") as fd:
            fd.write(f"# This is package {name}")

        pkg = Wheel.build(source_dir=name, dest_dir=".")
        assert isfile(pkg.path)

        with open(pkg.path, "rb") as f:
            result = f.read()

        context.status_code = 200
        return result

    def get_metadata(self, request: Any, context: Any) -> dict:
        m = self.MATCHER.match(request.url)
        if not m:
            context.status_code = 400
            return {
                "message": "Bad Request",
                "exception": "Mocked pypi received an unexpected request",
                "url": request.url,
                "traceback": [tmp.strip() for tmp in traceback_format_stack()],
            }

        package = m.group("package")

        path = path_join(self.DATA_DIR, "json", f"{package}.json")
        if not isfile(path):
            context.status_code = 404
            return {
                "message": "Not Found",
                "exception": f"'{package}.json' file not found",
                "url": request.url,
                "package": package,
                "traceback": [tmp.strip() for tmp in traceback_format_stack()],
            }

        try:
            with open(path) as json_file:
                result = json_loads(json_file.read())

            if "releases" not in result:
                raise Exception("Bad json metadata: 'releases' key not found")
        except Exception as e:
            context.status_code = 500
            return {
                "message": "Internal Server Error",
                "exception": str(e),
                "url": request.url,
                "package": package,
                "traceback": [tmp.strip() for tmp in traceback_format_stack()],
            }

        for version, data in result["releases"].items():
            for elm in data:
                # Only wheel are supported
                if elm["url"] not in self.mocked_download_urls or not elm[
                    "url"
                ].endswith(".whl"):
                    self.mocked_download_urls.add(elm["url"])
                    self.requests_mock.get(
                        elm["url"],
                        content=partial(
                            self.download_file, result["info"]["name"], version
                        ),
                    )
        context.status_code = 200
        return result

    def __enter__(self):
        self.requests_mock.start()
        self.requests_mock.get(self.MATCHER, json=self.get_metadata)
        return self

    def __exit__(self, type_t: Any, value: Any, traceback: Any):
        self.requests_mock.stop()


@pytest.fixture(scope="function")
def pypi_server(requests_mock):
    requests_mock.stop()
    return PypiSimulator(requests_mock)
