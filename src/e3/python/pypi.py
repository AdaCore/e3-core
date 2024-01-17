from __future__ import annotations
import json
import logging
import requests
import re
import os
import time
import packaging.version
import packaging.tags
import packaging.specifiers
from typing import TYPE_CHECKING
from e3.error import E3Error
from e3.python.wheel import Wheel
from e3.fs import cp
from pkg_resources import Requirement

if TYPE_CHECKING:
    from typing import Any
    from types import TracebackType

logger = logging.getLogger("e3.python.pypi")

PLATFORM_SYSTEMS = {"darwin": "Darwin", "win32": "Windows", "linux": "Linux"}


class PyPIError(E3Error):
    pass


class PackageFile:
    """A release package file as represented in PyPI."""

    def __init__(self, pypi: PyPIClosure, *, data: dict["str", Any]) -> None:
        """Initialize a package file.

        :param pypi: the pypi session
        :param data: json data for the package file
        """
        self.data = data

        # Get metadata from filename if possible
        if self.is_wheel:
            _, _, py_tags, abi_tags, platform_tags = self.filename[:-4].split("-")
        else:
            py_tags = ""
            abi_tags = ""
            platform_tags = ""

        self.py_tags = py_tags.split(".")
        self.abi_tags = abi_tags.split(".")
        self.platform_tags = platform_tags.split(".")
        self.pypi = pypi

    @property
    def kind(self) -> str:
        """Return the package kind."""
        return self.data["packagetype"]

    @property
    def filename(self) -> str:
        """Return the package filename."""
        return self.data["filename"]

    @property
    def url(self) -> str:
        """Return the download url."""
        return self.data["url"]

    @property
    def is_yanked(self) -> bool:
        """Return whether the package is yanked."""
        return self.data.get("yanked", False)

    @property
    def is_wheel(self) -> bool:
        """Return whether the package is a wheel."""
        return self.kind == "bdist_wheel"

    def is_compatible_with_platforms(self, platform_list: list[str]) -> bool:
        """Check if the package is compatible with a list of platform.

        :param platform_list: a list of platform name in e3 format (x86_64-linux, ...)
        :return: True if the package is compatible with any of the platform
        """
        if not self.is_wheel:
            result = True
        else:
            platforms_regex = ["any"]
            if "x86_64-linux" in platform_list:
                platforms_regex.append("manylinux.*x86_64")
            if "aarch64-linux" in platform_list:
                platforms_regex.append("manylinux.*aarch64")
            if "x86_64-darwin" in platform_list:
                platforms_regex.append("macosx.*(x86_64|intel|universal.*)")
            if "aarch64-darwin" in platform_list:
                platforms_regex.append("macosx.*(aarch64|arm64|universal.*)")
            if "x86_64-windows" in platform_list or "x86_64-windows64" in platform_list:
                platforms_regex.append("win_amd64")
            if "x86-windows" in platform_list:
                platforms_regex.append("win32")

            result = any(
                (
                    platform
                    for platform in self.platform_tags
                    if re.match("|".join(platforms_regex), platform)
                )
            )
        logger.debug(f"{self.filename} compatible with {platform_list}: {result}")
        return result

    @property
    def is_generic_wheel(self) -> bool:
        """Return whether the package is a generic package.

        If True then the wheel can be used on any Python 3.x version and on any
        platform.
        """
        return (
            "py3" in self.py_tags
            and "none" in self.abi_tags
            and "any" in self.platform_tags
        )

    def is_compatible_with_cpython3(self, minor_version: int) -> bool:
        """Check whether the package is compatible with a given python 3 version.

        :param minor_version: to check compatibility with 3.10 set this param to 10
        :return: True if compatible
        """
        if not self.is_wheel:
            result = True
        else:
            result = (
                any(
                    (
                        tag
                        for tag in self.py_tags
                        if tag in ("py3", f"cp3{minor_version}")
                    )
                )
                or "abi3" in self.abi_tags
            )
        logger.debug(
            f"{self.filename} compatible with Python 3.{minor_version}: {result}"
        )
        return result

    def download(self) -> str:
        """Download the file in the PyPI cache.

        :return: the location of the file
        """
        download_path = os.path.join(self.pypi.cache_dir, self.filename)
        if not os.path.isfile(download_path):
            if self.url.startswith("file://"):
                cp(self.url.replace("file://", "", 1), download_path)
            else:
                answer = requests.get(self.url, stream=True)
                with open(download_path, "wb") as fd:
                    fd.write(answer.content)
        return download_path

    @property
    def requirements(self) -> set[Requirement]:
        """Return the list of requirements for the package.

        Only dependencies for wheels can be tracked.
        """
        if not self.is_wheel:
            return set()

        wheel_path = self.download()
        return Wheel(path=wheel_path).requirements


