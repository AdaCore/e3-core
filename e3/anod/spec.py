from __future__ import absolute_import, division, print_function

import os
from collections import OrderedDict
from distutils.version import StrictVersion

import e3.anod.deps
import e3.anod.package
import e3.env
import e3.log
import e3.os.process
import e3.text
import yaml
from e3.anod.error import AnodError, ShellError
from e3.anod.status import ReturnValue
from e3.yaml import load_with_config

# CURRENT API version
__version__ = '1.4'

SUPPORTED_API = (__version__, '1.5')
# The driver can support multiple version of the spec API, we currently support
# only the version 1.4 and 1.5. Default is still 1.4

logger = e3.log.getLogger('anod')


def check_api_version(version):
    """Make sure there are no API mismatch."""
    if version.strip() not in SUPPORTED_API:
        raise AnodError(
            origin='check_api_version',
            message='API version mismatch. Anod specs are at %s but the '
            'driver is only supporting %s' % (
                version.strip(), ','.join(SUPPORTED_API)))


def parse_command(command, build_space):
    """Parse a command line formatting each string.

    :param command: the command line (a list of string)
    :type command: list[str] | tuple[str]
    :param build_space: a build space object
    :type build_space: e3.anod.sandbox.BuildSpace
    """
    cmd_dict = {}
    cmd_dict.update(
        dict((k.upper(), v)
             for (k, v) in build_space.__dict__.items()))
    return [e3.text.format_with_dict(c, cmd_dict) for c in command]


