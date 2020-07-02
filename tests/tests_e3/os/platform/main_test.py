import e3.os.platform


def test_system_info():
    """Compute SystemInfo and test the cache system."""
    s = e3.os.platform.SystemInfo
    s.reset_cache()
    platform_name = s.platform()
    os_version = s.os_version()
    assert s._platform == platform_name
    s._platform = "foo"
    assert s.platform() == "foo"
    s.reset_cache()
    assert s._platform is None
    assert s._os_version is None
    assert s.os_version() == os_version


def test_hostname():
    """Test SystemInfo.hostname."""
    s = e3.os.platform.SystemInfo
    try:
        s.reset_cache()
        hostname = s.hostname()
        s.reset_cache()
        assert s.hostname() == hostname
        real_uname = s.uname
        s.reset_cache()
        s.uname = e3.os.platform.Uname(
            system=real_uname.system,
            node="foo.example.net",
            release=real_uname.release,
            version=real_uname.version,
            machine=real_uname.machine,
            processor=real_uname.processor,
        )
        assert s.hostname() == ("foo", "example.net")
    finally:
        #  reset hostname() to the default value
        s.reset_cache()


def test_cpu():
    """Simple test for CPU."""
    cpu = e3.os.platform.CPU.get("x86_64")
    assert cpu.as_dict()["bits"] == 64


def test_os():
    """Simple test for OS."""
    os = e3.os.platform.OS.get("linux")
    assert os.as_dict()["dllext"] == ".so"

    e3.os.platform.KNOWLEDGE_BASE.os_info[
        "vxworks"
    ] = e3.os.platform.KNOWLEDGE_BASE.os_info["linux"]

    os = e3.os.platform.OS.get("vxworks", mode="rtp")
    assert os.as_dict()["exeext"] == ".vxe"
    os = e3.os.platform.OS.get("vxworks", version="6.8", mode="rtp")
    assert os.as_dict()["kernel_version"] == e3.os.platform.UNKNOWN