class Package:
    def __init__(
        self,
        pypi: PyPIClosure,
        *,
        data: dict["str", Any],
    ) -> None:
        """Initialize a pakage metadata object.

        :param pypi: a PyPIClosure session
        :param data: the data as fetched on pypi
        """
        self.pypi = pypi
        self.data = data
        self.extras = {""}
        self.versions = []
        self.releases: dict[str, list[PackageFile]] = {}
        self.sys_platforms: set[str] = set()

        for version in self.data.get("releases", {}):
            try:
                v = packaging.version.parse(version)

                if (not v.is_prerelease and not v.is_devrelease) or (
                    v.is_prerelease and self.name in pypi.allowed_prerelease
                ):
                    self.versions.append(v)
            except Exception:
                logger.warning(f"Cannot parse version {version} of {self.name}")
        logger.debug(f"Load package {self.name}")

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, Package) and other.name == self.name

    def __hash__(self) -> int:
        return hash(self.name)

    @property
    def as_requirement(self) -> list[Requirement]:
        """Return a list of requirement string for the package."""
        if len(self.sys_platforms) == len(PLATFORM_SYSTEMS):
            return [Requirement.parse(f"{self.name}=={self.latest_version}")]
        else:
            return [
                Requirement.parse(
                    f"{self.name}=={self.latest_version}; sys_platform == '{p}'"
                )
                for p in self.sys_platforms
            ]

    @property
    def name(self) -> str:
        """Name of the package."""
        return self.data["info"]["name"]

    @property
    def latest_release(self) -> list[PackageFile]:
        """Return the latest release files."""
        if self.latest_version not in self.releases:
            all_files = [
                PackageFile(pypi=self.pypi, data=el)
                for el in self.data["releases"][self.latest_version]
            ]
            all_files = [
                f
                for f in all_files
                if f.is_compatible_with_cpython3(self.pypi.python3_version)
                and f.is_compatible_with_platforms(self.pypi.platforms)
                and (not f.is_yanked or self.name in self.pypi.allowed_yanked)
            ]
            if any((f.is_generic_wheel for f in all_files)):
                all_files = [f for f in all_files if f.is_wheel]

            if not all_files:
                self.versions.remove(packaging.version.parse(self.latest_version))
                return self.latest_release

            self.releases[self.latest_version] = all_files

        return self.releases[self.latest_version]

    @property
    def has_generic_wheel(self) -> bool:
        """Return whether a generic wheel exists."""
        return any((f for f in self.latest_release if f.is_generic_wheel))

    @property
    def latest_release_requirements(self) -> set[Requirement]:
        """Return the requirements for the latest release."""
        result = set()
        for f in self.latest_release:
            for r in f.requirements:
                for extra in self.extras:
                    for sys_platform in self.pypi.sys_platforms:
                        if r.marker is None or r.marker.evaluate(
                            {
                                "python_version": f"3.{self.pypi.python3_version}",
                                "sys_platform": sys_platform,
                                "platform_system": PLATFORM_SYSTEMS[sys_platform],
                                "extra": extra,
                            }
                        ):
                            self.pypi.pkg(r.project_name).sys_platforms.add(
                                sys_platform
                            )
                            result.add(r)
        return result

    def closure(self, state: set[Package] | None = None) -> set[Package]:
        """Return package closure.

        :param state: an initial set of packages (internal parameter)
        :return: the closure of Packages associated with the most recent
            suitable release.
        """
        if state is None:
            state = set()

        for r in self.latest_release_requirements:
            p = self.pypi.add_requirement(r, explicit=False)

            if p not in state:
                state.add(p)
                state |= p.closure(state=state)

        return state

    def file_closure(self) -> set[str]:
        """Return file closure for the package."""
        all_pkgs = {self} | self.closure()
        all_files = set()
        for pkg in all_pkgs:
            logging.debug(
                f"Add files from {pkg.name} {len(self.latest_release)} "
                f"(from {self.name})"
            )
            all_files |= {f.download() for f in pkg.latest_release}
        return all_files

    @property
    def latest_version(self) -> str:
        """Return the latest version as str."""
        return str(max(self.versions))

    def add_constraint(self, requirement: Requirement) -> None:
        """Apply a new constraint to this package.

        The effect is mainly to remove versions of the current package that do not
        match the constraint. PyPIError is raised in case no version is available

        :param requirement: a requirement to apply
        """
        logging.debug(f"Apply constraint: {str(requirement)}")
        # Check if requirement applies to that package
        if requirement.project_name != self.name:
            return

        # Check platforms
        for sys_platform in self.pypi.sys_platforms:
            if requirement.marker is None or requirement.marker.evaluate(
                {
                    "python_version": f"3.{self.pypi.python3_version}",
                    "sys_platform": sys_platform,
                    "platform_system": PLATFORM_SYSTEMS[sys_platform],
                }
            ):
                self.sys_platforms.add(sys_platform)
        current_length = len(self.versions)

        # Apply version constraints
        for spec in requirement.specs:
            self.versions = [
                v
                for v in self.versions
                if packaging.specifiers.Specifier(f"{spec[0]}{spec[1]}").contains(
                    str(v)
                )
            ]

        if len(self.versions) != current_length:
            logging.debug(
                f"Found {len(self.versions)} versions after applying constraints"
            )
        if len(self.versions) == 0:
            logger.critical(f"Cannot satisfy constraint {requirement}")
            raise PyPIError(f"Cannot satisfy constraint {str(requirement)}")

    def __str__(self) -> str:
        return f"{self.name}=={self.latest_version}"


