import time


def timestamp_as_string(value):
    """Convert a timestamp into a human readable date/time.

    :param value: a timestamp or None
    :type value: float | None
    :return: the string representing the timestamp or None if value is None
    """
    if value is None:
        return None
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(value))
