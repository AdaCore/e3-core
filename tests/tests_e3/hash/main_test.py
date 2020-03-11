import e3.hash

import pytest


def test_hash():
    with open("to-hash.txt", "wb") as f:
        f.write(b"content\n")
    assert e3.hash.md5(f.name) == "f75b8179e4bbe7e2b4a074dcef62de95"
    assert e3.hash.sha1(f.name) == "7fe70820e08a1aac0ef224d9c66ab66831cc4ab1"
    assert (
        e3.hash.sha256(f.name)
        == "434728a410a78f56fc1b5899c3593436e61ab0c731e9072d95e96db290205e53"
    )
    with pytest.raises(e3.hash.HashError):
        e3.hash.md5("doesnotexist")