class PyPIClosure:
    """Represent a closure of Python package from PyPI."""

    def __init__(
        self,
        *,
        python3_version: int,
        platforms: list[str],
        cache_dir: str,
        cache_file: str | None = None,
        pypi_url: str = "https://pypi.org/pypi",
        allowed_prerelease: list[str] | None = None,
        allowed_yanked: list[str] | None = None,
    ) -> None:
        """Initialize a PyPI session.

        :param python3_version: python 3 minor version (i.e: for 3.9.1 it's 9)
        :param platforms: the list of platforms for which packages should be considered
        :param cache_dir: a cache directory used to store wheels and sources
        :param cache_file: if not None try to load data from a cache file. Note that
            data is cached a maximum of 24h. The cache contains results of requests to
            PyPI.
        :param pypi_url: set Python package registry URL. Default is PyPI
        :param allowed_prerelease: list of package names authorized to be into
            pre-release.
        :param allowed_yanked: list of package names authorized to have yanked flags set
            to true (see: PEP_592).
        """
        self.cache_file = cache_file
        self.cache_dir = cache_dir
        self.pypi_url = pypi_url
        self.db: dict[str, Any] = {}
        self.packages: dict[str, Package] = {}
        self.load_cache_file()
        self.requirements: set[Requirement] = set()
        self.explicit_requirements: set[Requirement] = set()
        self.allowed_prerelease = allowed_prerelease or []
        self.allowed_yanked = allowed_yanked or []

        self.platforms = platforms
        self.sys_platforms = set()
        for p in self.platforms:
            if "darwin" in p:
                self.sys_platforms.add("darwin")
            if "linux" in p:
                self.sys_platforms.add("linux")
            if "windows" in p:
                self.sys_platforms.add("win32")

        self.python3_version = python3_version

    def __enter__(self) -> PyPIClosure:
        return self

    def __exit__(
        self,
        _type: type[BaseException] | None,
        _val: BaseException | None,
        _tb: TracebackType | None,
    ) -> None:
        self.save_cache_file()

    def pkg(self, pkg: str, extras: list[str] | None = None) -> Package:
        """Fetch all metadata from PyPI for a given package.

        :param pkg: the package name
        :param extras: list of extras to consider for the package. For example
            if you need e3-core[test] extras should be set to ["test"]. None
            all extras for a given package are ignored.
        :return: a Package object
        """
        # Normalize the package name
        pkg = pkg.lower().replace("_", "-").replace(".", "-")

        pkg_extras = [""]
        if extras is not None:
            pkg_extras += extras

        if pkg not in self.packages:
            # Fetch the raw data
            if (
                pkg in self.db
                and (time.time() - self.db[pkg].get("timestamp", 0.0)) < 24 * 3600.0
            ):
                data_dict = self.db[pkg]["metadata"]
            else:
                answer = requests.get(f"{self.pypi_url}/{pkg}/json")
                if answer.status_code != requests.codes.ok:
                    raise PyPIError(
                        f"Cannot fetch {pkg} metadata from {self.pypi_url} "
                        f"(return: {answer.status_code})"
                    )
                data_dict = answer.json()
                self.db[pkg] = {"timestamp": time.time(), "metadata": data_dict}
            self.packages[pkg] = Package(pypi=self, data=data_dict)

        self.packages[pkg].extras |= set(pkg_extras)

        return self.packages[pkg]

    def add_wheel(self, filename: str) -> None:
        """Add manually a wheel to the local PyPI database.

        :param filename: path to the wheel
        """
        logging.debug(f"Add wheel {filename}")
        base, ext = os.path.splitext(os.path.basename(filename))
        (
            project_name,
            project_version,
            python_version,
            abi_version,
            platform,
        ) = base.split("-")
        project_name = project_name.lower().replace("_", "-")

        pkg = project_name.replace(".", "-")
        logging.debug(f"Add metadata for {pkg}")
        self.db[pkg] = {
            "timestamp": time.time(),
            "metadata": {
                "info": {"name": project_name},
                "local": True,
                "releases": {
                    project_version: [
                        {
                            "packagetype": "bdist_wheel",
                            "filename": os.path.basename(filename),
                            "url": f"file://{filename}",
                        }
                    ]
                },
            },
        }

    def closure(self) -> set[Package]:
        """Return the full Package closure.

        :return: a set of Package object.
        """
        result = set()
        for r in self.explicit_requirements:
            result.add(self.pkg(r.project_name))
            result |= self.pkg(r.project_name).closure()
        return result

    def file_closure(self) -> set[str]:
        """Return the file closure.

        :return: a list of paths
        """
        result = set()
        for r in self.explicit_requirements:
            result |= self.pkg(r.project_name).file_closure()
        return result

    def closure_as_requirements(self) -> list[Requirement]:
        """Return the list of frozen requirements for the closure.

        :return: a list of Requirements
        """
        req_lines = set()
        for p in self.closure():
            req_lines |= set(p.as_requirement)
        return sorted(req_lines, key=lambda x: x.project_name)

    def add_requirement(self, req: Requirement | str, explicit: bool = True) -> Package:
        """Add a requirement to the closure.

        :param req: a python requirement
        :param explicit: whether it is an explicit requirement or not
            (False value is used only internally)
        :return: a Package
        """
        if isinstance(req, str):
            req = Requirement.parse(req)

        if explicit:
            self.explicit_requirements.add(req)

        if req not in self.requirements:
            self.requirements.add(req)
            logger.info(f"Add requirement {req.project_name} extras={req.extras}")
            pkg = self.pkg(req.project_name, extras=list(req.extras))
            pkg.add_constraint(req)
            pkg.closure()
            return pkg
        else:
            return self.pkg(req.project_name, extras=list(req.extras))

    def load_cache_file(self) -> None:
        """Load cache information."""
        if self.cache_file is not None and os.path.isfile(self.cache_file):
            with open(self.cache_file) as fd:
                self.db = json.load(fd)

    def save_cache_file(self) -> None:
        """Save cache to file."""
        if self.cache_file is not None:
            with open(self.cache_file, "w") as fd:
                fd.write(json.dumps(self.db, indent=2))
