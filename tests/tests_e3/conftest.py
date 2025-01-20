from __future__ import annotations

from os.path import abspath, dirname, join as path_join, isfile, isdir
from typing import TYPE_CHECKING
from re import compile as regex_compile
from traceback import format_stack as traceback_format_stack
import json
import shutil
import os
from e3.fs import mkdir, cp
from e3.os.fs import touch, which
from e3.python.wheel import Wheel

import pytest

if TYPE_CHECKING:
    from typing import Any


from e3.pytest import require_tool

git = require_tool("git")
ldd = require_tool("ldd")


def svn_wrapper(request: pytest.FixtureRequest) -> None:
    if not which("svn"):
        pytest.skip("svn is not available")


svn = pytest.fixture(svn_wrapper)


class PypiSimulator:
    PYPI_URL = "https://pypi.org"
    PYPIHOSTED_URL = "https://files.pythonhosted.org"
    SIMPLE_MATCHER = regex_compile(f"{PYPI_URL}/simple/(?P<package>.*)/")
    DOWNLOAD_MATCHER = regex_compile(f"{PYPIHOSTED_URL}/(?P<path>.*)")
    DATA_DIR = path_join(dirname(abspath(__file__)), "pypi_data")

    def __init__(self, requests_mock: Any) -> None:
        self.mocked_download_urls: set[str] = set()
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

        pkg = Wheel.build(
            source_dir=name,
            dest_dir=".",
            build_args=["--no-build-isolation", "--no-index"],
        )
        assert isfile(pkg.path)

        with open(pkg.path, "rb") as f:
            result = f.read()

        context.status_code = 200
        return result

    def get_metadata(self, request: Any, context: Any) -> dict:
        m = self.SIMPLE_MATCHER.match(request.url)
        if not m:
            context.status_code = 400
            return json.dumps(
                {
                    "message": "Bad Request",
                    "exception": "Mocked pypi received an unexpected request",
                    "url": request.url,
                    "traceback": [tmp.strip() for tmp in traceback_format_stack()],
                }
            )

        package = m.group("package")

        path = path_join(self.DATA_DIR, "simple", f"{package}.html")
        if not isfile(path):
            context.status_code = 404
            return json.dumps(
                {
                    "message": "Not Found",
                    "exception": f"'{package}.html' file not found",
                    "url": request.url,
                    "package": package,
                    "traceback": [tmp.strip() for tmp in traceback_format_stack()],
                }
            )

        try:
            with open(path) as html_file:
                result = html_file.read()

        except Exception as e:
            context.status_code = 500
            return json.dumps(
                {
                    "message": "Internal Server Error",
                    "exception": str(e),
                    "url": request.url,
                    "package": package,
                    "traceback": [tmp.strip() for tmp in traceback_format_stack()],
                }
            )

        context.status_code = 200
        return result

    def get_resource(self, request: Any, context: Any) -> str:
        m = self.DOWNLOAD_MATCHER.match(request.url)
        package = m.group("path").split("/")[-1].split("#")[0]
        package_name = "-".join(package.split("-", 2)[0:2])
        metadata_file = os.path.join(self.DATA_DIR, "metadata", package_name)
        mkdir(f"{package_name}/{package_name}.dist-info")
        if os.path.isfile(metadata_file):
            cp(metadata_file, f"{package_name}/{package_name}.dist-info/METADATA")
        else:
            touch(f"{package_name}/{package_name}.dist-info/METADATA")
        shutil.make_archive(package, format="zip", root_dir=package_name, base_dir=".")
        with open(f"{package}.zip", "rb") as fd:
            result = fd.read()
        cp(f"{package}.zip", "/tmp")
        context.status_code = 200
        return result

    def __enter__(self):
        self.requests_mock.start()
        self.requests_mock.get(self.SIMPLE_MATCHER, text=self.get_metadata)
        self.requests_mock.get(self.DOWNLOAD_MATCHER, content=self.get_resource)
        return self

    def __exit__(self, type_t: Any, value: Any, traceback: Any) -> None:
        self.requests_mock.stop()


@pytest.fixture(scope="function")
def pypi_server(requests_mock):
    requests_mock.stop()
    return PypiSimulator(requests_mock)
