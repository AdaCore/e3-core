from __future__ import absolute_import

from functools import wraps

from e3.anod.spec import AnodError

import e3.log
import e3.store

logger = e3.log.getLogger('e3.anod.driver')


def primitive_check():
    def decorator(func):
        @wraps(func)
        def wrapper(self):
            if not self.anod_instance.has_primitive(func.__name__):
                raise AnodError('no primitive %s' % func.__name__)
        return wrapper
    return decorator


class AnodDriver(object):

    def __init__(self, anod_instance, store):
        """Initialize the Anod driver for a given Anod instance.

        :param anod_instance: an Anod instance
        :type anod_instance: e3.anod.spec.Anod
        :param sandbox: the sandbox where the build should be done
        :type sandbox: e3.anod.sandbox.Sandbox
        :param store: the store backend for accessing source and
            binary packages
        :type store: e3.store.backends.base.Store
        """
        self.anod_instance = anod_instance
        self.anod_instance.activate()
        self.store = store

    def call(self, action):
        """Call an Anod action.

        :param action: the action (build, install, test, ...)
        :type action: str
        """
        return getattr(self, action, self.unknown_action)()

    def unknown_action(self):
        logger.critical('unknown action')
        return False

    @primitive_check()
    def download(self):
        """Run the download primitive."""
        # First check whether there is a download primitive implemented by
        # the Anod spec.
        self.anod_instance.build_space.create(quiet=True)
        if self.anod_instance.has_primitive('download'):
            download_data = self.anod_instance.download()
            metadata = self.store.get_resource_metadata(download_data)
            self.store.download_resource(
                metadata,
                self.anod_instance.build_space.binary_dir)
