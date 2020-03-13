"""Global environment and platform information support.

This package provide a class called Env used to store global
information. Env is a singleton so there is in fact only one instance.
"""


import abc
import os
import pickle
import sys

import e3.log
import e3.os.platform
from collections import namedtuple
from e3.platform import Platform

logger = e3.log.getLogger("env")


# This global variable contains a list of tuples
# (build platform, host platform) that should not be considered as canadian
# configurations.
CANADIAN_EXCEPTIONS = (
    ("x86-windows", "x86_64-windows"),
    ("sparc-solaris", "sparc64-solaris"),
)


EnvInfo = namedtuple("EnvInfo", ["build", "host", "target"])


class AbstractBaseEnv(object, metaclass=abc.ABCMeta):
    """Environment Handling.

    Abstract class to factorize code between BaseEnv and Env.
    :ivar build: current build Platform
    :vartype build: Platform
    :ivar host: current host Platform
    :vartype host: Platform
    :ivar target: current target Platform
    :vartype target: Platform
    :ivar main_options: The command-line switches, after parsing by
    the e3.Main class (see the documentation of that class).
    """

    @abc.abstractmethod
    def __init__(self, build=None, host=None, target=None):
        if not self._initialized:
            self.build = Platform.get() if build is None else build
            self.host = self.build if host is None else host
            self.target = self.host if target is None else target
            self.environ = None
            self.cwd = None
            self.main_options = None

    @abc.abstractproperty
    def _initialized(self):
        """Whether the new instance should be initialized.

        This is mostly useful to implement a singleton, as done in Env()
        :rtype: bool
        """
        pass  # all: no cover

    @abc.abstractmethod
    def _items(self):
        """Return the list of instance variables.

        :rtype: collections.Iterable
        """
        pass  # all: no cover

    @property
    def platform(self):
        """Compute the platform name based on the host and the target.

        For example for target ppc-elf hosted on linux, platform will
        be ppc-elf-linux. So the concept of platform embed both target
        and host concept.

        :rtype: str
        """
        if self.is_cross:
            # In cross we need to append host information. For backward
            # compatibility we don't append 64 to darwin host (which is
            # always 64bits).
            suffix = self.host.os.name
            if self.host.cpu.bits == 64 and self.host.os.name != "darwin":
                suffix += "64"
            return self.target.platform + "-" + suffix
        else:
            # In native concept the platform is equivalent to target.platform
            return self.target.platform

    @property
    def is_canadian(self):
        """Return true if this is a canadian configuration.

        :rtype: bool
        """
        if self.build != self.host:
            if (self.build.platform, self.host.platform) in CANADIAN_EXCEPTIONS:
                return False
            return True
        else:
            return False

    @property
    def is_cross(self):
        """Return true if this is a cross configuration.

        :rtype: bool
        """
        if self.target != self.host:
            return True
        else:
            return False

    def set_build(self, name=None, version=None, machine=None, mode=None):
        """Set build platform.

        :param name: a string that identify the system to be considered
            as the build. If None then build is unchanged. Note that passing
            an empty value will force the autodetection and possibly reset to
            the default value.
        :type name: str | None
        :param version: a string containing the system version. If set
            to None the version is either a default or autodetected when
            possible
        :type version: str | None
        :param machine: a string containing the name of the target
            machine.
        :type machine: str | None
        :param mode: a string containing the name of the mode. This
            notion is needed on some targets such as VxWorks to switch between
            kernel mode and other modes such as rtp

        When calling set_build, the target and host systems are reset to the
        build one. Thus you should call set_build before calling either
        set_host or set_target.
        """
        e3.log.debug("set_build (build_name=%s, build_version=%s)", name, version)
        self.build = Platform.get(
            platform_name=name, version=version, machine=machine, mode=mode
        )
        self.host = self.build
        self.target = self.build

    def set_host(self, name=None, version=None, machine=None, mode=None):
        """Set host platform.

        :param name: a string that identify the system to be considered
            as the host. If None then host is set to the build one (the
            autodetected platform). If set to 'build' or 'target' then host
            is set respectively to current 'build' or 'target' value
        :type name: str | None
        :param version: a string containing the system version. If set to
            None the version is either a default or autodetected when possible
        :type version: str | None
        :param machine: a string containing the name of the target
            machine.
        :type machine: str | None
        :param mode: a string containing the name of the mode. This
            notion is needed on some targets such as VxWorks to switch between
            kernel mode and other modes such as rtp

        When calling set_host, the target system is reset to the host one.
        Thus you should call set_host before set_target otherwise your call
        to set_target will be ignored. Note also that is the host_name is
        equal to the build platform, host_version will be ignored.
        """
        if name is None:
            name = "build"

        if name == "target":
            self.host = self.target
        elif name == "build":
            self.host = self.build
        else:
            self.host = Platform.get(
                platform_name=name, version=version, machine=machine, mode=mode
            )
        self.target = self.host

    def set_target(self, name=None, version=None, machine=None, mode=None):
        """Set target platform.

        :param name: a string that identify the system to be considered
            as the host. If None then host is set to the host one. If set to
            'build' or 'host' then target is set respectively to current
            'build' or 'host' value. In that case target_version and
            target_machine are ignored.
        :type name: str | None
        :param version: a string containing the system version. If set
            to None the version is either a default or autodetected when
            possible.
        :type version: str | None
        :param machine: a string containing the name of the target
            machine.
        :type machine: str | None
        :param mode: a string containing the name of the mode. This
            notion is needed on some targets such as VxWorks to switch between
            kernel mode and other modes such as rtp

        The target parameters are ignored if the target_name is equal to the
        host platform.
        """
        if name is None:
            name = "host"

        if name == "host":
            self.target = self.host
        elif name == "build":
            self.target = self.build
        else:
            self.target = Platform.get(
                platform_name=name, version=version, machine=machine, mode=mode
            )

    def set_env(self, build=None, host=None, target=None):
        """Set build/host/target.

        :param build: string as passed to --build option
        :type build: str | None
        :param host: string as passed to --host
        :type host: str | None
        :param target: string as passed to --target
        :type target: str | None
        """
        saved_build = self.build
        saved_host = self.host
        saved_target = self.target

        def get_platform(value, propagate_build_info=False):
            """Platform based on string value.

            :param value: a string representing a platform or None
            :type value: str | None
            :param propagate_build_info: whether to propagate machine name
                and OS version if no machine name set
            :type propagate_build_info: bool
            :rtype: a Platform instance or None
            """
            if value is None:
                return None

            # We expect 4 fields for build and host and target
            split_value = ([k if k else None for k in value.split(",")] + [None] * 4)[
                0:4
            ]

            if split_value[0] == "build":
                return saved_build
            elif split_value[0] == "host":
                return saved_host
            elif split_value[0] == "target":
                return saved_target
            elif not propagate_build_info:
                return Platform.get(*split_value)
            else:

                # Propagate machine name and OS version if necessary
                if split_value[2] is None:
                    # No new machine name specified, reuse the current one
                    split_value[2] = saved_build.machine

                    # And if there is no OS version set also keep the
                    # current one, setting build='x86-linux' on a 64bit
                    # Linux machine should not change the OS version
                    if split_value[1] is None:
                        split_value[1] = saved_build.os.version
                return Platform.get(*split_value)

        # Retrieve final values for build, host and target
        build_opts = get_platform(build, propagate_build_info=True)
        host_opts = get_platform(host)
        target_opts = get_platform(target)

        # Apply new build, host and target in the right order
        if build_opts is not None:
            self.build = build_opts
            self.host = build_opts
            self.target = build_opts

        if host_opts is not None:
            self.host = host_opts
            self.target = host_opts

        if target_opts is not None:
            self.target = target_opts

    def str_triplet(self):
        """Return a triplet of strings suitable to call set_env.

        :return: a namedtuple suitable for a call to set_env
        :rtype: EnvInfo
        """
        result = []
        if not self.build.is_default:
            result.append(",".join([self.build.platform, self.build.os.version]))
        else:
            result.append(None)

        if self.host != self.build:
            result.append(",".join([self.host.platform, self.host.os.version]))
        else:
            result.append(None)

        if self.target != self.host:
            result.append(
                ",".join(
                    [
                        self.target.platform,
                        self.target.os.version,
                        self.target.machine,
                        self.target.os.mode,
                    ]
                )
            )
        else:
            result.append(None)
        return EnvInfo(*result)

    def cmd_triplet(self):
        """Return command line parameters corresponding to current env.

        :return: a list of command line parameters
        :rtype: list(str)
        """
        build_str, host_str, target_str = self.str_triplet()
        result = []
        if build_str is not None:
            result.append("--build=%s" % build_str)

        if host_str is not None:
            result.append("--host=%s" % host_str)

        if target_str is not None:
            result.append("--target=%s" % target_str)

        return result

    def get_attr(self, name, default_value=None, forced_value=None):
        """Return an attribute value.

        :param name: name of the attribute to check. Name can contain '.'
        :type name: str
        :param default_value: returned value if forced_value not set and the
            attribute does not exist
        :type default_value: object | None
        :param forced_value: if not None, this is the return value
        :type forced_value: object | None

        :return: the attribute value

        This function is useful to get the value of optional functions
        parameters whose default value might depend on the environment.
        """
        if forced_value is not None:
            return forced_value

        attributes = name.split(".")
        result = self
        for a in attributes:
            if not hasattr(result, a):
                return default_value
            else:
                result = getattr(result, a)

        if result is None or result == "":
            return default_value

        return result

    @classmethod
    def add_path(cls, path, append=False):
        """Set a path to PATH environment variable.

        :param path: path to add
        :type path: str
        :param append: if True append, otherwise prepend. Default is prepend
        :type append: bool
        """
        cls.add_search_path("PATH", path, append)

    @classmethod
    def add_search_path(cls, env_var, path, append=False):
        """Add a path to the env_var search paths.

        :param env_var: the environment variable name (e.g. PYTHONPATH,
            LD_LIBRARY_PATH, ...)
        :type env_var: str
        :param path: path to add
        :type path: str
        :param append: if True append, otherwise prepend. Default is prepend
        :type append: bool
        """
        if env_var not in os.environ:
            logger.debug("export {env_var}={path}".format(env_var=env_var, path=path))
            os.environ[env_var] = path
        else:
            if append:
                new_path = os.path.pathsep + path
                logger.debug(
                    "export {env_var}=${env_var}{new_path}".format(
                        env_var=env_var, new_path=new_path
                    )
                )
                os.environ[env_var] += new_path
            else:
                new_path = path + os.path.pathsep + os.environ[env_var]
                logger.debug(
                    "export {env_var}={new_path}".format(
                        env_var=env_var, new_path=new_path
                    )
                )
                os.environ[env_var] = new_path

    @property
    def dll_path_var(self):
        env_var_name = {"windows": "PATH", "darwin": "DYLD_FALLBACK_LIBRARY_PATH"}
        return env_var_name.get(self.host.os.name.lower(), "LD_LIBRARY_PATH")

    def add_dll_path(self, path, append=False):
        """Add a path to the dynamic libraries search paths.

        :param path: path to add
        :type path: str
        :param append: if True append, otherwise prepend. Default is prepend
        :type append: bool
        """
        # On most platforms LD_LIBRARY_PATH is used. For others use:
        self.add_search_path(self.dll_path_var, path, append)

    @property
    def discriminants(self):
        """Compute discriminants.

        :return: the list of discriminants associated with the current context
            (target, host, ...). This is mainly used for testsuites to ensure a
            coherent set of base discriminants.
        :rtype: list[str]
        """
        discs = [
            self.target.platform,
            self.target.triplet,
            self.target.cpu.endian + "-endian",
            self.target.cpu.name,
            self.host.os.name + "-host",
        ]

        if self.target.os.is_bareboard:
            discs.append("bareboard")
        else:
            discs.extend(
                (
                    self.target.os.name,
                    self.target.os.name + "-" + self.target.os.version,
                )
            )
        if self.target.os.name.startswith("vxworks"):  # all: no cover
            discs.append("vxworks")
        if not self.is_cross:
            discs.append("native")
        discs.append("%dbits" % self.target.cpu.bits)
        if self.target.os.name.lower() == "windows":
            discs.append("NT")

        if (not self.is_cross and not self.is_canadian) and self.build.is_virtual:
            discs.append("virtual_machine")  # all: no cover

        return discs

    @property
    def tmp_dir(self):
        """Return current temporary directory.

        :return: a path
        :rtype: str

        The function looks for several variables ``TMPDIR``, ``TMP``
        and in case none of these variables are defined fallback on
        on ``/tmp``.
        """
        return os.environ.get("TMPDIR", os.environ.get("TMP", "/tmp"))

    def to_dict(self):
        """Get current env as a dictionary.

        :return: the dictionary entries are all strings and thus the result
            can be used to format string. For example ``Env().target.os.name``
            will appear with the key ``target_os_name``, ...
        :rtype: dict
        """
        result = {k: v for k, v in self._items()}
        result["is_canadian"] = self.is_canadian
        result["is_cross"] = self.is_cross
        result["platform"] = self.platform

        for c in ("host", "target", "build"):
            result.update({"%s_%s" % (c, k): v for k, v in result[c].to_dict().items()})
            del result[c]
        return result

    @classmethod
    def from_platform_name(cls, platform):
        """Return a BaseEnv object from a platform name.

        That's the reverse of platform property
        """
        # Is it a native platform?
        found = False
        e = BaseEnv()
        try:
            # If it is a native then set_build will work
            e.set_build(platform)
            found = True
        except KeyError:
            # Check whether is this a cross, in that case the platform name is:
            # <target-platform>-<host os name>[64]
            target_name, host = platform.rsplit("-", 1)
            if host == "darwin":
                host_cpu = "x86_64"
            elif host == "solaris":
                host_cpu = "sparc"
            elif host.endswith("64"):
                host = host[:-2]
                host_cpu = "x86_64"
            else:
                host_cpu = "x86"
            try:
                e.set_build("%s-%s" % (host_cpu, host))
                e.set_target(target_name)
                found = True
            except KeyError:
                # invalid platform name
                pass
        if not found:
            return None
        else:
            # Verify that the computed platform is equal to what we had
            assert e.platform == platform
            return e


