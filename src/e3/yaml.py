"""Modification of the yaml loader for E3."""


import os
import re
import sys
from collections import OrderedDict

import e3.log
import yaml
import yaml.constructor
import yaml.parser
from e3.text import format_with_dict

try:
    from yaml import CLoader as Loader
except ImportError:  # defensive code
    from yaml import Loader


class YamlError(Exception):
    pass


class OrderedDictYAMLLoader(Loader):
    """A YAML loader that loads mappings into ordered dictionaries.

    The loader also support the !include constructor that allows
    inclusion of yaml files into another yaml
    """

    def __init__(self, stream):
        self.name = None
        self.stream = stream
        super(OrderedDictYAMLLoader, self).__init__(stream)

        self.add_constructor("tag:yaml.org,2002:map", type(self).construct_yaml_map)
        self.add_constructor("tag:yaml.org,2002:omap", type(self).construct_yaml_map)
        self.add_constructor("!include", type(self).yaml_include)

    def yaml_include(self, node):
        # Get the path out of the yaml file
        if self.name is None:
            if not isinstance(self.stream, str) or isinstance(self.stream, str):
                self.name = getattr(self.stream, "name", None)

        if self.name is not None and os.path.isfile(self.name):
            file_name = os.path.join(os.path.dirname(self.name), node.value)
        else:
            file_name = node.value

        with open(file_name, "rb") as inputfile:
            return yaml.load(inputfile, OrderedDictYAMLLoader)

    def construct_yaml_map(self, node):
        data = OrderedDict()
        yield data
        value = self.construct_mapping(node)
        data.update(value)

    def construct_mapping(self, node, deep=False):
        if isinstance(node, yaml.MappingNode):
            self.flatten_mapping(node)
        else:
            raise yaml.constructor.ConstructorError(
                context=None,
                context_mark=None,
                problem="expected a mapping node, but found %s" % node.id,
                problem_mark=node.start_mark,
            )

        mapping = OrderedDict()
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            try:
                hash(key)
            except TypeError as exc:
                raise yaml.constructor.ConstructorError(
                    context="while constructing a mapping",
                    context_mark=node.start_mark,
                    problem="found unacceptable key (%s)" % exc,
                    problem_mark=key_node.start_mark,
                )
            value = self.construct_object(value_node, deep=deep)
            if key in mapping:
                raise yaml.constructor.ConstructorError(
                    context="while constructing a mapping",
                    context_mark=node.start_mark,
                    problem="found duplicate key (%s)" % key,
                    problem_mark=key_node.start_mark,
                )
            mapping[key] = value
        return mapping


def load_ordered(filename):
    """Load a .yaml file, keep the file order.

    :type filename: str

    :rtype: OrderedDict
    """
    with open(filename) as f:
        return yaml.load(f, OrderedDictYAMLLoader)


