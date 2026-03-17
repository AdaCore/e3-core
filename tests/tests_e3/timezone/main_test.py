"""Tests for e3.timezone."""

import e3.os.timezone

# Timezone offset bounds (UTC-14 to UTC+12)
MIN_TIMEZONE_OFFSET = -14
MAX_TIMEZONE_OFFSET = 12


def test_tz() -> None:
    """Test tz."""
    tz = e3.os.timezone.timezone()
    assert isinstance(tz, float)
    assert MIN_TIMEZONE_OFFSET <= tz <= MAX_TIMEZONE_OFFSET
