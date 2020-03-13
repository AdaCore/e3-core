import sys

import e3.os.process

import pytest

if sys.platform == "win32":
    import e3.os.windows.native_api


@pytest.mark.skipif(sys.platform != "win32", reason="windows specific test")
def test_unicode_string_preallocation():
    s = e3.os.windows.native_api.UnicodeString(max_length=10)
    assert len(s) == 0, "preallocated unicode string has still a 0 length"
