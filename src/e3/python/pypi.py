from __future__ import annotations
from typing import TYPE_CHECKING
import tarfile
import json
import e3.log
import re
from e3.python.wheel import Wheel
from e3.fs import cp, mkdir
from operator import attrgetter
import os
import requests
from urllib.parse import urlparse
from resolvelib import BaseReporter, Resolver
from resolvelib.providers import AbstractProvider
from resolvelib.resolvers import ResolutionImpossible
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from html.parser import HTMLParser
from packaging.version import Version, InvalidVersion
from e3.error import E3Error
from requests.exceptions import HTTPError

if TYPE_CHECKING:
    from types import TracebackType
    from typing import Any
    from collections.abc import Iterable, Mapping, Sequence, Iterator
    from resolvelib.structs import Matches
    from resolvelib.providers import Preference
    from resolvelib.resolvers import RequirementInformation


logger = e3.log.getLogger("e3.python.pypi")


class PyPIError(E3Error):
    pass


def get_pip_env(platform: str, python_version: Version) -> dict[str, str]:
    """Return an environment used by pip to match requirements markers.

    :param platform: a platform (e3 format)
    :param python_version: the Python version to consider
    """
    # We always consider Cpython
    pv = python_version
    result = {
        "implementation_name": "cpython",
        "platform_python_implementation": "CPython",
        "implementation_version": f"{pv.major}.{pv.minor}.{pv.micro}",
        "python_full_version": f"{pv.major}.{pv.minor}.{pv.micro}",
        "python_version": f"{pv.major}.{pv.minor}",
    }

    # Fill platform informations
    if platform.endswith("-darwin"):
        result["sys_platform"] = "darwin"
    elif platform.endswith("-linux"):
        result["sys_platform"] = "linux"
    elif platform.endswith("-windows") or platform.endswith("-windows64"):
        result["sys_platform"] = "win32"
    else:
        raise PyPIError(f"Non supported platform {platform}")

    result["platform_system"] = {
        "darwin": "Darwin",
        "win32": "Windows",
        "linux": "Linux",
    }[result["sys_platform"]]

    result["os_name"] = {
        "darwin": "posix",
        "win32": "nt",
        "linux": "posix",
    }[result["sys_platform"]]

    # ??? add missing platform_machine
    return result


class PyPILink:
    """Link returned by PyPI simple API."""

    def __init__(
        self,
        identifier: str,
        url: str,
        yanked: str | None,
        has_metadata: bool,
        require_python: str | None = None,
    ) -> None:
        """Initialize a PyPI link.

        :param identifier: the project identifier
        :param url: url of the resource
        :param yanked: yanker data
        :param has_metadata: True if metadata is directly available from PyPI
        :param require_python: require python data
        """
        self.identifier = identifier
        self.url = url
        self.yanked = yanked
        self.require_python = require_python
        self.has_metadata = has_metadata
        self._urlparse = urlparse(url)
        self.checksum = self._urlparse.fragment.replace("sha256=", "", 1)
        self.filename = self._urlparse.path.rpartition("/")[-1]

        py_tags = ""
        abi_tags = ""
        platform_tags = ""
        # Retreive a package version.
        if self.filename.endswith(".whl"):
            # Wheel filenames contain compatibility information
            _, version, py_tags, abi_tags, platform_tags = self.filename[:-4].rsplit(
                "-", 4
            )
        else:
            package_filename = self.filename
            if any(package_filename.endswith(ext) for ext in (".tar.gz", ".tar.bz2")):
                # Remove .gz or .bz2
                package_filename, _ = os.path.splitext(package_filename)
            # Remove remaining extension
            basename, ext = os.path.splitext(package_filename)
            # Retrieve version
            _, version, *_ = basename.rsplit("-", 1)

        self.pkg_version = Version(version)
        self.pkg_py_tags = py_tags.split(".")
        self.pkg_abi_tags = abi_tags.split(".")
        self.pkg_platform_tags = platform_tags.split(".")

    @property
    def is_yanked(self) -> bool:
        """Return True if the package is yanked."""
        return self.yanked is not None

    @property
    def metadata_url(self) -> str:
        """Return the metadata url."""
        return self.url + ".metadata"

    def as_dict(self) -> dict[str, None | bool | str]:
        """Serialize the a PyPILink into a Python dict that can be dump as json."""
        res = {
            "identifier": self.identifier,
            "url": self.url,
            "filename": self.filename,
            "checksum": self.checksum,
            "yanked": self.yanked,
            "has_metadata": self.has_metadata,
        }
        if self.require_python:
            res["require_python"] = self.require_python
        return res

    @classmethod
    def from_dict(cls, data: dict) -> PyPILink:
        """Transform a generic dict into a PyPILink.

        :param data: the dict to read
        """
        return PyPILink(
            identifier=data["identifier"],
            url=data["url"],
            yanked=data.get("yanked"),
            has_metadata=data["has_metadata"],
            require_python=data.get("require-python"),
        )


