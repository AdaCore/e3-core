from __future__ import annotations

from os.path import abspath, dirname, join as path_join, isfile, isdir
from functools import partial
from json import loads as json_loads
from typing import TYPE_CHECKING
from re import compile as regex_compile
from traceback import format_stack as traceback_format_stack

from e3.fs import mkdir
from e3.python.wheel import Wheel

import pytest

if TYPE_CHECKING:
    from typing import Any


from e3.pytest import require_tool

git = require_tool("git")
svn = require_tool("svn")


class PypiSimulator:
    PYPI_URL = "https://pypi.org"
    MATCHER = regex_compile(f"{PYPI_URL}/pypi/(?P<package>.*)/json")
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

    def __exit__(self, type_t: Any, value: Any, traceback: Any) -> None:
        self.requests_mock.stop()


@pytest.fixture(scope="function")
def pypi_server(requests_mock):
    requests_mock.stop()
    return PypiSimulator(requests_mock)