class BaseEnv(AbstractBaseEnv):
    """BaseEnv."""

    _initialized = False
    # Not a singleton, always initialize new instance

    def __init__(self, build=None, host=None, target=None):
        """Initialize a BaseEnv object.

        On first instantiation, build attribute will be computed and host
        and target set to the build attribute.

        :param build: build architecture. If None then it is set to default
            build
        :type build: Platform | None
        :param host: host architecture. If None then it is set to build
        :type host: Platform | None
        :param target: target architecture. If None then it is set to target
        :type target: Platform | None
        """
        # class variable that holds the current environment
        self._instance = {}

        # class variable that holds the stack of saved environments state
        self._context = []
        super(BaseEnv, self).__init__(build, host, target)

    def __setattr__(self, name, value):
        if name in ("_instance", "_context"):
            object.__setattr__(self, name, value)
        else:
            self._instance[name] = value

    def __getattr__(self, name):
        try:
            return self._instance[name]
        except KeyError as e:
            raise AttributeError(e).with_traceback(sys.exc_info()[2])

    def _items(self):
        return iter(self._instance.items())

    def copy(self, build=None, host=None, target=None):
        """Copy an env.

        :param build: like build set_env parameter
        :type build: str | None
        :param host: like host set_env parameter
        :type host: str | None
        :param target: like target set_env parameter
        :type target: str | None
        :return: a deep copy of the current env
        :rtype: BaseEnv
        """
        result = BaseEnv()
        for k, v in self._items():
            setattr(result, k, v)
        result.set_env(build, host, target)
        return result

    @classmethod
    def from_env(cls, env=None):
        """Return a new BaseEnv object from an env.

        :param env: env. If None copy the current Env
        :type env: BaseEnv | Env
        :rtype: BaseEnv
        """
        if env is None:
            return BaseEnv(build=Env().build, host=Env().host, target=Env().target)
        else:
            return BaseEnv(build=env.build, host=env.host, target=env.target)


