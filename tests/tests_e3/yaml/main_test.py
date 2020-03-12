import os
from collections import OrderedDict

import e3.log
import e3.yaml
import yaml
import yaml.constructor

import pytest

try:
    from io import StringIO
except ImportError:
    from io import StringIO


@pytest.mark.parametrize(
    "config,expected",
    [
        (
            {"param1": "full", "param2": "short"},
            {"y": 0, "c": "", "value2": "", "value1": 10},
        ),
        (
            {"param1": "short", "param2": "full"},
            {
                "a": 42,
                "c": ["1", "default", "2"],
                "b": 5,
                "value3": 30,
                "value2": "['default']",
                "value1": 10,
            },
        ),
        (
            {"param1": "short", "param2": "dict"},
            {
                "a": 9,
                "c": {"default": "ok", "default2": "nok"},
                "b": 5,
                "value2": "{'default': 'ok'}",
                "value1": 10,
            },
        ),
    ],
)
def test_case_parser(config, expected):
    """Test yaml CaseParser."""
    yaml_case_content = """
case_param1:
    full:
        case_param2:
            full: {'a': 2, 'b': 1, 'c': 'content'}
            short: {'y': 0, 'c': ''}
    short:
        case_param2:
            full: {'a': 9, 'b': 5, 'c': ['default']}
            short: {'y': 3, 'c': ''}
            dict: {'a': 9, 'b': 5, 'c': {'default': 'ok'}}

value1: 10
value2: '%(c)s'
case_param2:
    'f.*l': {'value3': 30, 'a': 42, '+c': ['2'], 'c+': ['1']}
    'dict': {'+c': {'default2': 'nok'}}
"""
    d = yaml.load(StringIO(yaml_case_content), e3.yaml.OrderedDictYAMLLoader)
    parse_it = e3.yaml.CaseParser(config).parse(d)
    assert parse_it == expected

    with open("tmp", "w") as f:
        f.write(yaml_case_content)

    parse_it2 = e3.yaml.load_with_config("tmp", config)
    assert parse_it2 == expected


def test_case_parser_object():
    """CaseParser supports any objects."""
    yaml_case_content = """
case_v:
    .*:
        dt: !!python/object/apply:time.gmtime []

result: '%(dt)s'
    """
    d = yaml.load(StringIO(yaml_case_content), e3.yaml.OrderedDictYAMLLoader)
    parse_it = e3.yaml.CaseParser({"v": "true"}).parse(d)
    assert "time.struct_time" in parse_it["result"]


def test_case_parser_err():
    """Test CaseParser error handling."""
    yaml_case_content = "result: '%(dt)s'"
    d = yaml.load(StringIO(yaml_case_content), e3.yaml.OrderedDictYAMLLoader)
    parse_it = e3.yaml.CaseParser({}).parse(d)
    assert parse_it["result"] == "%(dt)s"


def test_include():
    """Test yaml !include."""
    with open("1.yaml", "w") as f:
        f.write("b: !include 2.yaml\n")
        f.write("c: !include %s\n" % os.path.join(os.getcwd(), "2.yaml"))

    with open("2.yaml", "w") as f:
        f.write("a: 4\n")

    d = e3.yaml.load_ordered("1.yaml")
    assert d == OrderedDict(
        [("b", OrderedDict([("a", 4)])), ("c", OrderedDict([("a", 4)]))]
    )

    with pytest.raises(IOError) as err:
        yaml.load("b: !include foo.yaml\n", e3.yaml.OrderedDictYAMLLoader)
    assert "No such file or directory" in str(err.value)
    assert "foo.yaml" in str(err.value)


def test_duplicatekey():
    """Duplicated key should be rejected by load_ordered."""
    with open("dup.yaml", "w") as f:
        f.write("b: 2\nb: 9")

    with pytest.raises(yaml.constructor.ConstructorError) as err:
        e3.yaml.load_ordered("dup.yaml")
    assert "found duplicate key (b)" in str(err.value)


def test_yaml_err():
    """Test load_ordered error handling."""
    with open("err.yaml", "w") as f:
        f.write("[1]: 2\n")

    with pytest.raises(yaml.constructor.ConstructorError) as err:
        e3.yaml.load_ordered("err.yaml")
    assert "found unacceptable key" in str(err.value)

    with open("err2.yaml", "w") as f:
        f.write("--- !!map [not, a, map]\n")

    with pytest.raises(yaml.constructor.ConstructorError) as err:
        e3.yaml.load_ordered("err2.yaml")
    assert "expected a mapping node" in str(err.value)


def test_load_with_config_err():
    """Test load_with_config error handling."""
    with pytest.raises(e3.yaml.YamlError) as err:
        e3.yaml.load_with_config("/does/not/exist", {})
    assert "cannot read" in str(err.value)

    with open("err.yaml", "w") as f:
        f.write('"o" "o" "o"')

    with pytest.raises(e3.yaml.YamlError) as err:
        e3.yaml.load_with_config("err.yaml", {})
    assert "invalid yaml" in str(err.value)


def test_load_with_regexp():
    """Test load_with_regexp."""
    with open("regexp1.yaml", "w") as f:
        f.write(
            "key1: [['ppc-vx6-.*', 'qemu-toto', 'FALSE'],"
            " ['ppc-vx6-.*', 'qemu.*', '%(data)s']]\n"
        )
        f.write(
            "key2: [['ppc-vx6-linux', '', ['TRUE', '%(data)s']],"
            " ['ppc-vx6.*', 'qemu.*', ['FALSE']]]\n"
        )
    selectors = ["ppc-vx6-linux", "qemu"]
    data = {"data": "TRUE"}

    result = e3.yaml.load_with_regexp_table(
        filename="regexp1.yaml", selectors=selectors, data=data
    )

    assert len(result) == 2
    assert result["key1"] == "TRUE"
    assert result["key2"][0] == "TRUE"
    assert result["key2"][1] == "TRUE"
