"""Read e3 config file."""
from __future__ import annotations
from dataclasses import fields, is_dataclass

from typing import TYPE_CHECKING, get_type_hints

try:
    from typeguard import check_type

    CONFIG_CHECK_TYPE = True
except ImportError:
    CONFIG_CHECK_TYPE = False


import logging
import os

if TYPE_CHECKING:
    from typing import Callable, ClassVar, TypeVar

    T = TypeVar("T")


if "E3_CONFIG" in os.environ:
    KNOWN_CONFIG_FILES = [os.environ["E3_CONFIG"]]
else:
    KNOWN_CONFIG_FILES = [
        os.path.join(
            os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")),
            "e3.toml",
        ),
        os.path.expanduser("~/e3.toml"),
    ]


class Config:
    """Load e3 configuration file and validate each section.

    This class expose the .get(<section>, <dataclass>) method
    that returns a dataclass instance corresponding to the loaded
    configuration section after validation.

    Note that without the tomlkit package the configuration is not read and
    only default values are kept. If the package typeguard is installed
    type defined in the metaclass will be verified.
    """

    data: ClassVar[dict] = {}

    @classmethod
    def get(cls, section: str, dataclass: Callable[..., T]) -> T:
        """Return the configuration for the given section.

        :param section: name of the section to load
        :param dataclass: dataclass to instantiate with the configuration
        content.
        :return: the dataclass instance
        """
        assert is_dataclass(dataclass)
        if not cls.data:
            cls.load()

        # Given that we use "from __future__ import annotations", fields
        # type are just names (e.g. "bool") instead of the expected types
        # Some magic is needed to get them
        resolved = get_type_hints(dataclass)

        cls_fields = {f.name: resolved[f.name] for f in fields(dataclass)}
        kwargs = {}

        for k, v in cls.data.get(section, {}).items():
            if k in cls_fields:
                ftype = cls_fields[k]
                try:
                    if CONFIG_CHECK_TYPE:
                        check_type(f"{section}.{k}", v, ftype)
                except TypeError as err:
                    logging.error(str(err))
                else:
                    kwargs[k] = v

        return dataclass(**kwargs)

    @classmethod
    def load(cls) -> None:
        """Load the configuration file(s).

        Note that this method is automatically loaded the first time .get()
        is called.
        """
        try:
            from tomlkit import parse
            from tomlkit.exceptions import TOMLKitError
        except ImportError:
            logging.error("cannot load config files (cannot import tomlkit)")
        else:
            for config_file in KNOWN_CONFIG_FILES:
                if os.path.exists(config_file):
                    with open(config_file) as f:
                        try:
                            cls.data.update(parse(f.read()))
                        except TOMLKitError as e:
                            logging.error(str(e))
            return
