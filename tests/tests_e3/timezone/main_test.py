import e3.os.timezone


def test_tz() -> None:
    tz = e3.os.timezone.timezone()
    assert isinstance(tz, float)
    assert -14 <= tz <= 12
