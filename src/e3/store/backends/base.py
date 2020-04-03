from __future__ import annotations

import abc
from collections import namedtuple
from typing import TYPE_CHECKING

import e3.log
from e3.error import E3Error

if TYPE_CHECKING:
    from typing import Any, Optional
    from e3.store.cache.backends.base import Cache

logger = e3.log.getLogger("store")


class ResourceInfo(metaclass=abc.ABCMeta):
    """Object representing resource metadata.

    This is subclassed by all store drivers.
    """

    @abc.abstractproperty
    def uid(self) -> str:
        """Return an unique identifier.

        This is meant to be used to implement a cache system.
        """
        pass  # all: no cover

    @abc.abstractmethod
    def verify(self, resource_path: str) -> bool:
        """Verify that a downloaded resource is valid.

        This is meant to validate the resource fingerprint (e.g. sha1sum).
        :param resource_path: path to the downloaded resource
        """
        pass  # all: no cover


class CachedResource(namedtuple("CachedResource", ["uid", "local_path"])):
    """Cached information about an already downloaded resource."""

    __slots__ = ()


class StoreError(E3Error):
    pass


class Store(metaclass=abc.ABCMeta):
    def __init__(self, store_configuration: Any, cache_backend: Cache):
        """Initialize a Store object.

        :param store_configuration: configuration for this store
        :param cache_backend: a Cache instance
        :return:
        """
        self.store_configuration = store_configuration
        self.cache_backend = cache_backend

    @abc.abstractmethod
    def get_resource_metadata(self, query: dict) -> ResourceInfo:
        """Get a resource metadata from query.

        :param query: a dictionary containing store specific queries to
            identify a resource
        """
        pass  # all: no cover

    def download_resource(self, metadata: ResourceInfo, dest: str) -> Optional[str]:
        """Download a resource identified by its metadata in dest.

        :param metadata: resource metadata
        :param dest: directory where the resource will be stored
        :return: resource path
        """
        cached_data = self.cache_backend.get(metadata.uid)
        if cached_data is not None:
            try:
                local_path = cached_data.local_path
            except (TypeError, AttributeError):
                logger.warning("invalid cache entry for %s", metadata.uid)
            else:
                if not metadata.verify(local_path):
                    logger.warning("corrupted cache entry for %s", metadata.uid)
                    # Discard invalid cache entry
                    self.cache_backend.delete(metadata.uid)
                else:
                    return local_path

        # else not in cache
        local_path = self.download_resource_content(metadata, dest)
        if local_path is None:
            # cannot get the resource
            return None

        # store the resource in the cache
        self.cache_backend.set(
            metadata.uid, CachedResource(uid=metadata.uid, local_path=local_path)
        )
        return local_path

    @abc.abstractmethod
    def download_resource_content(
        self, metadata: ResourceInfo, dest: str
    ) -> Optional[str]:
        """Download a resource identified by its metadata in dest.

        The resource is supposed to be validated with metadata.verify
        once the download is completed.

        :param metadata: resource metadata
        :param dest: directory where the resource will be stored
        :return: resource path
        """
        pass  # all: no cover
