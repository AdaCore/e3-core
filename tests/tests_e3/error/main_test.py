"""Tests for e3.error."""

from e3.error import E3Error


def test_e3error() -> None:
    """Test e3error."""
    err = None

    try:
        raise E3Error(None)  # noqa: TRY301
    except E3Error as basicerr:
        assert str(basicerr) == "E3Error"

    try:
        raise E3Error(None, origin="here")  # noqa: TRY301
    except E3Error as err0:
        err = err0
        assert str(err).strip() == "here: E3Error"

    try:
        msg = "one"
        raise E3Error(msg, origin="here")  # noqa: TRY301
    except E3Error as err1:
        err += err1

    try:
        raise E3Error(["two"])  # noqa: TRY301
    except E3Error as err2:
        err += err2
    assert str(err).strip() == "here: two"

    assert err.messages == ["one", "two"]

    err += "three"
    assert err.messages == ["one", "two", "three"]
