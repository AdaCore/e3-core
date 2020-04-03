from __future__ import annotations

from typing import TYPE_CHECKING

import abc
import time

if TYPE_CHECKING:
    from typing import Any

DEFAULT_TIMEOUT = 3600 * 24


class Cache(metaclass=abc.ABCMeta):
    def __init__(self, cache_configuration: Any):
        self.cache_configuration = cache_configuration

    @abc.abstractmethod
    def get(self, uid: str, default: Any = None) -> Any:
        """Fetch a given resource from the cache.

        If the resource does not exist, return default, which itself defaults
        to None.
        :param uid: the resource uid
        :param default: the default value if not found
        """
        pass  # all: no cover

    def get_expiry_time(self, timeout: int = DEFAULT_TIMEOUT) -> float:
        """Return the expiry time based upon the provided timeout.

        :param timeout: timeout
        """
        return time.time() + timeout

    def has_resource(self, uid: str) -> bool:
        """Return True if the uid is in the cache and has not expired.

        :param uid: the resource uid
        """
        return self.get(uid) is not None

    @abc.abstractmethod
    def set(self, uid: str, value: Any, timeout: int = DEFAULT_TIMEOUT) -> bool:
        """Set a value in the cache.

        :param uid: the cache entry uid
        :param value: the object to cache
        :param timeout: timeout to use for caching this value, otherwise the
            default cache timeout will be used.
        :return: True if the value is set, False in case of failure
        """
        pass  # all: no cover

    @abc.abstractmethod
    def delete(self, uid: str) -> None:
        """Delete a resource from the cache.

        Do nothing if the uid does not exist.
        :param uid: the resource uid
        """
        pass  # all: no cover

    @abc.abstractmethod
    def clear(self) -> None:
        """Remove *all* values from the cache at once."""
        pass  # all: no cover

    def close(self) -> None:
        """Close the cache connection."""
        pass  # all: no cover

    def __contains__(self, uid: str) -> bool:
        """Return True if the resource is in the cache and has not expired.

        :param uid: the resource uid
        """
        return self.has_resource(uid)
