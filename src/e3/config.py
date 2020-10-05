"""Read e3 config file."""
from __future__ import annotations
from dataclasses import fields, dataclass

from typing import TYPE_CHECKING, get_type_hints, ClassVar

try:
    from typeguard import check_type

    CONFIG_CHECK_TYPE = True
except ImportError:  # defensive code
    CONFIG_CHECK_TYPE = False


import logging
import os

if TYPE_CHECKING:
    from typing import Type, TypeVar

    T = TypeVar("T", bound="ConfigSection")


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


@dataclass
class ConfigSection:
    title: ClassVar[str]

    @classmethod
    def load(cls: Type[T]) -> T:
        """Load a section of the configuration file.

        To load a new section, subclass ConfigSection and document the
        fields that you expect to parse, e.g.::

            @dataclass
            class MyConfig(ConfigSection):
                title = "my_config_subsection"
                option : str = "default value"

        my_config = MyConfig.load()

        If the package typeguard is installed type defined in the metaclass
        will be verified.
        """
        schema = get_type_hints(cls)
        cls_fields = {f.name: schema[f.name] for f in fields(cls) if f.name != "title"}
        kwargs = {}

        for k, v in Config.load_section(cls.title).items():
            if k in cls_fields:
                ftype = cls_fields[k]
                try:
                    if CONFIG_CHECK_TYPE:
                        check_type(f"{cls.title}.{k}", v, ftype)
                except TypeError as err:
                    logging.error(str(err))
                else:
                    kwargs[k] = v

        return cls(**kwargs)  # type: ignore


class Config:
    """Load e3 configuration file and validate each section.

    This class expose the .load_section(<section>, <dataclass>) method
    that can be used by ConfigSection instance corresponding to the loaded
    configuration section after validation.

    Note that without the tomlkit package the configuration is not read.
    """

    data: ClassVar[dict] = {}

    @classmethod
    def load_section(cls, section: str) -> dict:
        """Load a configuration section content.

        :param section: if contains "." nested subsection will be found. For
            instance "log.fmt" will return the section:

            [log]
              [log.fmt]
        :return: the configuration dict
        """
        if not cls.data:
            cls.load()

        subsections = section.split(".")
        result = cls.data
        for subsection in subsections:
            result = result.get(subsection, {})

        return result

    @classmethod
    def load_file(cls, filename: str) -> None:
        """Load the configuration file(s).

        Note that this method is automatically loaded the first time .get()
        is called.

        :param filename: configuration file to load
        """
        try:
            from tomlkit import parse
            from tomlkit.exceptions import TOMLKitError
        except ImportError:  # defensive code
            logging.error(f"cannot load {filename} (cannot import tomlkit)")
        else:
            with open(filename) as f:
                try:
                    cls.data.update(parse(f.read()))
                except TOMLKitError as e:
                    logging.error(str(e))

    @classmethod
    def load(cls) -> None:
        """Load the configuration file(s).

        Note that this method is automatically loaded the first time .get()
        is called.

        :param filename: if not None load this configuration file instead of
            the default config files
        """
        for config_file in KNOWN_CONFIG_FILES:
            if os.path.isfile(config_file):
                cls.load_file(config_file)
