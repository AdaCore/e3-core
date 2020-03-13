import e3.env
import e3.platform

import pytest


def test_platform():

    a = e3.platform.Platform.get()
    b = e3.platform.Platform.get()

    assert b == a

    assert hash(b) == hash(a)

    c = e3.platform.Platform.get(platform_name="arm-linux")

    assert b != c

    assert c.os.name == "linux"


def test_is_host():
    p = e3.platform.Platform.get(machine=e3.env.Env().build.machine)
    assert p.is_host


def test_immutable():

    a = e3.platform.Platform.get()

    with pytest.raises(AttributeError):
        a.domain = "example.net"

    b = a._replace(domain="example.net")
    assert b != a
