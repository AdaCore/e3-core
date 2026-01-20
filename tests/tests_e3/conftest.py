from __future__ import annotations

from os.path import abspath, dirname, join as path_join, isfile, isdir
from typing import TYPE_CHECKING
from re import compile as regex_compile
from traceback import format_stack as traceback_format_stack
import hashlib
import random
import string
import json
import shutil
import os
from e3.fs import mkdir, cp
from e3.os.fs import touch, which
from e3.python.wheel import Wheel
from e3.maven import MavenLink

import pytest

if TYPE_CHECKING:
    from typing import Any
    from collections.abc import Set


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

    def __enter__(self) -> PypiSimulator:
        self.requests_mock.start()
        self.requests_mock.get(self.SIMPLE_MATCHER, text=self.get_metadata)
        self.requests_mock.get(self.DOWNLOAD_MATCHER, content=self.get_resource)
        return self

    def __exit__(self, type_t: Any, value: Any, traceback: Any) -> None:
        self.requests_mock.stop()


@pytest.fixture(scope="function")
def pypi_server(requests_mock) -> PypiSimulator:
    requests_mock.stop()
    return PypiSimulator(requests_mock)


class MavenCentralSimulator:
    METADATA_MATCHER = regex_compile(
        f"^{MavenLink.BASE_URL}/(?P<group>.*)/(?P<name>.*)/maven-metadata.xml$"
    )
    FILE_MATCHER = regex_compile(
        f"^{MavenLink.BASE_URL}/(?P<group>.*)/(?P<name>.*)/(?P<version>.*)/"
        "(?P<filename>.*\\.(jar|pom))$"
    )

    def __init__(self, requests_mock: Any) -> None:
        """Create the central simulator.

        :param request_mock: The mocker to use. See requests_mock modules for more
            information.
        """
        self.__packages: dict[str, dict[str, dict[str, dict[str, str]]]] = {}
        self.__requests_mock = requests_mock
        self.__requests_mock.stop()

    def get_package_data(self, group: str, name: str, version: str) -> dict[str, str]:
        """Retrieve the package data.

        The package data is a dictionnary with 'content', 'sha1' and 'md5' keys. The
        first key (content) reprensent the file content. The 'sha1' and 'md5' represent
        the checksum of the package content.

        Theses packages must be registred using "self.register_package".

        :param group: The maven package group.
        :param name: The maven package name (aka: artifactId).
        :param version: The maven package version.
        :return: the corresponding dictionnary.
        :raises KeyError: if the package is not found.
        """
        return self.__packages[group][name][version]

    def get_pom_data(self, group: str, name: str, version: str) -> dict[str, str]:
        """Retrieve the POM data.

        The POM data is a dictionnary with 'content', 'sha1' and 'md5' keys. The first
        key (content) reprensent the file content. The 'sha1' and 'md5' represent the
        checksum of the POM content.

        Theses data are created when using "self.register_package".

        :param group: The maven package group.
        :param name: The maven package name (aka: artifactId).
        :param version: The maven package version.
        :return: the corresponding dictionnary.
        :raises KeyError: if the package is not found.
        """
        return self.__packages[group][name][version]["pom"]

    def register_package(
        self,
        group: str,
        name: str,
        versions: Set[str],
        *,
        latest: str | None = None,
        release: str | None = None,
    ) -> None:
        """Register a new package in the simulator.

        The content and the checksum is auto generated. Be carefull: The package is not
        installable or usable with java, the returned content is random.

        :param group: The maven package group.
        :param name: The maven package name (aka: artifactId).
        :param versions: The available package version.
        :param latest: The optionnal latest package.
        :param release: The optionnal release package.
        """
        self.__packages.setdefault(group, {})

        self.__packages[group][name] = {}

        if latest:
            self.__packages[group][name]["latest"] = latest
        else:
            self.__packages[group][name].pop("latest", None)

        if release:
            self.__packages[group][name]["release"] = latest
        else:
            self.__packages[group][name].pop("release", None)

        for version in versions:
            content = version + "".join(
                random.choice(string.ascii_uppercase + string.digits) for _ in range(10)
            )
            pom_content = version + "".join(
                random.choice(string.ascii_uppercase + string.digits) for _ in range(10)
            )
            encoded_content = content.encode("utf-8")
            encoded_pom_content = pom_content.encode("utf-8")
            self.__packages[group][name][version] = {
                "content": content,
                "sha1": hashlib.sha1(encoded_content).hexdigest(),
                "md5": hashlib.md5(encoded_content).hexdigest(),
                "pom": {
                    "content": pom_content,
                    "sha1": hashlib.sha1(encoded_pom_content).hexdigest(),
                    "md5": hashlib.md5(encoded_pom_content).hexdigest(),
                },
            }

    def _get_file(self, request: Any, context: Any) -> str:
        """Get a Maven package file.

        This function is also used to simulate a HEAD request.

        :param request: The mocked request received. See request_mock for more
            information.
        :param context: The mocked context. This context is used to generate the HTTP
            response. See request_mock for more information.
        :return: The response content as a string.
        """
        m = self.FILE_MATCHER.match(request.url)
        if not m:
            context.status_code = 400
            return json.dumps(
                {
                    "message": "Bad Request",
                    "exception": "Mocked Mvn Central received an unexpected request",
                    "url": request.url,
                    "traceback": [tmp.strip() for tmp in traceback_format_stack()],
                }
            )

        group = m.group("group").replace("/", ".")
        name = m.group("name")
        version = m.group("version")
        filename = m.group("filename")

        if (
            not group
            or not name
            or not version
            or not filename
            or group not in self.__packages
            or name not in self.__packages[group]
            or version not in self.__packages[group][name]
        ):
            context.status_code = 404
            return json.dumps(
                {
                    "message": "Not Found",
                    "exception": f"'{group}/{name}@{version}' not found",
                    "url": request.url,
                    "package": f"{group}/{name}@{version}",
                    "traceback": [tmp.strip() for tmp in traceback_format_stack()],
                }
            )

        data = (
            self.__packages[group][name][version]
            if filename.endswith(".jar")
            else self.__packages[group][name][version]["pom"]
        )

        context.headers["x-checksum-sha1"] = data["sha1"]
        context.headers["x-checksum-md5"] = data["md5"]
        context.status_code = 200

        if request.method == "HEAD":
            return ""
        return data["content"]

    def _get_metadata(self, request: Any, context: Any) -> str:
        """Get a Maven package metadata.

        :param request: The mocked request received. See request_mock for more
            information.
        :param context: The mocked context. This context is used to generate the HTTP
            response. See request_mock for more information.
        :return: The response content as a string.
        """
        m = self.METADATA_MATCHER.match(request.url)
        if not m:
            context.status_code = 400
            return json.dumps(
                {
                    "message": "Bad Request",
                    "exception": "Mocked Mvn Central received an unexpected request",
                    "url": request.url,
                    "traceback": [tmp.strip() for tmp in traceback_format_stack()],
                }
            )

        group = m.group("group").replace("/", ".")
        name = m.group("name")

        if group not in self.__packages or name not in self.__packages[group]:
            context.status_code = 404
            return json.dumps(
                {
                    "message": "Not Found",
                    "exception": f"'{group}/{name}/maven-metadata.xml' not found",
                    "url": request.url,
                    "package": f"{group}/{name}",
                    "traceback": [tmp.strip() for tmp in traceback_format_stack()],
                }
            )

        package_data = self.__packages[group][name]

        versioning = "<versioning>"
        versions = "<versions>"
        for key, val in package_data.items():
            if key in ("latest", "release"):
                versioning += f"<{key}>{val}</{key}>"
            else:
                versions += f"<version>{key}</version>"
        versions += "</versions>"
        versioning += versions
        versioning += "<lastUpdated>20101111000655</lastUpdated>"
        versioning += "</versioning>"

        result = f"""<metadata>
<groupId>{group}</groupId>
<artifactId>{name}</artifactId>
{versioning}
</metadata>"""

        context.status_code = 200
        context.headers["x-checksum-sha1"] = hashlib.sha1(
            result.encode("utf-8")
        ).hexdigest()
        context.headers["x-checksum-md5"] = hashlib.md5(
            result.encode("utf-8")
        ).hexdigest()
        return result

    def __enter__(self) -> MavenCentralSimulator:
        self.__requests_mock.start()
        self.__requests_mock.get(self.METADATA_MATCHER, text=self._get_metadata)
        self.__requests_mock.head(self.FILE_MATCHER, text=self._get_file)
        self.__requests_mock.get(self.FILE_MATCHER, text=self._get_file)
        return self

    def __exit__(self, type_t: Any, value: Any, traceback: Any) -> None:
        self.__requests_mock.stop()


@pytest.fixture(scope="function")
def maven_central(requests_mock) -> MavenCentralSimulator:
    requests_mock.stop()
    return MavenCentralSimulator(requests_mock)
