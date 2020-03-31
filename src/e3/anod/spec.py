from __future__ import annotations

import os
from collections import OrderedDict
from distutils.version import StrictVersion
from typing import TYPE_CHECKING

import yaml

import e3.anod.deps
import e3.anod.package
import e3.env
import e3.log
import e3.os.process
import e3.text
from e3.anod.error import AnodError, ShellError
from e3.yaml import load_with_config

# CURRENT API version
__version__ = "1.4"

SUPPORTED_API = (__version__, "1.5")
# The driver can support multiple version of the spec API, we currently support
# only the version 1.4 and 1.5. Default is still 1.4

logger = e3.log.getLogger("anod")


if TYPE_CHECKING:
    from typing import Any, Callable, Dict, List, Optional, Sequence
    from e3.anod.buildspace import BuildSpace
    from e3.anod.sandbox import SandBox
    from e3.env import BaseEnv

    import e3.anod.package
    import e3.anod.sandbox


def check_api_version(version: str) -> None:
    """Make sure there are no API mismatch.

    :raise: AnodError if the API is not supported
    """
    if version.strip() not in SUPPORTED_API:
        raise AnodError(
            origin="check_api_version",
            message="API version mismatch. Anod specs are at %s but the "
            "driver is only supporting %s" % (version.strip(), ",".join(SUPPORTED_API)),
        )


def parse_command(command: Sequence[str], build_space: BuildSpace) -> List[str]:
    """Parse a command line formatting each string.

    :param command: the command line (a list of string)
    :param build_space: a build space object
    """
    cmd_dict = {}
    cmd_dict.update({k.upper(): v for (k, v) in list(build_space.__dict__.items())})
    return [e3.text.format_with_dict(c, cmd_dict) for c in command]


def has_primitive(anod_instance: Anod, name: str) -> bool:
    """Return True if the primitive `name` is supported.

    :param anod_instance: an Anod instance
    :param name: name of the primitive ('build', 'install'...)
    """
    if name == "source":
        source_pkg_build = getattr(anod_instance, "source_pkg_build", None)
        return source_pkg_build is not None

    try:
        func = getattr(anod_instance, name)
        is_primitive: bool = func.is_primitive
    except AttributeError:
        return False
    return is_primitive


