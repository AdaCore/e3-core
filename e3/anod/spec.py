from __future__ import absolute_import

import os
from collections import OrderedDict

from e3.anod.error import AnodError
from e3.anod.status import SUCCESS

import e3.anod.deps
import e3.anod.package

import e3.env
import e3.log

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
        raise AnodError('API version mismatch. Anod specs are at %s but the '
                        'driver is only supporting %s' % (
                            version.strip(), ','.join(SUPPORTED_API)))


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
        has been activated with self.activate()
    :vartype anod_id: str | None

    :ivar builder_registered: set a flag to mark the builder as not registered.
        This will be done later when needed.

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

    def __init__(self, qualifier, kind, env=None):
        self.deps = OrderedDict()
        self.build_vars = []
        self.kind = kind

        # Set when self.activate() is called
        self.build_space = None
        self.anod_id = None
        self.log = None

        if env is None:
            self.env = e3.env.BaseEnv(build=e3.env.Env().build,
                                      host=e3.env.Env().host,
                                      target=e3.env.Env().target)
        else:
            self.env = env

        self.fingerprint = None
        self.builder_registered = None

        self.parsed_qualifier = OrderedDict()
        if qualifier:
            for key, _, value in sorted(
                    (item.partition('=') for item in qualifier.split(','))):
                self.parsed_qualifier[key] = value

        # If the Anod module declares some properties, and the function call
        # raises an Exception, the call to hasatt() will return False (meaning
        # that the attribute is not defined). To check whether the attribute is
        # defined we get the list of all defined attributes using `dir`
        attributes = dir(self)

        # Get the module build space, the name of the build space is
        # build_space_name if defined or name (required in .anod specs)
        if 'build_space_name' not in attributes:
            self.build_space_name = self.name

        if not isinstance(self.build_space_name, basestring):
            error_msg = "Error: %s.build_space_name should be a string"
            if callable(self.build_space_name):
                error_msg += ". Is @property missing ?"
            raise AnodError('anod', error_msg % self.name)

        # Register sources, source builders and repositories
        self.source_list = {}

        self.map_attribute_elements(
            lambda x: self.source_list.update({x.name: x}),
            kind + '_source_list')

    def map_attribute_elements(self, function, attribute_name):
        """Iterate other an attribute an apply a function on all elements.

        :param function: function to be called on each element
        :type function: T -> T
        :param attribute_name: the attribute on which we want to iterate
        :type attribute_name: str

        :return: the attribute value or empty tuple is the attribute does not
          exists
        :rtype: T | ()

        :raise AnodError: if we cannot iterate on the attribute.
        """
        if attribute_name in dir(self):
            item_list = getattr(self, attribute_name)
            """:type: list[T]"""
            if isinstance(item_list, basestring):
                raise AnodError('%s cannot be a string' % attribute_name)

            try:
                for item in item_list:
                    function(item)
            except Exception as e:
                # Check if the expected iterable is in fact a callable
                if callable(item_list):
                    raise AnodError(
                        '%s is callable. Maybe you should add a '
                        '@property' %
                        attribute_name), None, sys.exc_traceback

                # Ensure that the attribute is an iterable
                try:
                    iter(item_list)
                except TypeError:
                    raise AnodError(
                        '%s is not an iterable' % attribute_name), \
                        None, sys.exc_traceback

                if isinstance(e, AnodError):
                    raise

                import traceback
                error_msg = 'unknown error when parsing in {anod_id}' \
                            ' attribute {attr}=[{item_list}]'.format(
                                anod_id=self.anod_id,
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

    def activate(self):
        if self.sandbox is None:
            raise AnodError('cannot activate a spec without a sandbox')

        self.build_space = self.sandbox.get_build_space(
            name=self.build_space_name,
            primitive=self.kind,
            platform=self.env.platform)

        # Compute an id that should be unique
        self.anod_id = os.path.relpath(
            self.build_space.root_dir,
            self.sandbox.root_dir).replace('/', '.').replace(
            '\\', '.') + '.' + self.kind

        self.log = e3.log.getLogger('spec.' + self.anod_id)
        e3.log.debug('activating spec %s', self.anod_id)

    def has_primitive(self, name):
        """Return True if the primitive `name` is supported.

        :param name: name of the primitive ('build', 'install'...)
        :type name: str

        :rtype: bool
        """
        try:
            func = getattr(self, name)
            is_primitive = getattr(func, 'is_primitive')
        except AttributeError:
            return False
        return bool(is_primitive)

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
        """

        def primitive_dec(f, pre=pre, post=post, version=version):

            def primitive_func(self, *args, **kwargs):
                # Check whether the instance has been activated
                if self.anod_id is None:
                    # Not yet activated, fail
                    raise AnodError('.activate() has not been run')

                self.log.debug("%s %s starts", self.name, f.__name__)

                success = False  # Set to True if no exception
                result = False

                # First reset last build status and actual fingerprint. This
                # ensure that even a crash will keep the module in a mode that
                # force its rebuild.
                self.update_status()

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
                        self.update_status(
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

    def update_status(self, status=None, fingerprint=None):
        # not implemented yet ???
        pass