class CaseParser(object):
    """Parse case statements in an OrderedDict.

    Each time a key starting with ``case_`` (or the prefix you choose) if
    found, in a block mapping, the value of the sub block matching the key
    value is added to the result dictionary.

    For instance: with an initial config
    ``{'param1': 'full', 'param2': 'short'}``, the result of the parsing of:

    .. code-block:: yaml

        {'case_param1': {
            'full': {
                'case_param2': {
                    'full': {'a': 2, 'b': 1, 'c': 'content'},
                    'short': {'y': 0, 'c': ''}}},
            'short': {
                'case_param2': {
                    'full': {'a': 9, 'b': 5, 'c': 'default'},
                    'short': {'y': 3, 'c': ''}}}},
         'value1': 10,
         'value2': '%(c)s',
         'case_param2' : {
                'f.*l': {'value3': 30, 'a': 42}}}

    is ``{'y': 0, 'c': '', 'value2': '', 'value1': 10}``

    and with ``{'param1': 'short', 'param2': 'full'}`` we get:

    .. code-block:: yaml

          {'a': 42, 'c': 'default', 'b': 5, 'value3': 30,
           'value2': 'default', 'value1': 10}

    Note that values can be redefined and that you can add a python regexp, as
    supported by the `re` module, in your case values.
    """

    def __init__(self, initial_config, case_prefix="case_"):
        self.__state = initial_config.copy()
        self.case_prefix = case_prefix

        # This contains the list of keys that have been updated. This
        # allow us to remove the keys part of initial_config that are
        # not modified.
        self.keys = set()

    def __parse_case(self, case_key, data):
        """Parse a case statement.

        :param case_key: the variable on which the case is evaluated
        :type case_key: str
        :param data: the dictionary of case conditions
        :type data: dict

        :return: the value of the matched element or None
        """
        key = case_key[len(self.case_prefix) :]
        key_val = str(self.__state[key])

        result = next(
            ((key_val, k, data[k]) for k in data if re.match("^%s$" % k, key_val)), None
        )
        if result is not None:
            e3.log.debug("%s=%s match %s", key, result[0], result[1])
            return result[2]
        else:
            return None

    def __format_value(self, value):
        """Format a value.

        :param value: the value to be formatted

        :return: the result of the expansion
        """
        try:
            if isinstance(value, str):
                return format_with_dict(value, self.__state)
            elif isinstance(value, dict):
                return {k: self.__format_value(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [self.__format_value(d) for d in value]
        except (KeyError, TypeError):
            e3.log.debug("Cannot format %s, ignore it", value)

        return value

    def __update_state(self, key, value, cursor, prefix):
        """Update state.

        :param key: the key to modify. Leading or trailing '+' in the key name
            are interpreted respectively as append and prepend operators.
            For dictionaries these operators are interpreted as an update
            on the original value.
        :type key: str
        :param value: the new value
        :param cursor: the object to be updated
        :param prefix: a tuple of string that gives the position of cursor in
            self.__state. This is used only for debugging purposes
        """
        real_key = key.strip("+")
        real_value = self.__format_value(value)

        # Update the list of keys that should be considered in the final
        # result
        if cursor is self.__state:
            self.keys.add(real_key)

        real_key_str = "[%s]" % "][".join(prefix + (real_key,))

        if real_key not in cursor or real_key == key:
            e3.log.debug("set %s -> %s", real_key_str, real_value)
            cursor[real_key] = real_value
        else:
            if isinstance(cursor[real_key], dict):
                e3.log.debug("update %s -> %s", real_key_str, real_value)
                cursor[real_key].update(real_value)
            else:
                if key.startswith("+"):
                    e3.log.debug("append %s -> %s", real_key_str, real_value)
                    cursor[real_key] = cursor[real_key] + real_value
                elif key.endswith("+"):
                    e3.log.debug("prepend %s -> %s", real_key_str, real_value)
                    cursor[real_key] = real_value + cursor[real_key]

    def parse(self, data):
        """Parse.

        :param data: a python object. Note that dictionaries in that structure
            should be OrderedDict.

        :return: a new python object after expansion of case statements and
            formatting of values
        """
        return self.__parse(data, self.__state, ())

    def __parse(self, data, cursor, prefix):
        """Parse (internal).

        :param data: a python object. Note that dictionaries in that structure
            should be OrderedDict.
        :param cursor: a ref to a substructure of self.__state
        :param prefix: the current location in self.__state (a tuple of keys)

        :return: the new cursor object
        """
        if not isinstance(data, dict):
            return self.__format_value(data)

        for key in data:
            if key.startswith(self.case_prefix):
                pc = self.__parse_case(key, data[key])
                if pc is not None:
                    result = self.__parse(pc, cursor, prefix)
                    if not isinstance(result, dict):
                        assert len(list(data.keys())) == 1, "invalid configuration file"
                        return result
            else:
                subcursor = cursor.get(key.strip("+"), {})
                subprefix = prefix + (key.strip("+"),)
                self.__update_state(
                    key,
                    self.__parse(data[key], cursor=subcursor, prefix=subprefix),
                    cursor,
                    prefix,
                )

        if cursor is self.__state:
            return {k: v for k, v in cursor.items() if k in self.keys}
        else:
            return cursor


def load_with_config(filename, config):
    """Load yaml config files with case statement handling.

    :param filename: a path or list of path. When a list of path
        is given, config files are loaded in order each one
        updating the result of the previous parsing.
    :type filename: str | list[str]
    :param config: initial state
    :type config: dict

    :return: the final object
    """
    if isinstance(filename, str):
        filename = [filename]

    result = None
    parser = CaseParser(config)

    for f in filename:
        try:
            e3.log.debug("load config file: %s", f)
            conf_data = load_ordered(f)
            result = parser.parse(conf_data)
        except IOError:
            raise YamlError("cannot read: %s" % f, "load_with_config").with_traceback(
                sys.exc_info()[2]
            )
        except (yaml.parser.ParserError, yaml.constructor.ConstructorError) as e:
            raise YamlError(
                "%s is an invalid yaml file: %s" % (f, e), "load_with_config"
            ).with_traceback(sys.exc_info()[2])

    return result


def load_with_regexp_table(filename, selectors, data):
    """Load a yaml file using regexp tables.

    :param filename: the yaml file to load
    :type filename: str
    :param selectors: a list of string that will be used to match the regexps
        in table
    :type selectors: list[str]
    :param data: a dictionary used to replace part of value content
    :type data: dict

    :rtype: dict

    This function expect a yaml file that has the following format::

        key1:
            [['regexp1_1', ..., 'regexp1_n', value],
             ['regexp2_1', ..., 'regexp2_n', value],...

        key2:
            ...

    The returned dictionary will have key1, key2, ... as keys. For each key
    the value is the last element of the first sublist for which the n first
    first regexp do match, strings in selectors list. So in the yaml file each
    sublist associated with each key should have exactly ``len(selectors) + 1``
    elements.
    """
    e3.log.debug("load %s with %s", filename, selectors)
    with open(filename) as f:
        conf_data = yaml.load(f.read(), OrderedDictYAMLLoader)

    assert isinstance(conf_data, dict), (
        "top level object in %s should be a dict" % filename
    )

    result = {}

    for key in conf_data:
        key_data = conf_data[key]
        assert isinstance(key_data, list), "value for key %s is not a list" % key

        for line in key_data:
            assert isinstance(line, list), (
                "value for key %s should be a list of list" % key
            )
            assert len(line) == len(selectors) + 1

            has_matched = True
            for index, r in enumerate(line[0:-1]):
                if len(r) == 0:
                    r = ".*"
                if not re.search(r"^%s$" % r, str(selectors[index])):
                    has_matched = False

            if has_matched:
                result[key] = line[-1]
                break

    # At this stage we have our dictionnary filled. Now use data to replace to
    # replace %()s strings.

    for key in result:
        if isinstance(result[key], str):
            result[key] = result[key] % data
        elif isinstance(result[key], list):
            result[key] = [k % data for k in result[key]]

    e3.log.debug("yaml results: %s", result)
    return result
