from __future__ import absolute_import

import os
from collections import OrderedDict

from e3.anod.error import AnodError, SpecError, ShellError
from e3.anod.status import SUCCESS

import e3.anod.deps
import e3.anod.package

import e3.env
import e3.log
import e3.os.process
import e3.text

import sys

# CURRENT API version
__version__ = '1.4'

SUPPORTED_API = (__version__,)
# The driver can support multiple version of the spec API, we currently support
# only the version 1.4.

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


def map_attribute_elements(anod_instance, function, attribute_name):
    """Iterate other an attribute an apply a function on all elements.

    :param anod_instance: an anod instance
    :type anod_instance: Anod
    :param function: function to be called on each element
    :type function: T -> T
    :param attribute_name: the attribute on which we want to iterate
    :type attribute_name: str

    :return: the attribute value or empty tuple is the attribute does not
      exists
    :rtype: T | ()

    :raise: SpecError if we cannot iterate on the attribute, or AnodError
    """
    if attribute_name in dir(anod_instance):
        item_list = getattr(anod_instance, attribute_name)
        """:type: list[T]"""
        if isinstance(item_list, basestring):
            raise SpecError(
                '%s cannot be a string' % attribute_name,
                'map_attribute_elements')

        try:
            for item in item_list:
                function(item)
        except Exception as e:
            # Check if the expected iterable is in fact a callable
            if callable(item_list):
                raise SpecError(
                    '%s is callable. Maybe you should add a @property' %
                    attribute_name,
                    'map_attribute_elements'), None, sys.exc_traceback

            # Ensure that the attribute is an iterable
            try:
                iter(item_list)
            except TypeError:
                raise SpecError(
                    '%s is not an iterable' % attribute_name,
                    'map_attribute_elements'), None, sys.exc_traceback

            if isinstance(e, AnodError):
                raise

            import traceback
            error_msg = 'unknown error when parsing in {anod_id}' \
                ' attribute {attr}=[{item_list}]'.format(
                    anod_id=anod_instance.anod_id,
                    attr=attribute_name,
                    item_list=", ".join(
                        '({})'.format(it) for it in item_list))
            _, _, exc_traceback = sys.exc_info()
            error_msg += '\nError: {}\n'.format(e)

            if 'invalid syntax' in error_msg:
                # Syntax error when executing the code
                pass
            else:
                # Unknown error, add a traceback
                error_msg += "Traceback for map_attribute_elements:\n"
                error_msg += "\n".join(traceback.format_tb(exc_traceback))
            raise AnodError(error_msg)
        return item_list
    else:
        return ()


def has_primitive(anod_instance, name):
    """Return True if the primitive `name` is supported.

    :param anod_instance: an Anod instance
    :type anod_instance: Anod
    :param name: name of the primitive ('build', 'install'...)
    :type name: str

    :rtype: bool
    """
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

    :cvar sandbox: e3.anod.sandbox.SandBox object shared by all Anod instances
    :vartype sandbox: e3.anod.sandbox.SandBox | None
    :cvar source_pkg_build: a dictionary associating Anod.SourceBuilder to the
        Anod.Source names
    :cvar name: specification file baseline without the .anod extension. This
        is set when loading the spec.
    :cvar package: ???

    :ivar anod_id: unique identifier for the instance, None until the instance
        has been activated with AnodDriver.activate()
    :vartype anod_id: str | None
    """
    sandbox = None
    source_pkg_build = None
    name = ''
    package = None

    Dependency = e3.anod.deps.Dependency
    Package = e3.anod.package.Package
    Source = e3.anod.package.Source
    SourceBuilder = e3.anod.package.SourceBuilder
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
        self.anod_id = None
        self.log = None

        # Build space name is computed as self.name + self.build_space_suffix
        self.build_space_suffix = ''

        if env is None:
            self.env = e3.env.BaseEnv(build=e3.env.Env().build,
                                      host=e3.env.Env().host,
                                      target=e3.env.Env().target)
        else:
            self.env = env

        self.fingerprint = None

        self.parsed_qualifier = OrderedDict()
        if qualifier:
            qual_dict = dict((key, value) for key, _, value in sorted(
                (item.partition('=') for item in qualifier.split(','))))
        else:
            qual_dict = {}

        for qual_key in getattr(self, '%s_qualifier_format' % self.kind, ()):
            key, is_required = qual_key
            value = qual_dict.get(key)
            if not is_required and value is None:
                pass
            elif value is None:
                raise AnodError(
                    message='the qualifier key %s is required for running'
                    ' %s %s' % (key, self.kind, self.name),
                    origin='anod.__parse_qualifier')
            else:
                self.parsed_qualifier[key] = qual_dict[key]
                self.build_space_suffix = '%s=%s' % (key, qual_dict[key])
                del qual_dict[key]

        if qual_dict:
            raise AnodError(
                message='the following keys in the qualifier were not '
                'parsed: %s' % ','.join(qual_dict.keys()),
                origin='anod.__parse_qualifier')

        # Register sources, source builders and repositories
        self.source_list = {}

        map_attribute_elements(
            self,
            lambda x: self.source_list.update({x.name: x}),
            kind + '_source_list')

    @classmethod
    def primitive(cls, pre=None, post=None, version=None):
        """Decorator for anod primitives.

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
                if self.anod_id is None:
                    # Not yet activated, fail
                    raise AnodError('AnodDriver.activate() has not been run')

                self.log.debug("%s %s starts", self.name, f.__name__)

                success = False  # Set to True if no exception
                result = False

                # First reset last build status and actual fingerprint. This
                # ensure that even a crash will keep the module in a mode that
                # force its rebuild.
                self.build_space.update_status()

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
                            status=SUCCESS,
                            fingerprint=self.fingerprint)
                return result

            primitive_func.is_primitive = True
            primitive_func.pre = pre
            primitive_func.post = post
            primitive_func.version = version
            return primitive_func

        return primitive_dec

    @property
    def has_package(self):
        """Whether a binary package can be created by the spec.

        :rtype: bool
        """
        return self.package is not None and self.package.name is not None

    @property
    def has_nsis(self):
        """Whether a dependency on NSIS is required.

        :rtype: bool
        """
        # nsis is used only during the builds
        return self.kind == 'build' and self.env.build.os.name == 'windows' \
            and self.has_package and self.package.nsis_cb is not None

    def shell(self, *command, **kwargs):
        """Run a subprocess using e3.os.process.Run."""
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
                index = content.rfind('e3.os.process.cmdline')
                content = content[index:]
                index = content.find(']')

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
