"""Utility functions related to json."""

from __future__ import annotations

import json
import os

import e3.error

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any, TypeVar

    JsonDataSelf = TypeVar("JsonDataSelf", bound="JsonData")


class JsonError(e3.error.E3Error):
    pass


class JsonDataInvalidJsonError(e3.error.E3Error):
    """An error thrown when input data string does not represent a dictionary."""

    pass


class JsonData(ABC):
    """An object to represent JSON data content."""

    @abstractmethod
    def as_dict(self) -> dict[str, object]:
        """Return the dict representation of this JSON data object."""
        ...

    def __eq__(self, other: object) -> bool:
        """Check if this JSON data is identical to *other*.

        :param other: The object to compare this JSON data with.

        :return: A :class:`bool` set to **True** if both JSON data are
            identical, **False** if they are not, or if *other* is not a
            :class:`JsonData` object.
        """  # noqa RST304
        if isinstance(other, self.__class__):
            return self.as_json() == other.as_json()
        return False

    def as_json(self) -> str:
        """Return a JSON string representing this JSON data.

        .. seealso:: :func:`python:json.dumps`
        """  # noqa RST304
        return json.dumps(self.as_dict(), sort_keys=True)

    @classmethod
    def from_dict(cls: type[JsonDataSelf], obj: dict) -> JsonDataSelf:
        """Load a dictionary as a JSON data object.

        :param obj: The dictionary to initialize the JSON data object with.

        :return: A new :class:`JsonData` object initialized with
            values from the input dictionary.
        """  # noqa RST304
        return cls(**obj)

    @classmethod
    def from_json(cls: type[JsonDataSelf], content: str) -> JsonDataSelf:
        """Load a JSON string as a JSON data object.

        As this method calls for :meth:`from_dict`,  the input *content* string
        **MUST** represent a dictionary. If that's not the case, a
        :class:`JsonDataInvalidJsonError` is thrown.

        :param content: The JSON string to initialize the JSON data object with.

        :return: A new :class:`JsonData` object initialized with
            values from the input dictionary.

        :raise: :class:`JsonDataInvalidJsonError` when *content* string does not
            represent a dictionary.

        .. seealso:: :meth:`as_json`, :meth:`from_dict`
        """  # noqa RST304
        dict_repr: dict = json.loads(content)
        if not isinstance(dict_repr, dict):
            raise JsonDataInvalidJsonError("Invalid JSON string initializer")
        return cls.from_dict(dict_repr)


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
