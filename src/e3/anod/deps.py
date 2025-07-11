from __future__ import annotations

import collections.abc
from typing import TYPE_CHECKING

import e3.anod.error
import e3.log
from e3.anod import qualifier_str_to_dict
from e3.env import BaseEnv


if TYPE_CHECKING:
    from typing import Any, Hashable, Literal
    from e3.anod.spec import Anod, DEPENDENCY_PRIMITIVE

logger = e3.log.getLogger("e3.anod.deps")


class BuildVar:
    """Declare a dependency between an Anod spec and a variable."""

    def __init__(self, name: str, value: Hashable):
        """Initialize a BuildVar object.

        :param name: name of the variable
        :param value: variable value
        """
        assert isinstance(value, collections.abc.Hashable)
        self.name = name
        self.value = value
        self.kind = "var"

    def __str__(self) -> str:
        return f"{self.name}={self.value}"


class Dependency:
    kind: DEPENDENCY_PRIMITIVE

    ALLOWED_REQUIRE: dict[str, str] = {
        "build_tree": "build",
        "download": "download",
        "installation": "install",
        "source_pkg": "source",
        "test": "test",
    }

    def __init__(
        self,
        name: str,
        product_version: str | None = None,
        host: str | None = None,
        target: str | None = None,
        build: str | None = None,
        qualifier: str | None | dict[str, str | bool | frozenset] = None,
        local_name: str | None = None,
        require: (
            Literal["build_tree"]
            | Literal["installation"]
            | Literal["download"]
            | Literal["source_pkg"]
            | Literal["test"]
        ) = "build_tree",
        track: bool = False,
        **kwargs: Any,
    ) -> None:
        """Initialize a Dependency object.

        :param name: basename of the Anod spec file (without .anod extension)
        :param product_version: product version to force when loading the spec
        :param host: can be either 'target' or 'build'. If set to 'target' then
            it means that the dependency will be loaded with host set to
            the current module target information. If set to 'build' then
            similar mechanism is used with the current module 'build'
            platform.
        :param target: can be either 'host' or 'build'
        :param build: build platform (if not the current build platform), the
            special value "default" change the build platform to the default
            build platform. Note that on windows, the default is always
            x86-windows.
        :param qualifier: qualifier to set when loading the spec
        :param local_name: if not None, this name will be the dependency key
            in deps and makedeps dictionaries. It allows importing twice
            the same anod module with different qualifers or platforms
        :param require: can be 'build_tree' (to force a local build),
            'installation', 'download', or 'source_pkg'
        :param track: if True, track all source packages metadata and include
            them in the local metadata.
        :param kwargs: other parameters valid in some API that we ignore now
        """
        del kwargs
        self.name = name
        self.product_version = product_version
        self.host = host
        self.target = target
        self.build = build
        self.local_name = local_name if local_name is not None else name

        self.parsed_qualifier: dict

        if isinstance(qualifier, str):
            self.parsed_qualifier = qualifier_str_to_dict(qualifier)

        elif isinstance(qualifier, dict):
            # Ensure we get a copy as in that case qualifier is mutable
            self.parsed_qualifier = dict(qualifier)

        elif qualifier is None:
            self.parsed_qualifier = {}

        else:
            raise e3.anod.error.SpecError(f"invalid qualifier type: {qualifier}")

        if require in self.ALLOWED_REQUIRE:
            self.kind = self.ALLOWED_REQUIRE[require]  # type: ignore[assignment]
        else:
            raise e3.anod.error.SpecError(
                f"Invalid require parameter {require!r}. "
                f"Allowed values are {', '.join(self.ALLOWED_REQUIRE)}"
            )

        self.track = track

    def env(self, parent: Anod, default_env: BaseEnv) -> BaseEnv:
        """Retrieve env for the dependency.

        :param parent: Anod instance in which the dep was declared
        :param default_env: default env for the current context
        :return: env object that should be used by the dependency
        """
        # Get the current environment associated with the Anod instance
        # and adjust it based on dependency parameters
        dep_env = BaseEnv(parent.env.build, parent.env.host, parent.env.target)

        # For simulation purposes we sometimes load specs as if it was
        # loaded on a non local machine thus 'default' does not correspond
        # to the default build platform of the local machine.
        if self.build == "default":
            build = default_env.build.platform
        else:
            build = self.build

        if self.host == "default":
            host = default_env.build.platform
        else:
            host = self.host

        if self.target == "default":
            target = default_env.build.platform
        else:
            target = self.target

        dep_env.set_env(build, host, target)
        return dep_env
