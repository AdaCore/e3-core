"""Return the current timezone offset."""

from __future__ import annotations

import sys
from datetime import datetime

from dateutil.tz import gettz


def timezone() -> float:
    """Return current timezone offset in hours.

    :return: offset from utc in hours
    """
    if sys.platform == "win32":  # unix: no cover
        from ctypes import windll, Structure, pointer
        from ctypes.wintypes import DWORD, WCHAR, LONG

        class TIME_ZONE_INFORMATION(Structure):
            _fields_ = [
                ("Bias", LONG),
                ("StandardName", WCHAR * 32),
                ("StandardDate", DWORD * 8),
                ("StandardBias", LONG),
                ("DaylightName", WCHAR * 32),
                ("DaylightDate", DWORD * 8),
                ("DaylightBias", LONG),
            ]

        win_tz = TIME_ZONE_INFORMATION()
        win_tz_pt = pointer(win_tz)
        windll.kernel32.GetTimeZoneInformation(win_tz_pt)
        result = win_tz.Bias
        result = -int(result) // 60
    else:
        # Note that in case timezone cannot be computed then
        # utcoffset can return None.
        offset = datetime.now(gettz()).utcoffset()
        if offset is None:
            result = 0.0  # defensive code
        else:
            result = offset.total_seconds() // 3600

    return float(result)
