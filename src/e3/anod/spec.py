from __future__ import annotations

import os
import re
import sys

from packaging.version import Version
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

import e3.anod.deps
import e3.anod.package
import e3.env
import e3.log
import e3.os.process
import e3.text
from e3.anod.error import AnodError, ShellError
from e3.anod import qualifier_dict_to_str, qualifier_str_to_dict
from e3.anod.qualifiers_manager import QualifiersManager
from e3.anod.qualifier import Qualifier
from e3.fs import find
from e3.os.fs import ldd_output_to_posix, which
from e3.platform_db.knowledge_base import OS_INFO
from e3.yaml import load_with_config

# Default API version
__version__ = "1.4"

SUPPORTED_API = (__version__, "1.5", "1.6", "1.7")
# API VERSIONS
#
# Version 1.4 (initial version)
# Version 1.5
#    NEW: YAML files are searched in subdirectories whose basename is the
#    associated spec basename.
#    DEPRECATED: YAML files in same directory as the spec
# Version 1.6
#    NEW: Add support for spec function automatically declared inside each spec
#    DEPRECATED: remove support of e3.anod.loader.spec
# Version 1.7
#    DEPRECATED: use of qualifier as string emits deprecation warning

logger = e3.log.getLogger("anod")
spec_logger = e3.log.getLogger("anod.spec")


if TYPE_CHECKING:
    from typing import Any, IO, Literal, Union, Iterable
    from collections.abc import Callable, Sequence
    from e3.anod.buildspace import BuildSpace
    from e3.anod.sandbox import SandBox
    from e3.env import BaseEnv
    from e3.os.process import DEVNULL_VALUE, PIPE_VALUE

    import e3.anod.package
    import e3.anod.sandbox

    BUILD_PRIMITIVE = Literal["build"]
    DOWNLOAD_PRIMITIVE = Literal["download"]
    INSTALL_PRIMITIVE = Literal["install"]
    TEST_PRIMITIVE = Literal["test"]
    SOURCE_PRIMITIVE = Literal["source"]

    # Anod Dependency can target a build, install, or source
    DEPENDENCY_PRIMITIVE = Union[
        BUILD_PRIMITIVE, DOWNLOAD_PRIMITIVE, INSTALL_PRIMITIVE, SOURCE_PRIMITIVE
    ]

    # Supported primitives are build, install, source, and test
    PRIMITIVE = Union[
        BUILD_PRIMITIVE, INSTALL_PRIMITIVE, SOURCE_PRIMITIVE, TEST_PRIMITIVE
    ]


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


def parse_command(command: Sequence[str], build_space: BuildSpace) -> list[str]:
    """Parse a command line formatting each string.

    :param command: the command line (a list of string)
    :param build_space: a build space object
    """
    cmd_dict = {}
    cmd_dict.update({k.upper(): v for (k, v) in list(build_space.__dict__.items())})
    return [e3.text.format_with_dict(c, cmd_dict) for c in command]


