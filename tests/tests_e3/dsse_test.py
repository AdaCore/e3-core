from e3.os.process import Run
from e3.dsse import DSSE, DSSEError
import pytest


def test_dsse():
    # Generate a temporary x509 keypairs
    p = Run(
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:4096",
            "-keyout",
            "codesign1.key",
            "-out",
            "codesign1.crt",
            "-nodes",
            "-subj",
            "/CN=localhost",
        ]
    )
    assert p.status == 0, f"openssl failed:\n{p.out}"

    p = Run(
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:4096",
            "-keyout",
            "codesign2.key",
            "-out",
            "codesign2.crt",
            "-nodes",
            "-subj",
            "/CN=localhost",
        ]
    )
    assert p.status == 0, f"openssl failed:\n{p.out}"

    # Create an envelope for a string value
    d = DSSE(body='{"key": "value"}', payload_type="application/json")

    # Check that we can sign and verify
    assert not d.verify("./codesign1.crt")
    d.sign("mykey", "./codesign1.key")
    assert d.verify("./codesign1.crt")
    assert not d.verify("./codesign2.crt")

    # Create an envelope for a bytes value
    d = DSSE(body=b'{"key": "value"}', payload_type="application/json")

    # Check that we can have several signatures
    assert not d.verify("./codesign1.crt")
    assert not d.verify("./codesign2.crt")
    d.sign("mykey", "./codesign1.key")
    d.sign("mykey", "./codesign2.key")
    assert d.verify("./codesign1.crt")
    assert d.verify("./codesign2.crt")

    # Ensure that serializing and deserializing works
    dsse_envelope = d.as_json()
    d2 = DSSE.load_json(dsse_envelope)
    assert d2.verify("./codesign1.crt")
    assert d2.verify("./codesign2.crt")

    with pytest.raises(DSSEError) as err:
        d2.verify("./unknown.crt")
    assert "Cannot fetch public key" in str(err)
    with pytest.raises(DSSEError) as err:
        d2.sign("unknown", "./unknown.key")
    assert "SSL error" in str(err)
