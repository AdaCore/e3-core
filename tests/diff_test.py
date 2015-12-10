import e3.diff


def test_non_existing():
    """Check that a non existing file will be considered as null string"""
    assert e3.diff.diff('foo1', 'foo2') == ''
