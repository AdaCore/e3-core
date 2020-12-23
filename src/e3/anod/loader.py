from __future__ import annotations

import inspect
import os
import sys
import types
import yaml

from typing import TYPE_CHECKING

import e3.hash
import e3.log
from e3.anod.error import SandBoxError
from e3.anod.spec import __version__
from e3.fs import ls

logger = e3.log.getLogger("anod.loader")

if TYPE_CHECKING:
    from typing import Any, Callable, Dict, List, Optional
    from types import ModuleType
    from e3.anod.spec import Anod


class SpecConfig:
    """Contain specification files configuration.

    :ivar spec_dir: path to the anod specs
    :ivar repositories: dict containing the list of repositories metadata
        (content of config/repositories)
    """

    def __init__(self) -> None:
        # Both values are set by AnodSpecRepository init
        self.spec_dir = ""
        self.repositories: Dict[str, Any] = {}


class AnodSpecRepository:
    """Anod spec repository.

    :ivar specs: A dictionary of AnodModule objects, indexed by spec name
        (without the spec filename's extension).
    :vartype specs: dict[e3.anod.loader.AnodModule]

    The object represent a set of anod specifications along with their data
    files.
    """

    def __init__(
        self,
        spec_dir: str,
        spec_config: Any = None,
        # Ideally should be spec_config: Optional[SpecConfig] = None,
        # We keep it to Any to avoid mypy issues on other projects
        extra_repositories_config: Optional[dict] = None,
    ):
        """Initialize an AnodSpecRepository.

        :param spec_dir: directory containing the anod specs.
        :param spec_config: dictionary containing the configuration for this
            AnodSpecRepository
        :param extra_repositories_config: first read the configuration from
            <spec_dir>/config/repositories.yaml and update the result with
            extra_repositories_config
        """
        logger.debug("initialize spec repository (%s)", spec_dir)

        if not os.path.isdir(spec_dir):
            raise SandBoxError(f"spec directory {spec_dir} does not exist")
        self.spec_dir = spec_dir
        self.api_version = __version__
        self.specs = {}
        self.repos: Dict[str, Dict[str, str]] = {}

        # Look for all spec files and data files
        spec_list = {
            os.path.basename(os.path.splitext(k)[0]): {"path": k, "data": []}
            for k in ls(os.path.join(self.spec_dir, "*.anod"), emit_log_record=False)
        }
        logger.debug("found %s specs", len(spec_list))

        # API == 1.4
        yaml_files = ls(os.path.join(self.spec_dir, "*.yaml"), emit_log_record=False)
        data_list = [os.path.basename(k)[:-5] for k in yaml_files]
        logger.debug("found %s yaml files API 1.4 compatible", len(data_list))

        # Match yaml files with associated specifications
        for data in data_list:
            candidate_specs = [
                spec_file for spec_file in spec_list if data.startswith(spec_file)
            ]
            # We pick the longuest spec name
            candidate_specs.sort(key=len)
            if candidate_specs:
                spec_list[candidate_specs[-1]]["data"].append(data)  # type: ignore

        # Find yaml files that are API >= 1.5 compatible
        new_yaml_files = ls(
            os.path.join(self.spec_dir, "*", "*.yaml"), emit_log_record=False
        )

        for yml_f in new_yaml_files:
            associated_spec = os.path.basename(os.path.dirname(yml_f))

            # Keep only the yaml files associated with an .anod file
            if associated_spec in spec_list:
                # We're recording the relative path without the extension
                suffix, _ = os.path.splitext(os.path.basename(yml_f))

                spec_list[associated_spec]["data"].append(  # type: ignore
                    os.path.join(associated_spec, suffix)
                )

        # Create AnodModule objects
        for name, value in spec_list.items():
            self.specs[name] = AnodModule(name, **value)  # type: ignore

        # Load config/repositories.yaml
        repo_file = os.path.join(self.spec_dir, "config", "repositories.yaml")
        if os.path.isfile(repo_file):
            with open(repo_file) as fd:
                self.repos = yaml.safe_load(fd)

        if extra_repositories_config:
            for repo_name, repo_data in extra_repositories_config.items():
                if repo_name in self.repos:
                    self.repos[repo_name].update(repo_data)
                else:
                    self.repos[repo_name] = repo_data

        # Make sure that all revision are strings and not floats
        for repo_conf in self.repos.values():
            if "revision" in repo_conf:
                repo_conf["revision"] = str(repo_conf["revision"])

        if spec_config is None:
            spec_config = SpecConfig()
        spec_config.spec_dir = self.spec_dir
        spec_config.repositories = self.repos

        # Declare spec prolog
        prolog_file = os.path.join(spec_dir, "prolog.py")
        self.prolog_dict = {"spec_config": spec_config, "__spec_repository": self}
        if os.path.exists(prolog_file):
            with open(prolog_file) as f:
                exec(compile(f.read(), prolog_file, "exec"), self.prolog_dict)

    def __contains__(self, item: str) -> bool:
        """Check by name if a spec is present in the repository.

        :return: True if present, False otherwise
        """
        return item in self.specs and self.specs[item].module is not None

    def load_all(self, ignore_errors: bool = False) -> None:
        """Load all the specs present in the repository.

        :param ignore_errors: if True don't stop on error.
        """
        for name in self.specs:
            try:
                self.specs[name].load(self)
            except SandBoxError:
                if not ignore_errors:
                    raise

    def load(self, name: str) -> Callable[..., Anod]:
        """Load an anod spec and return the corresponding Anod class.

        :param name: name of the spec to load
        """
        assert name in self.specs, f"spec {name} not found"
        return self.specs[name].load(self)