def has_primitive(anod_instance, name):
    """Return True if the primitive `name` is supported.

    :param anod_instance: an Anod instance
    :type anod_instance: Anod
    :param name: name of the primitive ('build', 'install'...)
    :type name: str

    :rtype: bool
    """
    if name == 'source':
        source_pkg_build = getattr(anod_instance, 'source_pkg_build', None)
        return source_pkg_build is not None

    try:
        func = getattr(anod_instance, name)
        is_primitive = getattr(func, 'is_primitive')
    except AttributeError:
        return False
    return bool(is_primitive)


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

    Three attributes are set when loading the spec:

    :cvar spec_checksum: the sha1 of the specification file content
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
    spec_checksum = ''
    sandbox = None
    name = ''

    # API
    Dependency = e3.anod.deps.Dependency
    Package = e3.anod.package.Package
    BuildVar = e3.anod.deps.BuildVar
    Source = e3.anod.package.Source
    SharedSource = e3.anod.package.SharedSource
    SourceBuilder = e3.anod.package.SourceBuilder
    ExternalSourceBuilder = e3.anod.package.ExternalSourceBuilder
    ThirdPartySourceBuilder = e3.anod.package.ThirdPartySourceBuilder

    def __init__(self, qualifier, kind, jobs=1, env=None):
        """Initialize an Anod instance.

        :param qualifier: the qualifier used when loading the spec
        :type qualifier: str
        :param kind: the action kind (build, install, test, ...)
        :type kind: str
        :param jobs: max parallelism level allowed for jobs spawned by this
            instance
        :type jobs: int
        :param env: alternate platform environment
        :type env: Env
        :raise: SpecError
        """
        self.deps = OrderedDict()
        """:type: OrderedDict[e3.anod.deps.Dependency]"""

        self.kind = kind
        self.jobs = jobs

        # Set when AnodDriver.activate() is called
        self.build_space = None
        self.log = None

        # Set spec environment
        if env is None:
            self.env = e3.env.BaseEnv(build=e3.env.Env().build,
                                      host=e3.env.Env().host,
                                      target=e3.env.Env().target)
        else:
            self.env = e3.env.BaseEnv(build=env.build,
                                      host=env.host,
                                      target=env.target)

        self.fingerprint = None

        # Parse qualifier
        self.parsed_qualifier = OrderedDict()
        if qualifier:
            qual_dict = [(key, value) for key, _, value in
                         (item.partition('=')
                         for item in qualifier.split(','))]
        else:
            qual_dict = []

        # ??? In the future qualifier keys should be ordered
        for k in qual_dict:
            self.parsed_qualifier[k[0]] = k[1]
        self.qualifier = qualifier

        # Default build space name is the spec name
        if 'build_space_name' not in dir(self):
            self.build_space_name = self.name

        # UID of the spec instance
        self.uid = ".".join((self.env.build.machine,
                             self.env.platform,
                             self.build_space_name,
                             self.kind))

    @property
    def has_package(self):
        """Return true if the spec defines a binary package.

        :rtype: bool
        """
        return self.package is not None and self.package.name is not None

    def load_config_file(self, extended=False, suffix=None, selectors=None):
        """Load a YAML config file associated with the current module.

        This function looks for a YAML starting with the spec basename. The
        list of available file is set by the data_files parameter when
        initializing the spec.

        :param suffix: suffix of the configuration file (default is '')
        :type suffix: str | unicode
        :param extended: if True then a special yaml parser is used with
            ability to use case statement
        :type extended: bool
        :param selectors: additional selectors for extended mode
        :type: dict | None
        :rtype: T
        """
        # Compute data file location and check for existence
        if StrictVersion(self.api_version) >= StrictVersion('1.5'):
            filename = os.path.join(self.name, suffix if suffix else 'config')
        else:
            filename = "%s%s" % (self.name, '-' + suffix if suffix else '')
        assert filename in self.data_files, "invalid data file: %s (%s)" % (
            filename, ', '.join(self.data_files))
        filename = os.path.join(self.spec_dir, filename + '.yaml')

        if extended:
            # Ensure selectors is a dict
            selectors = {} if selectors is None else selectors

            # Add environment information to selectors
            selectors.update(self.env.to_dict())

            return load_with_config(filename, selectors)
        else:
            with open(filename) as f:
                return yaml.load(f.read())

    def __getitem__(self, key):
        """Access build_space attributes and pre callback values directly.

        Allow accessing all build_space attributes directly by using
        __getitem__, e.g. self['PKG_DIR'] to access
        self.build_space.pkg_dir values.

        Also directly access items returned by the ``pre`` callback.

        :type key: str
        :rtype: T
        """
        if self.build_space is None:
            return 'unknown'
        # first look in the build_space config dictionary
        if key in self.build_space.config:
            return self.build_space.config[key]

        # Then check if the key (in lowercase) in build_space
        elif key.isupper():
            return getattr(self.build_space, key.lower(), None)

    @classmethod
    def primitive(cls, pre=None, post=None, version=None):
        """Declare an anod primitive.

        Store (and check) the fingerprint of the module dependencies
        Store the primitive success flag
        Catch all exceptions and raise AnodError with the traceback

        :param pre: None or a special function to call before running the
            primitive. The function takes a unique parameter `self` and
            returns a dict
        :type pre: None | Anod -> {}
        :param post: None or a callback function to call after running the
            primitive
        :type post: None | () -> None
        :param version: None or a callback function returning the version
            that will be evaluated as a string. This callback is called
            after running the primitive
        :type version: None | () -> str
        :raise: AnodError
        """
        def primitive_dec(f, pre=pre, post=post, version=version):

            def primitive_func(self, *args, **kwargs):
                # Check whether the instance has been activated
                if self.build_space is None:
                    # Not yet activated, fail
                    raise AnodError('AnodDriver.activate() has not been run')

                self.log.debug("%s %s starts", self.name, f.__name__)

                success = False  # Set to True if no exception
                result = False

                # First reset last build status and actual fingerprint. This
                # ensure that even a crash will keep the module in a mode that
                # force its rebuild.
                self.build_space.update_status(self.kind)

                # Ensure temporary directory is set to a directory local to
                # the current sandbox. This avoid mainly to loose track of
                # temporary files that are then accumulating on the
                # filesystems.
                for tmp_var in ('TMP', 'TEMP', 'TMPDIR'):
                    os.environ[tmp_var] = self.build_space.tmp_dir

                try:
                    result = f(self, *args, **kwargs)
                except AnodError as e:
                    self.log.error(e)
                    e += '{name} {action} fails'.format(name=self.name,
                                                        action=f.__name__)
                    raise
                except Exception:
                    self.log.error("%s %s fails", self.name, f.__name__)
                    self.build_space.dump_traceback(self.name, f.__name__)
                else:
                    self.log.debug("%s %s ends", self.name, f.__name__)
                    success = True
                finally:
                    if success:
                        # Don't update status or fingerprint if the primitive
                        # is an installation outside the build space.
                        self.build_space.update_status(
                            kind=self.kind,
                            status=ReturnValue.success,
                            fingerprint=self.fingerprint)
                return result

            primitive_func.is_primitive = True
            primitive_func.pre = pre
            primitive_func.post = post
            primitive_func.version = version
            return primitive_func

        return primitive_dec

    @property
    def package(self):
        """Return binary package creation recipe.

        If None don't create a binary package.

        :rtype: e3.anod.package.Package | None
        """
        return None

    @property
    def component(self):
        """Return component name.

        :rtype: str | None
        """
        return None

    @property
    def source_pkg_build(self):
        """Return list of SourceBuilder defined in the specification file."""
        return None

    @property
    def has_nsis(self):
        """Whether a dependency on NSIS is required.

        :rtype: bool
        """
        # nsis is used only during the builds
        return self.kind == 'build' and self.env.build.os.name == 'windows' \
            and self.package is not None and self.package.nsis is not None

    def shell(self, *command, **kwargs):
        """Run a subprocess using e3.os.process.Run.

        Contrary to what is done in e3.os.process.Run parse_shebang
        defaults to True and output is by default set to the anod
        build space log stream.

        Note that calling shell() raises an exception when the
        process returns an exit code that is not 0.

        :raise: ShellError
        """
        command = parse_command(command, self.build_space)
        if 'parse_shebang' not in kwargs:
            kwargs['parse_shebang'] = True
        if 'output' not in kwargs:
            kwargs['output'] = self.build_space.log_stream
        r = e3.os.process.Run(command, **kwargs)
        if r.status != 0:

            active_log_filename = self.build_space.log_file
            if active_log_filename is None:
                # ??? active_log_filename can be None, e.g. when building the
                # source package.
                raise ShellError(
                    message="%s failed (exit status: %d)" % (
                        " ".join(command), r.status),
                    origin='anod.shell',
                    process=r)
            else:
                # Try to extract the command output that lead to that error
                with open(active_log_filename, 'rb') as fd:
                    content = fd.read()
                index = content.rfind(b'e3.os.process.cmdline')
                content = content[index:]
                index = content.find(b']')

                # Create an exception with 2 messages: the log itself and
                # then the status. This is important not have the log as
                # last message as we might log it again otherwise (calls to
                # error with the exception instance).

                # ??? log analysis call should probably be inserted here.
                exc = ShellError(
                    message=content[index + 2:],
                    origin='anod.shell',
                    process=r)
                exc += "%s failed (exit status: %d)" % (
                    " ".join(command), r.status)
                raise exc
        return r