class Anod(object):
    """Anod base class.

    To write an Anod specification file, you'll need to subclass Anod. A very
    basic Anod specification file could be:

    .. code-block:: python

        from e3.anod.spec import Anod

        class MyProduct(Anod):
            pass

    All attributes starting with spec_ are reserved by the driver and must not
    be overwritten.

    Several attributes are set when loading the spec:

    :cvar api_version: which API version is in use
    :cvar data_files: set of yaml files associated with the spec
    :cvar spec_checksum: the sha1 of the specification file content
    :cvar spec_dir: directory where the specification files are located
    :cvar name: the basename of the specification file (without the .anod
         extension)
    :cvar sandbox: e3.anod.sandbox.SandBox object shared by all Anod instances
    :vartype sandbox: e3.anod.sandbox.SandBox | None

    Some attributes are meant the be overwritten in the specification file:

    :cvar source_pkg_build: a dictionary associating Anod.SourceBuilder to the
        Anod.Source names

    Some attributes are here to simply the writing of specification files.
    They are part of the Anod API:

    :cvar Dependency: the e3.anod.deps.Dependency class
    :cvar Package: the e3.anod.package.Package class
    :cvar Source: the e3.anod.package.Source class
    :cvar SourceBuilder: the e3.anod.package.SourceBuilder class
    :cvar ThirdPartySourceBuilder: the e3.anod.package.ThirdPartySourceBuilder

    :ivar uid: unique identifier for the instance, None until the instance
        has been activated with AnodDriver.activate()
    :vartype uid: str | None
    """

    # set when loading the spec
    spec_checksum = ""
    spec_dir = ""
    sandbox: Optional[SandBox] = None
    name = ""
    api_version = ""
    data_files = ()

    # API
    Dependency = e3.anod.deps.Dependency
    Package = e3.anod.package.Package
    BuildVar = e3.anod.deps.BuildVar
    Source = e3.anod.package.Source
    SharedSource = e3.anod.package.SharedSource
    SourceBuilder = e3.anod.package.SourceBuilder
    ExternalSourceBuilder = e3.anod.package.ExternalSourceBuilder
    ThirdPartySourceBuilder = e3.anod.package.ThirdPartySourceBuilder

    def __init__(self, qualifier: str, kind: str, jobs: int = 1, env: BaseEnv = None):
        """Initialize an Anod instance.

        :param qualifier: the qualifier used when loading the spec
        :param kind: the action kind (build, install, test, ...)
        :param jobs: max parallelism level allowed for jobs spawned by this
            instance
        :param env: alternate platform environment
        :raise: SpecError
        """
        self.deps: Dict[str, Anod] = OrderedDict()

        self.kind = kind
        self.jobs = jobs

        # Set when self.bind_to_sandbox is called
        self.__build_space: Optional[BuildSpace] = None

        # Default spec logger
        self.log = e3.log.getLogger("anod.spec")

        # Set spec environment
        self.env = e3.env.BaseEnv.from_env(env)

        # Create the parsed qualifier (dict version). In the future
        # self.parsed_qualifier should be replaced by self.qualifier
        self.parsed_qualifier = OrderedDict()
        if qualifier:
            qual_dict = [
                (key, value)
                for key, _, value in (
                    item.partition("=") for item in qualifier.split(",")
                )
            ]
        else:
            qual_dict = []

        for k in qual_dict:
            self.parsed_qualifier[k[0]] = k[1]
        self.qualifier = qualifier

        # Default build space name is the spec name
        if "build_space_name" not in dir(self):
            self.build_space_name = self.name

        # UID of the spec instance
        self.uid = ".".join(
            (
                self.env.build.machine,
                self.env.platform,
                self.build_space_name,
                self.kind,
            )
        )

        # Hold the config dictionary-like object
        self._config: Optional[dict] = None

        # Hold the result of the pre function
        self._pre = None

    @property
    def build_space(self) -> BuildSpace:
        if self.__build_space is None:
            raise AnodError("build space not set")
        return self.__build_space

    @property
    def has_package(self) -> bool:
        """Return true if the spec defines a binary package."""
        return (
            self.package is not None
            and self.package.name is not None
            and self.component is not None
        )

    def bind_to_sandbox(self, sandbox: SandBox) -> None:
        """Bind spec instance to a physical Anod sandbox.

        Binding an Anod instance to a sandbox will set the
        build_space attribute.
        """
        self.__build_space = sandbox.get_build_space(
            name=self.build_space_name, platform=self.env.platform
        )

    def bind_to_config(self, config: dict) -> None:
        """Bind an Anod instance to a config.

        :param config: a dictionary-like object
        """
        self._config = config

    def load_config_file(
        self,
        extended: bool = False,
        suffix: Optional[str] = None,
        selectors: dict = None,
    ) -> Any:
        """Load a YAML config file associated with the current module.

        This function looks for a YAML starting with the spec basename. The
        list of available file is set by the data_files parameter when
        initializing the spec.

        :param suffix: suffix of the configuration file (default is '')
        :param extended: if True then a special yaml parser is used with
            ability to use case statement
        :param selectors: additional selectors for extended mode
        """
        # Compute data file location and check for existence
        if StrictVersion(self.api_version) >= StrictVersion("1.5"):
            filename = os.path.join(self.name, suffix if suffix else "config")
        else:
            filename = "%s%s" % (self.name, "-" + suffix if suffix else "")
        assert filename in self.data_files, "invalid data file: %s (%s)" % (
            filename,
            ", ".join(self.data_files),
        )
        filename = os.path.join(self.spec_dir, filename + ".yaml")

        if extended:
            # Ensure selectors is a dict
            config_selectors: dict = {} if selectors is None else selectors

            # Add environment information to selectors
            config_selectors.update(self.env.to_dict())

            return load_with_config(filename, config_selectors)
        else:
            with open(filename) as f:
                return yaml.safe_load(f.read())

    def __getitem__(self, key: str) -> Any:
        """Access build_space attributes and pre callback values directly.

        Allow accessing all build_space attributes directly by using
        __getitem__, e.g. self['PKG_DIR'] to access
        self.build_space.pkg_dir values.

        Also directly access items returned by the ``pre`` callback.
        """
        if self.__build_space is None:
            return "unknown"

        # First look for pre result
        if self._pre is not None and key in self._pre:
            return self._pre[key]

        # Then look in the config dictionary
        if self._config is not None and key in self._config:
            return self._config[key]

        # Then check if the key (in lowercase) is in the build_space
        elif key.isupper():
            return getattr(self.build_space, key.lower(), None)

    @classmethod
    def primitive(
        cls,
        pre: Optional[Callable[[Anod], dict]] = None,
        post: Optional[Callable[..., None]] = None,
        version: Optional[Callable[..., str]] = None,
    ) -> Callable:
        """Declare an anod primitive.

        Catch all exceptions and raise AnodError with the traceback

        :param pre: None or a special function to call before running the
            primitive. The function takes a unique parameter `self` and
            returns a dict
        :param post: None or a callback function to call after running the
            primitive
        :param version: None or a callback function returning the version
            that will be evaluated as a string. This callback is called
            after running the primitive
        :raise: AnodError
        """

        def primitive_dec(f, pre=pre, post=post, version=version):
            def primitive_func(self, *args, **kwargs):
                self.log.debug("%s %s starts", self.name, f.__name__)

                result = False

                # Ensure temporary directory is set to a directory local to
                # the current sandbox. This avoid mainly to loose track of
                # temporary files that are then accumulating on the
                # filesystems.
                if self.build_space is not None and self.build_space.initialized:
                    for tmp_var in ("TMP", "TEMP", "TMPDIR"):
                        os.environ[tmp_var] = self.build_space.tmp_dir

                try:
                    # If there is a pre function call it
                    if pre is not None:
                        self._pre = getattr(self, pre)()

                    # Run the primitive
                    result = f(self, *args, **kwargs)
                    self.log.debug("%s %s ends", self.name, f.__name__)

                    # And return the result
                    return result
                except AnodError:
                    self.log.exception("%s %s fails", self.name, f.__name__)
                    raise AnodError(
                        "%s %s fails (AnodError exception in primitive)"
                        % (self.name, f.__name__)
                    )
                except Exception as e:
                    self.log.exception("%s %s fails", self.name, f.__name__)
                    raise AnodError(
                        "%s %s fails (got exception: %s)" % (self.name, f.__name__, e)
                    )

            primitive_func.is_primitive = True
            primitive_func.pre = pre
            primitive_func.post = post
            primitive_func.version = version
            return primitive_func

        return primitive_dec

    @property
    def package(self) -> Optional[e3.anod.package.Package]:
        """Return binary package creation recipe.

        If None don't create a binary package, needs a component name set.
        """
        return None

    @property
    def component(self) -> Optional[str]:
        """Return component name.

        If None, don't created a component (nor a binary package).
        """
        return None

    @property
    def module_name(self) -> str:
        """For backward compatibility purpose."""
        return self.name

    @property
    def anod_id(self) -> str:
        """For backward compativility purpose."""
        return self.uid

    @property
    def source_pkg_build(self) -> Optional[List[e3.anod.package.SourceBuilder]]:
        """Return list of SourceBuilder defined in the specification file."""
        return None

    def shell(self, *command: str, **kwargs) -> e3.os.process.Run:
        """Run a subprocess using e3.os.process.Run.

        Contrary to what is done in e3.os.process.Run parse_shebang
        defaults to True and output is by default set to the anod
        build space log stream.

        Note that calling shell() raises an exception when the
        process returns an exit code that is not 0.

        :raise: ShellError
        """
        parsed_command = parse_command(command, self.build_space)
        if "parse_shebang" not in kwargs:
            kwargs["parse_shebang"] = True
        if "output" not in kwargs:
            kwargs["output"] = e3.log.default_output_stream

        # For backward compatibility ???
        if "python_executable" in kwargs:
            del kwargs["python_executable"]

        r = e3.os.process.Run(parsed_command, **kwargs)
        if TYPE_CHECKING:
            assert r.status is not None
        if r.status != 0:
            raise ShellError(
                message="%s failed (exit status: %d)" % (" ".join(command), r.status),
                origin="anod.shell",
                process=r,
            )
        return r