class Env(AbstractBaseEnv):
    """Env shows the current environment in used.

    Env is a singleton holding the current environment and platform
    information. It is set by e3.main when the --build/--host/--target option
    are passed to the command line and can be then changed by calling
    :meth:`set_build`, :meth:`set_host`, and :meth:`set_target`.
    """

    # class variable that holds the current environment
    _instance = {}

    # class variable that holds the stack of saved environments state
    _context = []

    def __init__(self):
        """Initialize or reuse an existing Env object (singleton).

        On first instantiation, build attribute will be computed and
        host and target set to the build attribute.
        """
        super(Env, self).__init__()

    @property
    def _initialized(self):
        return "build" in Env._instance

    def __setattr__(self, name, value):
        if name == "_instance":
            Env._instance = value
        elif name == "_context":
            Env._context = value
        else:
            self._instance[name] = value

    def __getattr__(self, name):
        try:
            return self._instance[name]
        except KeyError as e:
            raise AttributeError(e).with_traceback(sys.exc_info()[2])

    def _items(self):
        return iter(self._instance.items())

    def store(self, filename=None):
        """Save environment into memory or file.

        :param filename: a string containing the path of the filename in which
            the environment will be saved. If set to None the environment is
            saved into memory in a stack like structure.
        :type filename: str | None
        """
        # Store environment variables
        self.environ = os.environ.copy()

        # Store cwd
        self.cwd = os.getcwd()

        if filename is None:
            self._context.append(pickle.dumps(self._instance))
        else:
            with open(filename, "wb+") as fd:
                pickle.dump(self._instance, fd)

    def restore(self, filename=None):
        """Restore environment from memory or a file.

        :param filename: a string containing the path of the filename from
            which the environment will be restored. If set to None the
            environment is pop the last saved one
        :type filename: str | None
        """
        if filename is None:
            # We are restoring from memory.  In that case, just double-check
            # that we did store the Env object in memory beforehand (using
            # the store method).
            assert self.environ is not None

        if filename is None and self._context:
            self._instance = pickle.loads(self._context[-1])
            self._context = self._context[:-1]
        elif filename is not None:
            with open(filename, "rb") as fd:
                self._instance = pickle.load(fd)
        else:
            return

        # Restore environment variables value
        # Do not use os.environ = self.environ.copy()
        # or it will break the os.environ object and child process
        # will get the old environment.
        for k in list(os.environ.keys()):
            if os.environ[k] != self.environ.get(k, None):
                del os.environ[k]
        for k in self.environ:
            if os.environ.get(k, None) != self.environ[k]:
                os.environ[k] = self.environ[k]

        # Restore current directory
        os.chdir(self.cwd)