class AnodModule:
    def __init__(self, name: str, path: str, data: List[str]):
        """Initialize an AnodModule instance.

        :param name: module name
        :param path: path to the spec
        :param data: list of data files (yaml files) associated with the spec
        """
        self.name = name
        self.data = data
        self.path = path
        self.module: Optional[ModuleType] = None
        self.anod_class: Optional[Callable[..., Anod]] = None
        self.checksum = e3.hash.sha1(self.path)

    @property
    def is_loaded(self) -> bool:
        """Check if a spec is already loaded.

        :return: True if the spec is already loaded, False otherwise
        """
        return self.module is not None

    def load(self, repository: AnodSpecRepository) -> Callable[..., Anod]:
        """Load an anod specification and return the corresponding Anod class.

        :param repository: the anod spec repository of the spec file
        :raise SandBoxError: in case of failure
        """
        if self.is_loaded:
            if TYPE_CHECKING:
                assert self.anod_class is not None
            return self.anod_class

        logger.debug("loading anod spec: %s", self.name)

        # Create a new module
        mod_name = "anod_" + self.name
        anod_module = types.ModuleType(mod_name)

        try:
            with open(self.path) as fd:
                # Inject the prolog into the new module dict
                anod_module.__dict__.update(repository.prolog_dict)

                # Exec spec code
                code = compile(fd.read(), self.path, "exec")
                exec(code, anod_module.__dict__)
        except Exception as e:
            logger.error("exception: %s", e)
            logger.error("cannot load code of %s", self.name)
            raise SandBoxError(
                origin="load", message=f"invalid spec code for {self.name}"
            ).with_traceback(sys.exc_info()[2])

        # At this stage we have loaded completely the module. Now we need to
        # look for a subclass of Anod. Use python inspection features to
        # achieve this.

        for members in inspect.getmembers(anod_module):
            _, value = members
            # Return the first subclass of Anod defined in this module
            if (
                inspect.isclass(value)
                and value.__module__ == mod_name
                and "Anod" in (k.__name__ for k in value.__mro__)
            ):
                # Reject class named "Anod" this is reserved to the base
                # class and can cause some issues when reused
                if value.__name__ == "Anod":
                    raise SandBoxError(
                        f"{self.name}.anod must not use Anod as a class name", "load"
                    )

                # This class is a child of Anod so register it.
                # Note that even if we won't use directly the
                # module we need to keep a reference on it in order
                # to avoid garbage collector issues.
                value.spec_checksum = self.checksum

                # Give a name to our Anod class: the basename of the
                # anod spec file (without the .anod extension)
                value.name = self.name
                self.anod_class = value
                self.module = anod_module
                self.anod_class.data_files = self.data  # type: ignore
                self.anod_class.spec_dir = os.path.dirname(self.path)  # type: ignore
                self.anod_class.api_version = repository.api_version  # type: ignore
                return value

        logger.error(f"spec {self.name} does not contains an Anod subclass")
        raise SandBoxError(f"cannot find Anod subclass in {self.path}", "load")


def spec(name: str) -> Callable[..., Anod]:
    """Load an Anod spec class.

    Note that two spec having the same name cannot be loaded in the same
    process as e3 keeps a cache of loaded spec using the spec basename as a
    key.
    :param name: name of the spec to load
    """
    spec_repository: Optional[AnodSpecRepository] = None
    for k in inspect.stack()[1:]:
        if "__spec_repository" in k[0].f_globals:
            spec_repository = k[0].f_globals["__spec_repository"]
            break

    assert spec_repository is not None
    return spec_repository.load(name)