def has_primitive(anod_instance: Anod, name: Literal["download"] | PRIMITIVE) -> bool:
    """Return True if the primitive `name` is supported.

    Note that download is currently considered as a primitive in that context.

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

    if is_primitive:
        if func.require is None:
            return True
        else:
            return func.require(anod_instance)
    else:
        return False


def fetch_attr(instance: Any, name: str, default_value: Any) -> Any:
    """Return an attribute or the default value if missing.

    Unlike `getattr(instance, name, default_value)`, this works only on
    attributes present in the class (so class attributes or properties) and
    this does not hide AttributeError exceptions that getting an existing
    attribute might raise.
    """
    # Singleton used to determine whether call to ``gettattr()`` returns the
    # default value (i.e. attribute is missing) or just returns the attribute
    # value (it could be ``None``).
    sentinel = object()

    return (
        default_value
        if getattr(type(instance), name, sentinel) is sentinel
        else getattr(instance, name)
    )


class Anod:
    """Anod base class.

    To write an Anod specification file, you'll need to subclass Anod. A very
    basic Anod specification file could be:

    .. code-block:: python

        from e3.anod.spec import Anod

        class MyProduct(Anod):
            pass

    All attributes starting with ``spec_`` are reserved by the driver and must
    not be overwritten.

    Several attributes are set when loading the spec:

    :cvar api_version: which API version is in use
    :cvar data_files: set of yaml files associated with the spec
    :cvar spec_checksum: the sha1 of the specification file content
    :cvar spec_dir: directory where the specification files are located
    :cvar name: the basename of the specification file (without the .anod
         extension)
    :cvar sandbox: e3.anod.sandbox.SandBox object shared by all Anod instances
    :vartype sandbox: e3.anod.sandbox.SandBox | None

    Some attributes are meant to be overwritten in the specification file:

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
    sandbox: SandBox | None = None
    name = ""
    api_version = __version__
    data_files: tuple[str, ...] = ()

    # API
    Dependency = e3.anod.deps.Dependency
    Package = e3.anod.package.Package
    BuildVar = e3.anod.deps.BuildVar
    Source = e3.anod.package.Source
    SharedSource = e3.anod.package.SharedSource
    SourceBuilder = e3.anod.package.SourceBuilder
    ExternalSourceBuilder = e3.anod.package.ExternalSourceBuilder
    ThirdPartySourceBuilder = e3.anod.package.ThirdPartySourceBuilder

    def __new__(cls, *args: Any, **kwargs: Any) -> Any:
        """Replace `method` by property when decorator is missing."""
        should_be_property = (
            "enable_name_generator",
            "readme_info",
            "base_name",
            "build_space_name",
            "has_package",
            "package",
            "component",
            "source_pkg_build",
        )

        for prop in should_be_property:
            class_property = getattr(cls, prop)
            if callable(class_property):
                setattr(cls, prop, property(fget=class_property))

        return super().__new__(cls)

    def __init__(
        self,
        qualifier: str | dict[str, str | bool | Iterable[str]] | None,
        kind: PRIMITIVE,
        jobs: int = 1,
        env: BaseEnv | None = None,
        *,
        parse_qualifiers: bool = True,
    ):
        """Initialize an Anod instance.

        :param qualifier: the qualifier used when loading the spec
        :param kind: the action kind (build, install, test, ...)
        :param jobs: max parallelism level allowed for jobs spawned by this
            instance
        :param env: alternate platform environment
        :param parse_qualifiers: if True AND Anod.enable_name_generator, parse the
            qualifiers, otherwise do nothing. This is useful to be able to load a spec
            and retrieve qualifiers information without raising any qualifier related
            exception.
        :raise: SpecError
        """
        self.deps: dict[str, Anod] = {}

        self.kind = kind
        self.jobs = jobs

        # Set when self.bind_to_sandbox is called
        self.__build_space: BuildSpace | None = None

        # Default spec logger
        self.log = spec_logger

        # Set spec environment
        self.env = e3.env.BaseEnv.from_env(env)

        # Create the parsed qualifier (dict version). In the future
        # self.parsed_qualifier should be replaced by self.qualifier
        if isinstance(qualifier, str):
            if Version(self.api_version) >= Version("1.7"):
                logger.error(
                    f"Use dict for qualifiers when declaring specs (spec {self.name})"
                )
                raise e3.anod.error.SpecError("Use of str qualifiers is deprecated")

            self.parsed_qualifier = qualifier_str_to_dict(qualifier)
        elif isinstance(qualifier, dict):
            self.parsed_qualifier = dict(qualifier)
        elif qualifier is None:
            self.parsed_qualifier = {}
        else:
            raise e3.anod.error.SpecError("invalid qualifier")

        # Create the QualifiersManager.
        # Skip if the name generator is disabled.
        if self.enable_name_generator and self.kind != "source":
            self.qualifiers_manager = QualifiersManager(self)
            self.declare_qualifiers_and_components(self.qualifiers_manager)
            if parse_qualifiers:
                self.qualifiers_manager.parse(self.parsed_qualifier)

        # UID of the spec instance
        self.uid = ".".join(
            (
                self.env.platform,
                self.build_space_name,
                self.kind,
            )
        )

        # Hold the config dictionary-like object
        self._config: dict | None = None

        # Hold the result of the pre function
        self._pre: dict[str, Any] | None = None

    @property
    def qualifier(self) -> str:
        if Version(self.api_version) >= Version("1.7"):
            logger.warning(f"qualifier attribute is obsolete (spec: {self.name})")
        return qualifier_dict_to_str(self.parsed_qualifier)

    # Temporary flag used to disable the name generator during the
    # transition (U625-013).
    @property
    def enable_name_generator(self) -> bool:
        """State if the name generation must be enabled.

        If true, then both the 'component' and the 'build_space_name' are generated.
        """
        return False

    @property
    def readme_info(self) -> tuple[str, str] | None:
        """Return readme location and final filename.

        .. note:: This property make sens only if a component is declared.

        :return: A tuple with a relative path to spec directory where the find the
            content and the final basename for the readme.
        """
        return None

    def declare_qualifiers_and_components(
        self, qualifiers_manager: QualifiersManager
    ) -> None:
        """Configure all the qualifiers and components.

        This method must be overridden in the user spec to actually configure
        the QualifiersManager.

        All the qualifiers must be declared using the declare_tag_qualifier and
        declare_key_value_qualifier spec_parameter_manager method.

        All the components must be declared using the declare_component
        method of QualifiersManager class.

        :param qualifiers_manager: the QualifiersManager instance to be configured.
        """
        pass

    @property
    def args(self) -> dict[str, str | bool | frozenset[str]]:
        """Access to final qualifier values (with defaults set)."""
        if self.enable_name_generator:
            return Qualifier(self.qualifiers_manager.qualifier_values)
        else:
            return self.parsed_qualifier  # type: ignore

    @property
    def base_name(self) -> str:
        """Set the base name used for the name generation.

        This method is used to provide the base name to be used by the name generator.
        By default, this base name is 'self.name' (the spec name without .anod).

        It can be overloaded in the user spec.
        """
        return self.name

    @property
    def build_space_name(self) -> str:
        """Return an automatic build_space_name.

        If the component name is not None (from the component method), it will return
        the component name for consistency reasons.

        :return: self.name if the name generator is disabled and the generated
            build_space name otherwise.
        :rtype: str | None
        """
        if self.enable_name_generator and self.kind != "source":
            return self.qualifiers_manager.build_space_name
        else:
            return self.name

    @property
    def build_space(self) -> BuildSpace:
        if self.__build_space is None:
            raise AnodError("build space not set")
        return self.__build_space

    @property
    def has_package(self) -> bool:
        """Return true if the spec defines a binary package."""
        return self.package is not None and self.component is not None

    def bind_to_sandbox(self, sandbox: SandBox) -> None:
        """Bind spec instance to a physical Anod sandbox.

        Binding an Anod instance to a sandbox will set the
        build_space attribute.
        """
        self.__build_space = sandbox.get_build_space(
            name=self.build_space_name, platform=self.env.platform
        )

    def check_shared_libraries_closure(
        self,
        prefix: str | None = None,
        ignored_libs: list[str] | None = None,
        ldd_output: str | None = None,
        case_sensitive: bool | None = None,
    ) -> dict[str, list[tuple[str, str]]]:
        """Sanity check the shared library closure.

        Make sure that the libraries only depend on authorized system shared
        libraries.

        Raise an error when a problem is detected.

        It is possible to use the *ldd_output* parameter to mimic the ``ldd``
        call. In that case, the *ldd_output* should look like::

            /a/b/c.so:
                    d.so => /e/f/d.so
                    g.so => /a/b/g.so
            /a/b/h.so:
                    g.so => /a/b/g.so

        .. note::
            Indented lines above use the TAB character.

        .. note::
            This method may be used only on hosts with an ``ldd`` tool in the
            ``PATH``. If the tool may not be found with :func:`~e3.os.fs.which`,
            and *ldd_output* is not provided, a :exc:`FileNotFoundError`
            exception is raised.

        :param prefix: The path where to find the library to be checked.
        :param ignored_libs: The list of additional system libraries authorized
            in the closure.
        :param ldd_output: An ``ldd`` command output.
        :param case_sensitive: State if the comparison of a library name and the
            value in *ignored_libs* should be case-sensitive or not. If
            ``None``, the comparison is case-sensitive, but on Windows hosts.

        :return: A dictionary, where keys are the analyzed files, and the
            values are the shared libraries linked to that file (a tuple made
            of the file name and its path).

        :raise AnodError: if some of the shared libraries in *prefix* (or in
            *ldd_output*) is not in the same directory as the analysed element.
        :raise FileNotFoundError: if *ldd_output* is not provided and ``ldd``
            application cannot be found in the ``PATH``.
        """  # noqa RST304
        ignored: list[str] = ignored_libs or []
        result: dict[str, list[tuple[str, str]]] = {}
        errors: dict[str, list[str]] = {}
        lib_file: str = ""

        if case_sensitive is None:
            case_sensitive = False if sys.platform == "win32" else True

        if ldd_output is None:
            # If ldd is not in the path, return and issue a warning.
            if not which("ldd"):
                raise FileNotFoundError(
                    "Shared Libraries closure check skipped: ldd could not be found."
                )

            if prefix is None:
                prefix = self.build_space.install_dir

            # Get all files matching the OS shared lib extension.
            shlib_ext: str = f"{OS_INFO[e3.env.Env().build.os.name]['dllext']}"
            lib_files = find(root=prefix, pattern=f"*{shlib_ext}")

            if not lib_files:
                self.log.info(f"No {shlib_ext} files to check in {prefix}")
                ldd_output = ""
            else:
                ldd_output = e3.os.process.Run(["ldd"] + lib_files).out or ""

                # When only one path is specified, ldd does not add the name of the
                # file in the output. This would break the parsing below.
                if len(lib_files) == 1:
                    ldd_output = f"{lib_files[0]}:\n{ldd_output}"
                ldd_output = ldd_output_to_posix(ldd_output)
        else:
            # An ldd output has been provided. Update it first to Posix.
            ldd_output = ldd_output_to_posix(ldd_output)
            lib_files = re.findall(r"^([^\t].*):$", ldd_output, flags=re.M)

        if self.sandbox and hasattr(self.sandbox, "root_dir"):
            root_dir = self.sandbox.root_dir
        else:
            root_dir = str(Path(self.build_space.install_dir).parent)

        # Retrieve list of shared lib dependencies for sanity checking

        self.log.info("Running Shared Libraries closure check")
        # Build up a list of linked libraries. Dict key is the library
        # name/path, value is the list of linked libraries.
        for line in ldd_output.splitlines():
            if line[:-1] in lib_files:
                # Line is like ``/mypath/mydll.so:``, it's the result of
                # ldd for ``mydll.so``.
                lib_file = line[:-1]
                if lib_file not in result:
                    result[lib_file] = []
            elif lib_file and " => " in line:
                # Line looks like:
                # ``        otherdll.so => /other/otherdll.so (0xabcd)``
                name, path = line.strip().split(" => ", 1)

                if case_sensitive:
                    in_ignored = len([k for k in ignored if name.startswith(k)]) > 0
                else:
                    in_ignored = (
                        len([k for k in ignored if name.lower().startswith(k.lower())])
                        > 0
                    )

                # Make sure there are no "not found" errors
                if "not found" in line.lower():
                    result[lib_file].append((name, path))
                    if not in_ignored:
                        if lib_file not in errors:
                            errors[lib_file] = []
                        errors[lib_file].append(f"\n\t- {name}: {path}")
                    continue

                path = re.sub(" (.*)", "", path)
                result[lib_file].append((name, path))

                # Make sure a path is defined, we may have lines like::
                #
                # myprojects.so:
                #       linux-vdso.so.1 =>  (0x00007ffdd6d55000)
                #
                if not path.strip() or not Path(path).exists():
                    continue

                if os.path.relpath(path, root_dir).startswith("..") and not in_ignored:
                    if lib_file not in errors:
                        errors[lib_file] = []
                    errors[lib_file].append(f"\n\t- {name}: {path}")

        if errors:
            # Build up error message
            err_msg: str = "Dependencies on external libraries:"
            for shared_lib, dependencies in errors.items():
                err_msg = (
                    f"{err_msg}\n    Shared lib {shared_lib} has external shared "
                    f"dependencies:{''.join(sorted(dependencies))}"
                )
            raise AnodError(err_msg)

        return result

    def load_config_file(
        self,
        extended: bool = False,
        suffix: str | None = None,
        selectors: dict | None = None,
    ) -> Any:
        """Load a YAML config file associated with the current module.

        This function looks for a YAML starting with the spec basename. The
        list of available file is set by the data_files parameter when
        initializing the spec.

        :param suffix: suffix of the configuration file (default is None)
        :param extended: if True then a special yaml parser is used with
            ability to use case statement
        :param selectors: additional selectors for extended mode
        """
        # Compute data file location and check for existence
        if Version(self.api_version) >= Version("1.5"):
            filename = os.path.join(self.name, suffix if suffix else "config")
        else:
            filename = "{}{}".format(self.name, "-" + suffix if suffix else "")
        assert filename in self.data_files, "invalid data file: {} ({})".format(
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

        Also, directly access items returned by the ``pre`` callback.
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

    def get_qualifier(self, qualifier_name: str) -> str | bool | frozenset[str] | None:
        """Return a qualifier value.

        Requires that qualifiers_manager attribute has been initialized and its parse
        method called.

        :return: The qualifier value:
            - A string for key value qualifiers
            - A bool for tag qualifiers
            - ``None`` if the name_generator is disabled
        """
        if self.enable_name_generator:
            assert self.qualifiers_manager is not None
            return self.qualifiers_manager[qualifier_name]
        else:
            return self.parsed_qualifier.get(qualifier_name, None)

    @classmethod
    def primitive(
        cls,
        pre: str | None = None,
        post: str | None = None,
        version: Callable[..., str] | None = None,
        require: Callable[[Anod], bool] | None = None,
        post_install: bool = False,
    ) -> Callable:
        """Declare an anod primitive.

        Catch all exceptions and raise AnodError with the traceback

        :param pre: None or name of method in the spec to call before running
            the primitive. The method takes a unique parameter `self` and
            returns a dict
        :param post: None or "install". This parameter is obsolete and should
            not be used. Prefer "post_install=True" to achieve the same effect
        :param version: None or a callback function returning the version
            that will be evaluated as a string. This callback is called
            after running the primitive
        :param require: None or a special function to call before running the
            primitive. The function takes a unique parameter `self` and
            returns a boolean
        :param post_install: if True call the install primitive after the build
            primitive. Note that between the two a binary package might be generated
            depending on the context. This is equivalent to post="install"
        :raise: AnodError
        """

        def primitive_dec(f, pre=pre, post=post, version=version):  # type: ignore
            def primitive_func(self, *args, **kwargs):  # type: ignore
                self.log.debug("%s %s starts", self.name, f.__name__)

                # Ensure temporary directory is set to a directory local to
                # the current sandbox. This avoids mainly to lose track of
                # temporary files that are then accumulating on the
                # filesystems.
                # ??? Temporary fix for T409-012 ???
                if self.__build_space is not None and self.build_space.initialized:
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
                except Exception as err:
                    error_msg = f"{self.name} {f.__name__} fails"
                    self.log.exception(error_msg)
                    raise AnodError(error_msg) from err

            primitive_func.is_primitive = True
            primitive_func.pre = pre
            primitive_func.post = post
            primitive_func.post_install = post_install or (post == "install")
            primitive_func.version = version
            primitive_func.require = require
            return primitive_func

        return primitive_dec

    @property
    def package(self) -> e3.anod.package.Package | None:
        """Return binary package creation recipe.

        If None don't create a binary package, needs a component name set.
        """
        return None

    @property
    def component(self) -> str | None:
        """Return component name.

        If None, don't created a component (nor a binary package).
        :return: None if the name generator is disabled and the generated name
        otherwise (possibly None if no component is required)
        """
        if self.enable_name_generator:
            return self.qualifiers_manager.component
        return None

    @property
    def module_name(self) -> str:
        """For backward compatibility purpose."""
        return self.name

    @property
    def anod_id(self) -> str:
        """For backward compatibility purpose."""
        return self.uid

    @property
    def source_pkg_build(self) -> list[e3.anod.package.SourceBuilder] | None:
        """Return list of SourceBuilder defined in the specification file."""
        return None

    def shell(
        self,
        *command: str,
        parse_shebang: bool = True,
        output: DEVNULL_VALUE | PIPE_VALUE | str | IO | None = None,
        python_executable: None = None,
        **kwargs: Any,
    ) -> e3.os.process.Run:
        """Run a subprocess using e3.os.process.Run.

        Contrary to what is done in e3.os.process.Run parse_shebang
        defaults to True and output is by default set to the anod
        build space log stream.

        Note that calling shell() raises an exception when the
        process returns an exit code that is not 0.

        Same options as e3.os.process.Run with some small differences:

        :param python_executable: kept for backward compatibility but ignored
        :param output: by default set to anod build space log stream
        :param parse_shebang: by default set True

        :raise: ShellError
        """
        parsed_command = parse_command(command, self.build_space)
        if output is None:
            output = e3.log.default_output_stream

        r = e3.os.process.Run(
            parsed_command, parse_shebang=parse_shebang, output=output, **kwargs
        )
        if TYPE_CHECKING:
            assert r.status is not None
        if r.status != 0:
            raise ShellError(
                message="%s failed (exit status: %d)" % (" ".join(command), r.status),
                origin="anod.shell",
                process=r,
            )
        return r
