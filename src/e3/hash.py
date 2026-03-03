"""Hash computation utilities (MD5, SHA1, SHA256, SHA512)."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import TYPE_CHECKING

import e3.error

if TYPE_CHECKING:
    from os import PathLike
    from typing import Literal


class HashError(e3.error.E3Error):
    pass


def __compute_hash(
    path: PathLike[str] | str,
    kind: Literal["md5", "sha1", "sha256", "sha512"],
) -> str:
    """Compute hash of a file.

    :param path: path to a file
    :param kind: hash algorithm to use
    """
    if not Path(path).is_file():
        raise HashError(kind, f"cannot find {path}")

    with Path(path).open("rb") as f:
        result = getattr(hashlib, kind)()
        while True:
            data = f.read(1024 * 1024)
            if not data:
                break
            result.update(data)
    return result.hexdigest()


def md5(path: PathLike[str] | str) -> str:
    """Compute md5 hexadecimal digest of a file.

    :param path: path to a file

    :return: the hash of the file content
    :raise HashError: in case of error
    """
    return __compute_hash(path, "md5")


def sha1(path: PathLike[str] | str) -> str:
    """Compute sha1 hexadecimal digest of a file.

    :param str path: path to a file

    :return: the hash of the file content
    :raise HashError: in case of error
    """
    return __compute_hash(path, "sha1")


def sha256(path: PathLike[str] | str) -> str:
    """Compute sha256 hexadecimal digest of a file.

    :param str path: path to a file

    :return: the hash of the file content
    :raise HashError: in case of error
    """
    return __compute_hash(path, "sha256")


def sha512(path: PathLike[str] | str) -> str:
    """Compute sha512 hexadecimal digest of a file.

    :param str path: path to a file

    :return: the hash of the file content
    :raise HashError: in case of error
    """
    return __compute_hash(path, "sha512")