class PyPILinksParser(HTMLParser):
    """HTML parser to parse links from the PyPI simple API."""

    def __init__(self, identifier: str) -> None:
        """Initialize the parser."""
        super().__init__()
        self.identifier = identifier
        self.links: list[PyPILink] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """See HTMLParser doc."""
        if tag == "a":
            attr_dict = dict(attrs)
            assert attr_dict["href"] is not None
            try:
                self.links.append(
                    PyPILink(
                        url=attr_dict["href"],
                        yanked=attr_dict.get("data-yanked"),
                        require_python=attr_dict.get("data-requires-python"),
                        has_metadata="data-dist-info-metadata" in attr_dict,
                        identifier=self.identifier,
                    )
                )
            except InvalidVersion:
                pass


class PyPI:
    def __init__(
        self,
        pypi_url: str = "https://pypi.org/",
        allowed_yanked: list[str] | None = None,
        allowed_prerelease: list[str] | None = None,
        cache_dir: str = "pypi.cache",
    ) -> None:
        """Interface to a PYPI simple API.

        :param pypi_url: URL to pypi
        :param allowed_yanked: list of projects for which yanked releases are accepted
        """
        self.pypi_url = pypi_url

        # Normalize the URL
        if not self.pypi_url.endswith("/"):
            self.pypi_url += "/"

        # Normalize list of package for which yanked releases are acceptable
        if allowed_yanked is not None:
            self.allowed_yanked = {canonicalize_name(el) for el in allowed_yanked}
        else:
            self.allowed_yanked = set()

        if allowed_prerelease is None:
            self.allowed_prerelease = set()
        else:
            self.allowed_prerelease = {
                canonicalize_name(el) for el in allowed_prerelease
            }

        self.cache_dir = os.path.abspath(cache_dir)
        self.cache: dict[str, list[PyPILink]] = {}
        self.candidate_cache: dict[str, list[PyPICandidate]] = {}

    @property
    def pypi_cache_file(self) -> str:
        """Get location of file containing result of pypi requests."""
        return os.path.join(self.cache_dir, "pypi-cache.json")

    def fetch_project_links(self, name: str) -> list[PyPILink]:
        """Fetch list of resource for a given Python package.

        :param name: Python package name
        :return: a list of dict containing the link to each resource along with
            some metadata
        """
        identifier = canonicalize_name(name)
        if identifier not in self.cache:
            logger.debug(f"fetch {identifier} links from {self.pypi_url}")
            pypi_request = requests.get(self.pypi_url + "simple/" + identifier + "/")
            pypi_request.raise_for_status()
            pypi_links_parser = PyPILinksParser(identifier)
            pypi_links_parser.feed(pypi_request.text)

            # Update cache
            self.cache[identifier] = pypi_links_parser.links
        return self.cache[identifier]

    def fetch_candidates(
        self, identifier: str, env: dict[str, str], extras: set[str]
    ) -> list[PyPICandidate]:
        """Return a list of candidates for a given package, env and list of extras.

        :param identifier: a normalized python package name or internal identifier
            computed by the provider
        :param env: the pip environment required
        :param extras: set of needed extras
        """
        if identifier not in self.candidate_cache:
            self.candidate_cache[identifier] = []
            project_links = self.fetch_project_links(identifier.split("@", 1)[0])
            for link in project_links:
                try:
                    c = PyPICandidate(
                        identifier=identifier.split("@", 1)[0],
                        link=link,
                        extras=extras,
                        cache_dir=os.path.join(self.cache_dir, "resources"),
                    )
                    # Discard prerelease unless explicitely allowed
                    if (
                        c.version.is_prerelease
                        and c.name not in self.allowed_prerelease
                    ):
                        continue

                    # Discard yanked releases unless explicitely allowed
                    if c.is_yanked and c.name not in self.allowed_yanked:
                        continue

                    self.candidate_cache[identifier].append(c)
                except InvalidVersion:
                    continue
        return self.candidate_cache[identifier]

    def save_cache(self) -> None:
        """Dump cache to disk."""
        mkdir(self.cache_dir)
        with open(self.pypi_cache_file, "w") as fd:
            fd.write(
                json.dumps(
                    {k: [el.as_dict() for el in v] for k, v in self.cache.items()},
                    indent=2,
                )
            )

    def load_cache(self) -> None:
        """Load cache from disk."""
        if os.path.isfile(self.pypi_cache_file):
            with open(self.pypi_cache_file) as fd:
                self.cache = {
                    k: [PyPILink.from_dict(el) for el in v]
                    for k, v in json.load(fd).items()
                }


