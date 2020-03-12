import errno
import os
import sys
import tempfile
import time

import e3.log
from e3.fs import mkdir, rm
from e3.store.cache.backends.base import DEFAULT_TIMEOUT, Cache

try:
    import pickle as pickle
except ImportError:  # defensive code
    import pickle


class FileCache(Cache):

    cache_suffix = ".cache"

    def __init__(self, cache_configuration):
        super(FileCache, self).__init__(cache_configuration)
        self.cache_dir = cache_configuration["cache_dir"]

    def clear(self):
        rm(os.path.join(self.cache_dir, "*.cache"))

    def delete(self, uid):
        rm(self.uid_to_file(uid))

    def _create_cache_dir(self):
        mkdir(self.cache_dir)

    def uid_to_file(self, uid):
        """Convert a resource uid to a cache file path.

        This backend assumes that the uid is a safe value for a file name.
        :param uid: the resource uid
        :type uid: str
        :rtype: str
        """
        return os.path.join(self.cache_dir, uid + self.cache_suffix)

    @staticmethod
    def _is_expired(fd):
        """Determine if an open cache file has expired.

        Automatically delete the file if it has passed its expiry time.
        """
        exp = pickle.load(fd)
        if exp is not None and exp < time.time():
            fd.close()
            rm(fd.name)
            return True
        return False

    def get(self, uid, default=None):
        cache_file = self.uid_to_file(uid)
        try:
            with open(cache_file, "rb") as fd:
                if not self._is_expired(fd):
                    return pickle.load(fd)
        except IOError as err:
            if err.errno == errno.ENOENT:
                pass  # Cache file was removed after the exists check
        return default

    def set(self, uid, value, timeout=DEFAULT_TIMEOUT):
        # Make sure that the cache dir exists
        self._create_cache_dir()
        dest_file = self.uid_to_file(uid)

        tmp_file = tempfile.NamedTemporaryFile(dir=self.cache_dir, delete=False)
        try:
            tmp_file.write(
                pickle.dumps(self.get_expiry_time(timeout), pickle.HIGHEST_PROTOCOL)
            )
            tmp_file.write(pickle.dumps(value, pickle.HIGHEST_PROTOCOL))
        except Exception as err:
            tmp_file.close()
            e3.log.debug("error when setting %s in %s:\n%s", uid, dest_file, err)
            return False
        else:
            tmp_file.close()

            if sys.platform == "win32":  # unix: no cover
                # atomic rename does not work on windows if the dest file
                # already exist
                rm(dest_file)
            os.rename(tmp_file.name, dest_file)
            return True

        finally:
            rm(tmp_file.name)
