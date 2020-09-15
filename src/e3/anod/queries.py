"""Provides high level queries on Anod specs."""
from __future__ import annotations

import collections
from typing import overload, TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any, Callable, Dict, List, NamedTuple, Optional, Tuple
    from e3.anod.spec import Anod
    from e3.anod.context import AnodContext
    from e3.anod.package import SourceBuilder

    class SourceKey(NamedTuple):
        anod_uid: str
        src_name: str
        publish: bool

    class PackageKey(NamedTuple):
        anod_uid: str
        track: bool
        has_closure: bool


else:
    SourceKey = collections.namedtuple("SourceKey", ["anod_uid", "src_name", "publish"])
    PackageKey = collections.namedtuple(
        "PackageKey", ["anod_uid", "track", "has_closure"]
    )


@overload
def get_build_node(
    anod_instance: Anod, context: AnodContext, default: None = None
) -> Optional[Anod]:
    ...


@overload
def get_build_node(anod_instance: Anod, context: AnodContext, default: Anod) -> Anod:
    ...


def get_build_node(
    anod_instance: Anod, context: AnodContext, default: Optional[Anod] = None
) -> Optional[Anod]:
    """Return the build anod instance corresponding to an install.

    :param anod_instance: an Anod instance
    :param context: Anod context
    :param default: value returned if the build Anod instance does not exist
    :return: the associated build anod instance. If such instance does not
        exist then return default
    """
    if anod_instance.kind != "install":
        return default

    elif anod_instance.uid[:-8] + ".build" in context.tree:
        return context[anod_instance.uid[:-8] + ".build"].anod_instance  # type: ignore
    else:
        return default


def get_source_builder(
    anod_instance: Anod, source_name: str, local_sources_only: bool = False
) -> Optional[SourceBuilder]:
    """Given a source name return the associated builder.

    :param anod_instance: an Anod instance
    :param source_name: a source name
    :param local_sources_only: if True consider only builders declared in the
        spec itself. if False also consider source builders in source
        dependencies (i.e: require='source_pkg')
    :return: a source builder or None if no builder can be found.
    """
    # First look locally
    builder = None

    if anod_instance.source_pkg_build is not None:
        builder = next(
            (b for b in anod_instance.source_pkg_build if b.name == source_name), None
        )

    if builder is None and not local_sources_only:
        # If needed look into the deps
        for dep in list(anod_instance.deps.values()):
            if dep.kind != "source":
                continue
            builder = get_source_builder(dep, source_name, local_sources_only=True)
            if builder is not None:
                break
    return builder


class SourceClosure:
    """Helper object to resolve source closure for a given spec instance."""

    def __init__(
        self,
        anod_instance: Anod,
        context: AnodContext,
        expand_packages: bool = False,
        data_key: Optional[Callable[[Any], str]] = None,
    ):
        """Initialize a SourceClosure.

        :param anod_instance: an Anod instance
        :param context: the Anod context in which anod_instance was created
        :param expand_packages: whether to attempt to find source closure for
            installation dependencies which are producing a package
        :param data_key: function that given a data associated to a source
            return a key. By default __hash__ is used.
        """
        self.anod_instance = anod_instance
        self.expand_packages = expand_packages
        self.context = context
        self.source_list: Dict[SourceKey, Optional[Any]] = {}
        self.package_list: Dict[PackageKey, Optional[Any]] = {}
        self.compute_closure(self.anod_instance, publish=True)
        self.data_key = data_key
        if self.data_key is None:
            self.data_key = lambda x: x.__hash__()

    def compute_closure(self, spec: Anod, publish: bool) -> None:
        """Compute the source closure (internal function).

        :param spec: an anod instance to inspect
        :param publish: whether the sources found should be marked internal
            or not.
        """
        # If this is an installation add the corresponding package
        if spec.kind == "install":
            has_closure = get_build_node(spec, self.context) is not None
            self.package_list[PackageKey(spec.uid, publish, has_closure)] = None
            return

        # Otherwise consider the sources and recursively iterate on the
        # dependencies.
        for source in getattr(spec, f"{spec.kind}_source_list", []):
            publish_source = publish and source.publish
            self.source_list[SourceKey(spec.uid, source.name, publish_source)] = None

        # Follow dependencies
        for dep, dep_spec in list(self.context.dependencies[spec.uid].values()):

            # Only consider build and install dependency (discard source deps)
            if dep.kind in ("build", "install"):
                if dep_spec.kind == "install":
                    # An install dep should be expanded whenever
                    # expand_packages is defined or when there is no component
                    # information generated (i.e: when dep_spec.component is
                    # None)
                    if self.expand_packages or dep_spec.component is None:
                        dep_spec = get_build_node(
                            dep_spec, context=self.context, default=dep_spec
                        )
                self.compute_closure(dep_spec, publish and dep.track)

    def resolve_package(self, spec_uid: str, data: List[Tuple[Any, bool]]) -> None:
        """Associate source information to a given package.

        :param spec_uid: the anod uid
        :param data: list of data associated to the package. This is a list of
            tuples (src_data, publish). Where src_data is the data for a given
            source package and publish a boolean indicated whether the entry is
            internal or not.
        """
        for pkg_key in self.package_list:
            if pkg_key.anod_uid == spec_uid:
                self.package_list[pkg_key] = data

    def resolve_source(self, source_name: str, data: Any) -> None:
        """Associate source information to a given source.

        :param source_name: the source name. The closure resolution is
            done locally so we can assume that for all occurences of a
            given source name the same data should be associated
        :param data: data associated with the source
        """
        for src_key in self.source_list:
            if src_key.src_name == source_name:
                self.source_list[src_key] = data

    def get_source_list(self) -> List[List[Any]]:
        """Get the closure source list.

        The function return the list of data for the sources in the closure.
            Note that if a package present in the closure is both marked as
            untracked and that closure cannot be found then it is ignored.
            For any other source or package if no data is associated then
            an assert exception will be raised

        :return: a list of list (source, publish)
        """
        result: Dict[str, List[Any]] = {}
        for src_key, src in list(self.source_list.items()):
            assert src is not None, "missing resolution"
            if TYPE_CHECKING:
                assert self.data_key is not None
            result_key = self.data_key(src)
            result[result_key] = [
                src,
                result.get(result_key, (None, False))[1] or src_key.publish,
            ]

        for pkg_key, pkg in list(self.package_list.items()):
            if not pkg_key.has_closure and not pkg_key.track:
                continue
            assert pkg is not None, "missing resolution"

            for src, publish in pkg:
                if TYPE_CHECKING:
                    assert self.data_key is not None
                result_key = self.data_key(src)

                result[result_key] = [
                    src,
                    result.get(result_key, (None, False))[1]
                    or (publish and pkg_key.track),
                ]
        return list(result.values())
