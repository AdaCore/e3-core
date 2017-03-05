from __future__ import absolute_import, division, print_function

import sys
from functools import wraps

import e3.log
import e3.store
from e3.anod.spec import AnodError, has_primitive
from e3.error import E3Error

logger = e3.log.getLogger('e3.anod.driver')


def primitive_check():
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            if not has_primitive(self.anod_instance, func.__name__):
                raise AnodError('no primitive %s' % func.__name__)
            elif self.anod_instance.build_space is None:
                raise AnodError('.activate() has not been called')
            return func(self, *args, **kwargs)
        return wrapper
    return decorator


class AnodDriver(object):

    def __init__(self, anod_instance, store):
        """Initialize the Anod driver for a given Anod instance.

        :param anod_instance: an Anod instance
        :type anod_instance: e3.anod.spec.Anod
        :param store: the store backend for accessing source and
            binary packages
        :type store: e3.store.backends.base.Store
        """
        self.anod_instance = anod_instance
        self.store = store

    def activate(self):
        sbx = self.anod_instance.sandbox
        if sbx is None:
            raise AnodError('cannot activate a spec without a sandbox',
                            'activate')

        self.anod_instance.build_space = sbx.get_build_space(
            name=self.anod_instance.build_space_name,
            primitive=self.anod_instance.kind,
            platform=self.anod_instance.env.platform)

        self.anod_instance.log = e3.log.getLogger(
            'spec.' + self.anod_instance.uid)
        e3.log.debug('activating spec %s', self.anod_instance.uid)

    def call(self, action):
        """Call an Anod action.

        :param action: the action (build, install, test, ...)
        :type action: str
        """
        return getattr(self, action, self.unknown_action)()

    @staticmethod
    def unknown_action():
        logger.critical('unknown action')
        return False

    @primitive_check()
    def download(self):
        """Run the download primitive."""
        # First check whether there is a download primitive implemented by
        # the Anod spec.
        self.anod_instance.build_space.create(quiet=True)
        download_data = self.anod_instance.download()
        try:
            metadata = self.store.get_resource_metadata(download_data)
        except E3Error as err:
            self.anod_instance.log.critical(err)
            raise AnodError(
                'cannot get resource metadata from store',
                origin=self.anod_instance.uid), None, sys.exc_traceback
        else:
            self.store.download_resource(
                metadata,
                self.anod_instance.build_space.binary_dir)
