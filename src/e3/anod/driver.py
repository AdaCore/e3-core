from __future__ import annotations

import sys
from functools import wraps
from typing import TYPE_CHECKING

import e3.log
import e3.store
from e3.anod.spec import AnodError, has_primitive
from e3.env import BaseEnv
from e3.error import E3Error

logger = e3.log.getLogger("e3.anod.driver")

if TYPE_CHECKING:
    from typing import Any, Callable, Literal, TypeVar
    from e3.anod.spec import Anod
    from e3.store.backends.base import Store
    from e3.anod.sandbox import SandBox
    from e3.anod.loader import AnodSpecRepository

    F = TypeVar("F", bound=Callable[..., Any])


def primitive_check() -> Callable[[F], F]:
    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            if not has_primitive(self.anod_instance, func.__name__):
                raise AnodError(f"no primitive {func.__name__}")
            elif self.anod_instance.build_space is None:
                raise AnodError(".activate() has not been called")
            return func(self, *args, **kwargs)

        return wrapper  # type: ignore

    return decorator


class AnodDriver:
    def __init__(self, anod_instance: Anod, store: Store):
        """Initialize the Anod driver for a given Anod instance.

        :param anod_instance: an Anod instance
        :param store: the store backend for accessing source and
            binary packages
        """
        self.anod_instance = anod_instance
        self.store = store

    def activate(self, sandbox: SandBox, spec_repository: AnodSpecRepository) -> None:
        self.anod_instance.bind_to_sandbox(sandbox)

        self.anod_instance.log = e3.log.getLogger("spec." + self.anod_instance.uid)

        for e in getattr(self.anod_instance, f"{self.anod_instance.kind}_deps", ()):
            if isinstance(e, self.anod_instance.Dependency):
                dep_class = spec_repository.load(e.name)
                dep_instance = dep_class(
                    qualifier=e.qualifier,
                    kind=e.kind,
                    env=e.env(self.anod_instance, BaseEnv.from_env()),
                )
                self.anod_instance.deps[e.local_name] = dep_instance
        e3.log.debug("activating spec %s", self.anod_instance.uid)

    def call(self, action: str) -> Any:
        """Call an Anod action.

        :param action: the action (build, install, test, ...)
        """
        return getattr(self, action, self.unknown_action)()

    @staticmethod
    def unknown_action() -> Literal[False]:
        logger.critical("unknown action")
        return False

    @primitive_check()
    def download(self):
        """Run the download primitive."""
        # First check whether there is a download primitive implemented by
        # the Anod spec.
        self.anod_instance.build_space.create(quiet=True)
        download_data = self.anod_instance.download()
        if download_data is None:
            raise AnodError("no download metadata returned by the download primitive")
        try:
            metadata = self.store.get_resource_metadata(download_data)
        except E3Error as err:
            self.anod_instance.log.critical(err)
            raise AnodError(
                "cannot get resource metadata from store", origin=self.anod_instance.uid
            ).with_traceback(sys.exc_info()[2])
        else:
            self.store.download_resource(
                metadata, self.anod_instance.build_space.binary_dir
            )
