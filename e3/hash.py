import hashlib
import os

import e3.error


class HashError(e3.error.E3Error):
    pass


def __compute_hash(path, kind):
    if not os.path.isfile(path):
        raise HashError(kind, "cannot find %s" % path)

    with open(path, "rb") as f:
        result = getattr(hashlib, kind)()
        while True:
            data = f.read(1024 * 1024)
            if not data:
                break
            result.update(data)
    return result.hexdigest()


def md5(path):
    """Compute md5 hexadecimal digest of a file.

    :param str path: path to a file

    :return: the hash of the file content
    :rtype: str
    :raise HashError: in case of error
    """
    return __compute_hash(path, "md5")


def sha1(path):
    """Compute sha1 hexadecimal digest of a file.

    :param str path: path to a file

    :return: the hash of the file content
    :rtype: str
    :raise HashError: in case of error
    """
    return __compute_hash(path, "sha1")


def sha256(path):
    """Compute sha256 hexadecimal digest of a file.

    :param str path: path to a file

    :return: the hash of the file content
    :rtype: str
    :raise HashError: in case of error
    """
    return __compute_hash(path, "sha256")
