from __future__ import absolute_import, division, print_function

import re


def format_with_dict(pattern, values):
    """Safely format a python string using % and a dictionary for values.

    This method is safer than using directly percent as it will escape
    automatically % in the pattern that cannot be replaced.

    :param pattern: a string that should be formatted
    :type pattern: str | unicode
    :param values: a dictionary containing the values of the keys that can be
        replaced
    :type values: dict

    :rtype: str
    """
    key_regexp = r"|".join([r'\(%s\)' % k for k in values])
    result = re.sub(r'%%(?!%s)' % key_regexp, r'%%', pattern)
    return result % values
