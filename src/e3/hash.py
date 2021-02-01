from __future__ import annotations

from typing import TYPE_CHECKING

import hashlib
import os

import e3.error

if TYPE_CHECKING:
    from typing import Literal


class HashError(e3.error.E3Error):
    pass


def __compute_hash(
    path: str, kind: Literal["md5"] | Literal["sha1"] | Literal["sha256"]
) -> str:
    if not os.path.isfile(path):
        raise HashError(kind, f"cannot find {path}")

    with open(path, "rb") as f:
        result = getattr(hashlib, kind)()
        while True:
            data = f.read(1024 * 1024)
            if not data:
                break
            result.update(data)
    return result.hexdigest()


def md5(path: str) -> str:
    """Compute md5 hexadecimal digest of a file.

    :param path: path to a file

    :return: the hash of the file content
    :raise HashError: in case of error
    """
    return __compute_hash(path, "md5")


def sha1(path: str) -> str:
    """Compute sha1 hexadecimal digest of a file.

    :param str path: path to a file

    :return: the hash of the file content
    :raise HashError: in case of error
    """
    return __compute_hash(path, "sha1")


def sha256(path: str) -> str:
    """Compute sha256 hexadecimal digest of a file.

    :param str path: path to a file

    :return: the hash of the file content
    :raise HashError: in case of error
    """
    return __compute_hash(path, "sha256")