class PyPICandidate:
    def __init__(
        self,
        identifier: str,
        link: PyPILink,
        extras: set[str],
        cache_dir: str,
    ) -> None:
        """Initialize a Candidate.

        :param identifier: the identifier on PyPI
        :param link: data return by PyPI simple API
        :param extras: list of extras that should be included
        :param cache_dir: cache location in which resources are downloaded
        """
        self.name = canonicalize_name(identifier)
        self.url = link.url
        self.is_yanked = link.is_yanked
        self.has_direct_metadata = link.has_metadata
        self.extras = set(extras)
        self.cache_dir = os.path.abspath(cache_dir)

        # Compute filename and extract compatibility information
        self.filename = link.filename

        self.version = link.pkg_version
        self.py_tags = link.pkg_py_tags
        self.abi_tags = link.pkg_abi_tags
        self.platform_tags = link.pkg_platform_tags

        # Requirements cache
        self._reqs: None | set[Requirement] = None

    @property
    def is_wheel(self) -> bool:
        """Check if resource is a wheel."""
        return self.filename.endswith(".whl")

    def download(self) -> str:
        """Download the file in the PyPI cache.

        :return: the location of the file
        """
        download_path = os.path.join(self.cache_dir, self.filename)
        if not os.path.isfile(download_path):
            mkdir(self.cache_dir)
            if self.url.startswith("file://"):
                cp(self.url.replace("file://", "", 1), download_path)
            else:
                answer = requests.get(self.url, stream=True)
                with open(download_path, "wb") as fd:
                    fd.write(answer.content)
        return download_path

    def requirements(self, env: dict[str, str]) -> set[Requirement]:
        """Return the list of requirements for the package.

        :param env: the environment used to evaluate requirements markers
        :return: a set of Requirement
        """
        # Make a copy of the env as the function modifies it on the fly
        env = dict(env)

        # Check if the requirements have already been computed
        if self._reqs is None:
            self._reqs = set()

            if self.is_wheel:
                # This is a wheel so there is a formal way to get the metadata.
                wheel_path = self.download()
                self._reqs |= Wheel(path=wheel_path).requirements

            elif self.filename.endswith(".tar.gz"):
                # This is a .tar.gz archive so we might find some info about the
                # requirements either in the egg-info data for older packages or
                # as fallback in a requirements.txt file.
                path = self.download()
                with tarfile.open(name=path, mode="r:gz") as fd:
                    egg_info = f"{self.filename[:-7]}/{self.name}.egg-info"
                    egg_info_requires = f"{egg_info}/requires.txt"
                    requirements_txt = f"{self.filename[:-7]}/requirements.txt"
                    archive_members = fd.getnames()

                    if egg_info in archive_members:
                        # If we have egg-info data without requires.txt it means the
                        # package has no dependencies.
                        if egg_info_requires in archive_members:
                            file_fd = fd.extractfile(egg_info_requires)
                            assert file_fd is not None
                            requires = file_fd.read().decode("utf-8")
                            current_marker = ""
                            for line in requires.splitlines():
                                line = line.strip()

                                if line.startswith("[:") and line.endswith("]"):
                                    # In requires.txt format markers are set using
                                    # sections
                                    current_marker = line[2:-1]
                                elif line and not line.startswith("#"):
                                    # Non empty lines that are not comments should be
                                    # considered as requirements
                                    if current_marker:
                                        self._reqs.add(
                                            Requirement(f"{line};{current_marker}")
                                        )
                                    else:
                                        # Don't emit a final ; if the marker is empty
                                        # as this is not accepted by the syntax
                                        self._reqs.add(Requirement(line))

                    elif requirements_txt in archive_members:
                        # Check if there is a requirements.txt (this is a fallback)
                        file_fd = fd.extractfile(requirements_txt)
                        assert file_fd is not None
                        requires = file_fd.read().decode("utf-8")
                        self._reqs |= {
                            Requirement(line.strip()) for line in requires.splitlines()
                        }

                    else:
                        logger.warning(
                            f"Cannot follow dependencies of package {self.name}"
                        )

        # Once we have the complete list of requirements, use the env to filter
        # out requirements not needed for the current configuration. Don't cache that
        # result as it depends on the current environment.
        reqs: set[Requirement] = set()

        if self.extras:
            # Special handling for extras. An additional dependencies is added
            # to the package itself without extras
            for extra in self.extras:
                env["extra"] = extra
                for r in self._reqs:
                    if r.marker is not None and r.marker.evaluate(env):
                        reqs.add(r)
            reqs.add(Requirement(f"{self.name} == {self.version}"))
        else:
            for r in self._reqs:
                if r.marker is None or r.marker.evaluate(env):
                    reqs.add(r)
        return reqs

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
        return result

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

    def __repr__(self) -> str:
        return f"{self.name}@{self.version} ({self.filename})"

    def __str__(self) -> str:
        return f"{self.name}@{self.version} ({self.filename})"


