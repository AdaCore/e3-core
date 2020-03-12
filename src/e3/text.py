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
    key_regexp = r"|".join([r"\(%s\)" % k for k in values])
    result = re.sub(r"%%(?!%s)" % key_regexp, r"%%", pattern)
    return result % values


def bytes_as_str(content):
    """Safely convert bytes to a python string.

    This function attempts the conversion assuming a utf-8 enconding.
    If this triggers a conversion error, it then falls back to a safe
    representation, where some characters might be escaped.

    :param content: content to be transformed
    :type content: bytes
    :return: a string
    :rtype: str
    """
    try:
        result = content.decode("utf-8")
    except UnicodeDecodeError:
        # The default representation for bytes in python returns
        # b'content' and escape various characters. To make the
        # representation more human readable, strip the quotes
        # and unescape LF character.
        if isinstance(content, str):
            # Python 2.x case
            result = "".join(
                [
                    c if 32 <= ord(c) <= 126 or ord(c) == 10 else "\\x%02x" % ord(c)
                    for c in content
                ]
            )
        else:
            # Python 3.x case
            result = str(content)[2:-1].replace("\\n", "\n")
    return result
