from __future__ import absolute_import, division, print_function

from collections import OrderedDict

import e3.log
import e3.yaml
import yaml

import pytest

try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO


@pytest.mark.parametrize('config,expected', [
    ({'param1': 'full', 'param2': 'short'},
     {'y': 0, 'c': '', 'value2': '', 'value1': 10}),
    ({'param1': 'short', 'param2': 'full'},
     {'a': 42, 'c': 'default', 'b': 5, 'value3': 30,
      'value2': 'default', 'value1': 10})])
def test_case_parser(config, expected):

    yaml_case_content = """
case_param1:
    full:
        case_param2:
            full: {'a': 2, 'b': 1, 'c': 'content'}
            short: {'y': 0, 'c': ''}
    short:
        case_param2:
            full: {'a': 9, 'b': 5, 'c': 'default'}
            short: {'y': 3, 'c': ''}

value1: 10
value2: '%(c)s'
case_param2:
    'f.*l': {'value3': 30, 'a': 42}
"""
    d = yaml.load(StringIO(yaml_case_content),
                  e3.yaml.OrderedDictYAMLLoader)
    parse_it = e3.yaml.CaseParser(config).parse(d)
    assert parse_it == expected

    with open('tmp', 'w') as f:
        f.write(yaml_case_content)

    parse_it2 = e3.yaml.load_with_config('tmp', config)
    assert parse_it2 == expected


def test_include():
    with open('1.yaml', 'w') as f:
        f.write('b: !include 2.yaml\n')

    with open('2.yaml', 'w') as f:
        f.write('a: 4\n')

    d = e3.yaml.load_ordered('1.yaml')
    assert d == OrderedDict([('b', OrderedDict([('a', 4)]))])