class PyPIProvider(AbstractProvider):
    """Class that should declared to instanciate a resolver (see resolvelib doc)."""

    def __init__(self, env: dict[str, str], pypi: PyPI):
        """Initialize the provider.

        :param env: a pip environment selected packages should match
        :param pypi: an interface object to PyPI
        """
        super().__init__()
        self.pypi = pypi
        self.env = env

    def identify(self, requirement_or_candidate: Requirement | PyPICandidate) -> str:
        """See resolvelib documentation."""
        result: str = canonicalize_name(requirement_or_candidate.name)
        if requirement_or_candidate.extras:
            result += "@" + ",".join(sorted(requirement_or_candidate.extras))
        return result

    def get_preference(
        self,
        identifier: str,
        resolutions: Mapping[str, PyPICandidate],
        candidates: Mapping[str, Iterator[PyPICandidate]],
        information: Mapping[Any, Iterator[RequirementInformation[Any, Any]]],
        backtrack_causes: Sequence[RequirementInformation],
    ) -> Preference:
        """See resolvelib documentation."""
        return sum(1 for _ in candidates[identifier])

    def find_matches(
        self,
        identifier: str,
        requirements: Mapping[str, Iterator[Requirement]],
        incompatibilities: Mapping[str, Iterator[PyPICandidate]],
    ) -> Matches:
        """Return the list of candidates that match a given list of requirements."""
        # Get requirements that must be satisfied
        reqs = list(requirements[identifier])

        extras = set()
        for r in reqs:
            extras |= r.extras

        # And discarded versions
        incomps = {c.version for c in incompatibilities[identifier]}

        # Fetch the list of releases for the given package
        candidates = self.pypi.fetch_candidates(identifier, env=self.env, extras=extras)
        result = []

        version_has_wheel = {}
        for c in candidates:
            if c.filename.endswith(".whl"):
                version_has_wheel[c.version] = True

        for candidate in candidates:
            if not candidate.filename.endswith(".whl"):
                if version_has_wheel.get(candidate.version):
                    # If a wheel is present for the candidate specific version,
                    # don't use sdist files to fetch dependencies.
                    continue

                elif not candidate.filename.endswith(".tar.gz"):
                    # Only .tar.gz archive are considered for sdist files
                    continue

            if candidate.version in incomps:
                continue

            match_all = True
            for r in reqs:
                if candidate.version not in r.specifier:
                    match_all = False
                    continue

            if match_all:
                result.append(candidate)

        return sorted(result, key=attrgetter("version"), reverse=True)

    def is_satisfied_by(
        self, requirement: Requirement, candidate: PyPICandidate
    ) -> bool:
        """See resolvelib documentation."""
        if canonicalize_name(requirement.name) != candidate.name:
            return False
        return candidate.version in requirement.specifier

    def get_dependencies(self, candidate: PyPICandidate) -> Iterable[Requirement]:
        """See resolvelib documentation."""
        return candidate.requirements(env=self.env)


