from e3.error import E3Error


def test_e3error():
    err = None

    try:
        raise E3Error(None)
    except E3Error as basicerr:
        assert str(basicerr) == "E3Error"

    try:
        raise E3Error(None, origin="here")
    except E3Error as err0:
        err = err0
        assert str(err).strip() == "here: E3Error"

    try:
        raise E3Error("one", origin="here")
    except E3Error as err1:
        err += err1

    try:
        raise E3Error(["two"])
    except E3Error as err2:
        err += err2
    assert str(err).strip() == "here: two"

    assert err.messages == ["one", "two"]

    err += "three"
    assert err.messages == ["one", "two", "three"]
