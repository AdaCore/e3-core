"""Utility functions related to json."""


from __future__ import annotations

import json
import os

import e3.error

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any


class JsonError(e3.error.E3Error):
    pass


def dump_to_json_file(path: str, obj: Any) -> None:
    """Dump a Python object to a json file.

    :param path: path to the json file
    :param obj: a Python object that can serialized to JSON
    """
    with open(path, "w") as fd:
        json.dump(obj, fd, indent=2)


def load_from_json_file(
    path: str, default: Any = None, ignore_non_existing: bool = True
) -> Any:
    """Load a Python object from a JSON file.

    :param path: json file path
    :param default: default value returned if ignore_non_existing is True and
        the specified file does not exist.
    :param ignore_non_existing: if False raise JsonError if the file does not
        exist, otherwise return default value
    :return: a Python object
    """
    if os.path.isfile(path):
        with open(path) as fd:
            content = json.load(fd)
        return content
    else:
        if ignore_non_existing:
            return default
        else:
            raise JsonError(f"json file {path} does not exist")
