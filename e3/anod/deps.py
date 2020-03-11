import collections

import e3.anod.error
from e3.env import BaseEnv


class BuildVar(object):
    """Declare a dependency between an Anod spec and a variable."""

    def __init__(self, name, value):
        """Initialize a BuildVar object.

        :param name: name of the variable
        :type name: str
        :param value: variable value
        :type value: collections.Hashable
        """
        assert isinstance(value, collections.Hashable)
        self.name = name
        self.value = value
        self.kind = "var"

    def __str__(self):
        return "%s=%s" % (self.name, self.value)


class Dependency(object):
    def __init__(
        self,
        name,
        product_version=None,
        host=None,
        target=None,
        build=None,
        qualifier=None,
        local_name=None,
        require="build_tree",
        track=False,
        **kwargs
    ):
        """Initialize a Dependency object.

        :param name: basename of the Anod spec file (without .anod extension)
        :type name: str
        :param product_version: product version to force when loading the spec
        :type product_version: str | None
        :param host: can be either 'target' or 'build'. If set to 'target' then
            it means that the dependency will be loaded with host set to
            the current module target information. If set to 'build' then
            similar mechanism is used with the current module 'build'
            platform.
        :type host: str | None
        :param target: can be either 'host' or 'build'
        :type target: str | None
        :param build: build platform (if not the current build platform), the
            special value "default" change the build platform to the default
            build platform. Note that on windows, the default is always
            x86-windows.
        :type build: str | None
        :param qualifier: qualifier to set when loading the spec
        :type qualifier: str | None
        :param local_name: if not None, this name will be the dependency key
            in deps and makedeps dictionaries. It allows importing twice
            the same anod module with different qualifers or platforms
        :type local_name: str | None
        :param require: can be 'build_tree' (to force a local build),
            'installation' or 'source_pkg'
        :type require: str
        :param track: if True, track all source packages metadata and include
            them in the local metadata.
        :type track: bool
        :param kwargs: other parameters valid in some API that we ignore now
        :type kwargs: dict
        """
        del kwargs
        self.name = name
        self.product_version = product_version
        self.host = host
        self.target = target
        self.build = build
        self.qualifier = qualifier
        self.local_name = local_name if local_name is not None else name
        self.kind = None
        if require not in ("build_tree", "installation", "source_pkg"):
            raise e3.anod.error.SpecError(
                "require should be build_tree, installation or source_pkg"
                " not %s." % require
            )
        self.kind = {
            "build_tree": "build",
            "installation": "install",
            "source_pkg": "source",
        }[require]
        self.track = track

    def env(self, parent, default_env):
        """Retrieve env for the dependency.

        :param parent: Anod instance in which the dep was declared
        :type parent: Anod
        :param default_env: default env for the current context
        :type default_env: BaseEnv
        :return: env object that should be used by the dependency
        :rtype: BaseEnv
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
