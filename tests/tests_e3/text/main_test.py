import e3.text


def test_bytes_as_str():
    """Test bytes_as_str function."""
    result = e3.text.bytes_as_str(b"\x00\xff")
    assert result == "\\x00\\xff"
    result = e3.text.bytes_as_str("echo\n".encode("utf-8"))
    assert result == "echo\n"
