from __future__ import annotations

import re
from typing import Dict


def format_with_dict(pattern: str, values: Dict[str, str]) -> str:
    """Safely format a python string using % and a dictionary for values.

    This method is safer than using directly percent as it will escape
    automatically % in the pattern that cannot be replaced.

    :param pattern: a string that should be formatted
    :param values: a dictionary containing the values of the keys that can be
        replaced
    """
    key_regexp = r"|".join([fr"\({k}\)" for k in values])
    result = re.sub(r"%%(?!%s)" % key_regexp, r"%%", pattern)
    return result % values


def bytes_as_str(content: bytes) -> str:
    """Safely convert bytes to a python string.

    This function attempts the conversion assuming a utf-8 enconding.
    If this triggers a conversion error, it then falls back to a safe
    representation, where some characters might be escaped.

    :param content: content to be transformed
    :return: a string
    """
    try:
        result = content.decode("utf-8")
    except UnicodeDecodeError:
        result = str(content)[2:-1].replace("\\n", "\n")
    return result
