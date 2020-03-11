"""Provides high level queries on Anod specs."""
import collections


def get_build_node(anod_instance, context, default=None):
    """Return the build anod instance corresponding to an install.

    :param anod_instance: an Anod instance
    :type anod_instance: Anod
    :param context: Anod context
    :type context: AnodContext
    :param default: value returned if the build Anod instance does not exist
    :type default: T
    :return: the associated build anod instance. If such instance does not
        exist then return default
    :rtype: Anod
    """
    if anod_instance.kind != "install":
        return default

    elif anod_instance.uid[:-8] + ".build" in context.tree:
        return context[anod_instance.uid[:-8] + ".build"].anod_instance
    else:
        return default


def get_source_builder(anod_instance, source_name, local_sources_only=False):
    """Given a source name return the associated builder.

    :param anod_instance: an Anod instance
    :type anod_instance: e3.anod.spec.Anod
    :param source_name: a source name
    :type source_name: str
    :param local_sources_only: if True consider only builders declared in the
        spec itself. if False also consider source builders in source
        dependencies (i.e: require='source_pkg')
    :type local_sources_only: bool
    :return: a source builder or None if no builder can be found.
    :rtype: e3.anod.package.SourceBuilder | None
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


class SourceClosure(object):
    """Helper object to resolve source closure for a given spec instance."""

    SourceKey = collections.namedtuple("SourceKey", ["anod_uid", "src_name", "publish"])
    PackageKey = collections.namedtuple(
        "PackageKey", ["anod_uid", "track", "has_closure"]
    )

    def __init__(self, anod_instance, context, expand_packages=False, data_key=None):
        """Initialize a SourceClosure.

        :param anod_instance: an Anod instance
        :type anod_instance: Anod
        :param context: the Anod context in which anod_instance was created
        :type context: AnodContext
        :param expand_packages: whether to attempt to find source closure for
            installation dependencies which are producing a package
        :type expand_packages: bool
        :param data_key: function that given a data associated to a source
            return a key. By default __hash__ is used.
        :type data_key: T -> str
        """
        self.anod_instance = anod_instance
        self.expand_packages = expand_packages
        self.context = context
        self.source_list = {}
        self.package_list = {}
        self.compute_closure(self.anod_instance, publish=True)
        self.data_key = data_key
        if self.data_key is None:
            self.data_key = lambda x: x.__hash__()

    def compute_closure(self, spec, publish):
        """Compute the source closure (internal function).

        :param spec: an anod instance to inspect
        :type spec: Anod
        :param publish: whether the sources found should be marked internal
            or not.
        :type publish: bool
        """
        # If this is an installation add the corresponding package
        if spec.kind == "install":
            has_closure = get_build_node(spec, self.context) is not None
            self.package_list[self.PackageKey(spec.uid, publish, has_closure)] = None
            return

        # Otherwise consider the sources and recursively iterate on the
        # dependencies.
        for source in getattr(spec, "%s_source_list" % spec.kind, []):
            publish_source = publish and source.publish
            self.source_list[
                self.SourceKey(spec.uid, source.name, publish_source)
            ] = None

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

    def resolve_package(self, spec_uid, data):
        """Associate source information to a given package.

        :param spec_uid: the anod uid
        :type spec_uid: str
        :param data: list of data associated to the package. This is a list of
            tuples (src_data, publish). Where src_data is the data for a given
            source package and publish a boolean indicated whether the entry is
            internal or not.
        :type data: list[(T, bool)]
        """
        for pkg_key in self.package_list:
            if pkg_key.anod_uid == spec_uid:
                self.package_list[pkg_key] = data

    def resolve_source(self, source_name, data):
        """Associate source information to a given source.

        :param source_name: the source name. The closure resolution is
            done locally so we can assume that for all occurences of a
            given source name the same data should be associated
        :type source_name: str
        :param data: data associated with the source
        :type data: T
        """
        for src_key in self.source_list:
            if src_key.src_name == source_name:
                self.source_list[src_key] = data

    def get_source_list(self):
        """Get the closure source list.

        The function return the list of data for the sources in the closure.
            Note that if a package present in the closure is both marked as
            untracked and that closure cannot be found then it is ignored.
            For any other source or package if no data is associated then
            an assert exception will be raised

        :return: a list of tuples (source, publish)
        :rtype: list[(T, bool)]
        """
        result = {}
        for key, src in list(self.source_list.items()):
            assert src is not None, "missing resolution"
            result_key = self.data_key(src)
            result[result_key] = [
                src,
                result.get(result_key, (None, False))[1] or key.publish,
            ]

        for key, pkg in list(self.package_list.items()):
            if not key.has_closure and not key.track:
                continue
            assert pkg is not None, "missing resolution"

            for src, publish in pkg:
                result_key = self.data_key(src)

                result[result_key] = [
                    src,
                    result.get(result_key, (None, False))[1] or (publish and key.track),
                ]
        return list(result.values())
