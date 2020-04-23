from __future__ import annotations

import calendar
from datetime import datetime
import time
from typing import TYPE_CHECKING, overload

if TYPE_CHECKING:
    from typing import Optional


@overload
def timestamp_as_string(value: None) -> None:
    ...


@overload
def timestamp_as_string(value: float) -> str:
    ...


def timestamp_as_string(value: Optional[float]) -> Optional[str]:
    """Convert a timestamp into a human readable date/time.

    :param value: a timestamp or None
    :return: the string representing the timestamp or None if value is None
    """
    if value is None:
        return None
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(value))


def utc_timestamp() -> int:
    """Return the number of seconds since epoch UTC."""
    d = datetime.utcnow()
    return calendar.timegm(d.utctimetuple())
