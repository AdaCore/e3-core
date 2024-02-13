from __future__ import annotations

import pytest

from pathlib import Path
from typing import TYPE_CHECKING

from e3.json import (
    JsonData,
    JsonError,
    JsonDataInvalidJsonError,
    dump_to_json_file,
    load_from_json_file,
)

if TYPE_CHECKING:
    from typing import TypeVar

    ComplexJsonDataSelf = TypeVar("ComplexJsonDataSelf", bound="ComplexJsonData")

# Define some test classes.

DICT_VALUES: dict = {
    "one": 1,
    "two": 2,
}


class AnObject(object):
    def __init__(self, value: dict):
        self.value = value

    def __eq__(self, other: object):
        if isinstance(other, self.__class__):
            return self.value == other.value
        return False


class SimpleJsonData(JsonData):
    def __init__(self, string: str, integer: int, float_var: float):
        self.string: str = string
        self.integer: int = integer
        self.float_var: float = float_var

    def as_dict(self) -> dict[str, object]:
        return {
            "string": self.string,
            "integer": self.integer,
            "float_var": self.float_var,
        }


class ComplexJsonData(JsonData):
    """Example of a JsonData which needs to overwrite the from_dict() method."""

    def __init__(self, data: SimpleJsonData, an_object: AnObject):
        self.data: SimpleJsonData = data
        self.an_object = an_object

    def as_dict(self) -> dict[str, object]:
        return {"data": self.data.as_dict(), "an_object": self.an_object.value}

    @classmethod
    def from_dict(cls: type[ComplexJsonDataSelf], obj: dict) -> ComplexJsonDataSelf:
        return cls(
            data=SimpleJsonData.from_dict(obj["data"]),
            an_object=AnObject(obj["an_object"]),
        )


def test_simple_json_data() -> None:
    """Test a simple JSON data object."""
    simple: SimpleJsonData = SimpleJsonData(
        string="string",
        integer=1234,
        float_var=98765.43210,
    )
    simple_dict: dict = simple.as_dict()
    assert simple.string == "string"
    assert simple_dict["string"] == "string"
    assert simple.integer == 1234
    assert simple_dict["integer"] == 1234
    assert simple.float_var == 98765.43210
    assert simple_dict["float_var"] == 98765.43210

    other_simple: SimpleJsonData = SimpleJsonData.from_dict(simple.as_dict())
    assert simple == other_simple

    # Make sure the __eq__() method returns False on invalid compared object.

    assert simple != "simple"

    # Some simple tests on from_json().

    json_simple: SimpleJsonData = SimpleJsonData.from_json(simple.as_json())
    assert simple == json_simple

    # Check for invalid JSON string initializer.

    with pytest.raises(JsonDataInvalidJsonError):
        SimpleJsonData.from_json('"string"')


def test_complex_json_data() -> None:
    """Test with a complex JSON data object.

    This test is mainly to create an example on when to override the from_dict()
    method.
    """
    an_object = AnObject(DICT_VALUES)
    simple: SimpleJsonData = SimpleJsonData(
        string="string",
        integer=1234,
        float_var=98765.43210,
    )
    cmplx: ComplexJsonData = ComplexJsonData(data=simple, an_object=an_object)

    complex_dict: dict = cmplx.as_dict()

    assert cmplx.data == simple
    assert complex_dict["data"] == simple.as_dict()
    assert cmplx.an_object == an_object
    assert AnObject(complex_dict["an_object"]) == an_object

    other_complex: ComplexJsonData = ComplexJsonData.from_dict(cmplx.as_dict())

    assert cmplx == other_complex


def test_json_files():
    """Tests saving to, and loading from a JSON file."""
    json_path: Path = Path.cwd() / f"{__name__}.json"
    dump_to_json_file(str(json_path), DICT_VALUES)
    print(f"Saved to {json_path}")
    # Now load it, and compare.
    loaded_dict: dict = load_from_json_file(str(json_path))

    assert loaded_dict == DICT_VALUES

    # Check with default value on a non-existing file.
    default_value: str = "default value"
    assert load_from_json_file("does not exist", default=default_value) == default_value

    # Make sure it raises an exception if the ignore_non_existing parameter is
    # False.

    with pytest.raises(JsonError) as je:
        load_from_json_file("does not exist", ignore_non_existing=False)
    assert "json file does not exist does not exist" in je.value.args[0]
