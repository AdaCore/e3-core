"""Utility functions related to json."""


import json
import os

import e3.error


class JsonError(e3.error.E3Error):
    pass


def dump_to_json_file(path, obj):
    """Dump a Python object to a json file.

    :param path: path to the json file
    :type path: str
    :param obj: a Python object that can serialized to JSON
    :type obj: object
    """
    with open(path, "w") as fd:
        json.dump(obj, fd, indent=2)


def load_from_json_file(path, default=None, ignore_non_existing=True):
    """Load a Python object from a JSON file.

    :param path: json file path
    :type path: str
    :param default: default value returned if ignore_non_existing is True and
        the specified file does not exist.
    :type default: object
    :param ignore_non_existing: if False raise JsonError if the file does not
        exist, otherwise return default value
    :type ignore_non_existing: bool
    :return: a Python object
    :rtype: object
    """
    if os.path.isfile(path):
        with open(path, "r") as fd:
            content = json.load(fd)
        return content
    else:
        if ignore_non_existing:
            return default
        else:
            raise JsonError("json file %s does not exist" % path)
