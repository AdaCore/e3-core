from __future__ import absolute_import, division, print_function

import e3.os.timezone


def test_tz():
    tz = e3.os.timezone.timezone()
    assert isinstance(tz, float)
    assert -14 <= tz <= 12