class PyPIClosure:
    """Represent a closure of Python package from PyPI."""

    def __init__(
        self,
        *,
        python3_version: str,
        platforms: list[str],
        cache_dir: str,
        pypi_url: str = "https://pypi.org/",
        allowed_prerelease: list[str] | None = None,
        allowed_yanked: list[str] | None = None,
    ) -> None:
        """Initialize a PyPI session.

        :param python3_version: python 3 minor version (i.e: for 3.9.1 it's 9)
        :param platforms: the list of platforms for which packages should be considered
        :param cache_dir: a cache directory used to store wheels and sources
        :param pypi_url: set Python package registry URL. Default is PyPI
        :param allowed_prerelease: list of package names authorized to be into
            pre-release.
        :param allowed_yanked: list of package names authorized to have yanked flags set
            to true (see: PEP_592).
        """
        # Pypi database
        self.pypi = PyPI(pypi_url, allowed_yanked=allowed_yanked, cache_dir=cache_dir)
        self.requirements: set[Requirement] = set()
        self.allowed_prerelease = allowed_prerelease or []
        self.allowed_yanked = allowed_yanked or []
        self.platforms = platforms
        self.python3_version = Version(python3_version)
        self.pypi.load_cache()

    def add_wheel(self, filename: str) -> None:
        """Introduce a local wheel into the closure."""
        name = os.path.basename(filename)[:-4].split("-")[0]
        self.pypi.cache[canonicalize_name(name)] = [
            PyPILink(
                identifier=name,
                url=f"file://{os.path.abspath(filename)}".replace("\\", "/"),
                yanked=None,
                has_metadata=False,
            )
        ]

    def add_requirement(self, req: str | Requirement) -> None:
        """Add a requirement in the closure."""
        if isinstance(req, str):
            req = Requirement(req)
        self.requirements.add(req)

    def file_closure(self) -> list[str]:
        reqs = self._requirements_closure()
        result = set()

        for req in reqs:

            # First check if there is a generic wheel present or no. If there is
            # one then there is no need to package the sources.
            has_generic_wheel = any(
                (
                    c
                    for c in self.pypi.candidate_cache[canonicalize_name(req.name)]
                    if c.is_generic_wheel and c.version in req.specifier
                )
            )

            for candidate in self.pypi.candidate_cache[canonicalize_name(req.name)]:
                # Skip source files if we have a generic wheel
                if has_generic_wheel and not candidate.is_wheel:
                    continue

                if candidate.version in req.specifier:
                    if candidate.is_compatible_with_cpython3(
                        int(self.python3_version.minor)
                    ) and candidate.is_compatible_with_platforms(self.platforms):
                        result.add(candidate)
                        candidate.download()
        return [os.path.join(el.cache_dir, el.filename) for el in result]

    def _requirements_closure(self) -> dict:
        all_reqs: dict[Requirement, set[str]] = {}
        for platform in self.platforms:
            provider = PyPIProvider(
                get_pip_env(platform, python_version=self.python3_version), self.pypi
            )
            reporter: BaseReporter = BaseReporter()
            resolver: Resolver = Resolver(provider, reporter)
            try:
                result = resolver.resolve(self.requirements, max_rounds=500)
            except ResolutionImpossible as e:
                raise PyPIError(f"Impossible resolution: {e}") from e

            for name, candidate in result.mapping.items():
                # Skip intermediate nodes introduced to handle extras
                if "@" in name:
                    continue

                base_req = Requirement(f"{name} == {candidate.version}")
                if base_req not in all_reqs:
                    all_reqs[base_req] = set()
                all_reqs[base_req].add(platform)

        return all_reqs

    def requirements_closure(self) -> list[Requirement]:
        """Get the closure of requirements.

        :return: return a list of requirement that can be used as a lock file
        """
        all_reqs = self._requirements_closure()
        reqs = set()
        for k, v in all_reqs.items():
            if len(v) == len(self.platforms):
                reqs.add(k)
            else:
                for p in v:
                    sys_platform = get_pip_env(p, self.python3_version)["sys_platform"]
                    reqs.add(Requirement(f'{k}; sys_platform == "{sys_platform}"'))
        return sorted(reqs, key=lambda r: r.name)

    def __enter__(self) -> PyPIClosure:
        return self

    def __exit__(
        self,
        _type: type[BaseException] | None,
        _val: BaseException | None,
        _tb: TracebackType | None,
    ) -> None:
        self.pypi.save_cache()


def fetch_from_registry(
    packages: Iterable[str], registry_url: str, *, log_missing_packages: bool = False
) -> dict[str, PyPILink]:
    """Fetch packages currently in a registry.

    :param packages: The list of packages to look for.
    :param registry_url: The URL to a python registry to use.
        If the protocol is not defined on the URL, https will be used by default.
    :return: A filename to link mapping (dict).
    """
    url = (
        f"https://{registry_url}"
        if not registry_url.startswith("http")
        else registry_url
    )

    registry = PyPI(url)
    res: dict[str, PyPILink] = {}
    for p in packages:
        try:
            res.update(
                {link.filename: link for link in registry.fetch_project_links(p)}
            )
        except HTTPError as err:
            if err.response.status_code != 404:  # if other than NotFound
                raise err
            if log_missing_packages:
                logger.error(f"Package {p!r} is missing on the given registry")
    return res
