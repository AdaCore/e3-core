try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO

import pytest
import yaml
import e3.yaml
import e3.log

e3.log.activate()
e3.log.e3_debug_logger = True


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
