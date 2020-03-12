import abc
import time

DEFAULT_TIMEOUT = 3600 * 24


class Cache(object, metaclass=abc.ABCMeta):
    def __init__(self, cache_configuration):
        self.cache_configuration = cache_configuration

    @abc.abstractmethod
    def get(self, uid, default=None):
        """Fetch a given resource from the cache.

        If the resource does not exist, return default, which itself defaults
        to None.
        :param uid: the resource uid
        :type uid: str
        :param default: the default value if not found
        """
        pass  # all: no cover

    def get_expiry_time(self, timeout=DEFAULT_TIMEOUT):
        """Return the expiry time based upon the provided timeout.

        :param timeout: timeout
        :type timeout: int
        """
        return time.time() + timeout

    def has_resource(self, uid):
        """Return True if the uid is in the cache and has not expired.

        :param uid: the resource uid
        :type uid: uid
        :rtype: bool
        """
        return self.get(uid) is not None

    @abc.abstractmethod
    def set(self, uid, value, timeout=DEFAULT_TIMEOUT):
        """Set a value in the cache.

        :param uid: the cache entry uid
        :type uid: str
        :param value: the object to cache
        :param timeout: timeout to use for caching this value, otherwise the
            default cache timeout will be used.
        :type timeout: int
        :return: True if the value is set, False in case of failure
        :rtype: bool
        """
        pass  # all: no cover

    @abc.abstractmethod
    def delete(self, uid):
        """Delete a resource from the cache.

        Do nothing if the uid does not exist.
        :param uid: the resource uid
        :type uid: str
        """
        pass  # all: no cover

    @abc.abstractmethod
    def clear(self):
        """Remove *all* values from the cache at once."""
        pass  # all: no cover

    def close(self):
        """Close the cache connection."""
        pass  # all: no cover

    def __contains__(self, uid):
        """Return True if the resource is in the cache and has not expired.

        :param uid: the resource uid
        :type uid: str
        """
        return self.has_resource(uid)
