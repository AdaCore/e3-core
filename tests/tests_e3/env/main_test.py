import os
import sys

import e3.env
import e3.fs
import e3.os.process
import e3.platform

import pytest


def test_autodetect():
    sys_platform = (
        sys.platform.replace("linux2", "linux")
        .replace("win32", "windows")
        .replace("aix7", "aix")
        .replace("sunos5", "solaris")
    )
    assert sys_platform in str(e3.platform.Platform.get())

    assert sys_platform in e3.env.Env().build.platform

    b = e3.env.BaseEnv()
    b.set_build("x86-linux", "rhES7")
    assert b.build.platform == "x86-linux"
    assert sys_platform in e3.env.Env().build.platform

    assert "--build=x86-linux,rhES7" in b.cmd_triplet()

    b.set_host("x86_64-linux", "rhES7")
    assert "--build=x86-linux,rhES7" in b.cmd_triplet()
    assert "--host=x86_64-linux,rhES7" in b.cmd_triplet()
    assert b.get_attr("build.os.version") == "rhES7"


def test_platform():
    e = e3.env.BaseEnv()
    e.set_host("x86-linux")
    assert e.platform == "x86-linux"
    e.set_target("x86-solaris")
    assert e.platform == "x86-solaris-linux"


def test_is_canadian():
    e = e3.env.BaseEnv()
    e.set_build("sparc-solaris")
    assert not e.is_canadian
    e.set_host("sparc64-solaris")
    assert not e.is_canadian
    e.set_host("x86-windows")
    assert e.is_canadian


def test_set_host():
    e = e3.env.BaseEnv()
    e.set_build("x86-linux")

    # check that set_host reset target to host
    e.set_target("x86-windows")
    e.set_host("x86_64-linux")
    assert e.target == e.host

    # check special value 'build'
    e.set_host("build")
    assert e.build == e.host
    assert e.target == e.build

    # check no value passed (should be the same as host='build')
    e.set_host("x86_64-linux")
    e.set_host()
    assert e.host == e.build
    assert e.target == e.build

    # check special value 'target'
    e.set_target("x86-windows")
    e.set_host("target")
    assert e.host == e.target


def test_set_target():
    e = e3.env.BaseEnv()
    e.set_build("x86-linux")
    e.set_host("x86_64-linux")

    # check 'build' special value
    e.set_target("build")
    assert e.is_cross
    assert e.is_canadian

    e.set_target("host")
    assert e.host == e.target

    e.set_target()
    assert e.host == e.target


def test_set_env():
    e = e3.env.BaseEnv()
    e.set_env("x86-linux,rhEs5", "x86_64-linux,debian7", "x86-windows,2008")
    assert e.build.platform == "x86-linux"
    assert e.host.platform == "x86_64-linux"
    assert e.target.platform == "x86-windows"

    # keep the current target
    e.set_env("x86-linux,rhEs5", "x86_64-linux,debian7", "target")
    assert e.target.platform == "x86-windows"

    # None means host, replace the target by the previous host value
    e.set_env("x86-linux,rhEs5", "x86_64-linux,debian7", None)
    assert e.target.platform == "x86_64-linux"

    # replace the target by the previous build value
    e.set_env("x86-linux,rhEs5", "x86_64-linux,debian7", "build")
    assert e.target.platform == "x86-linux"

    # replace the target by the previous build host
    e.set_env("x86-linux,rhEs5", "x86_64-linux,debian7", "host")
    assert e.target.platform == "x86_64-linux"


def test_cmd_triplet():
    if e3.env.Env().build.platform == "x86-linux":
        build_platform = "x86_64-linux,rhES5"
    else:
        build_platform = "x86-linux,rhES5"
    e = e3.env.BaseEnv()
    e.set_env(build_platform, "x86_64-linux,debian7", "x86-windows,2008")
    cmd_options = e.cmd_triplet()
    assert len(cmd_options) == 3
    assert cmd_options[0] == "--build=%s" % build_platform
    assert cmd_options[1] == "--host=x86_64-linux,debian7"
    assert cmd_options[2].startswith("--target=x86-windows,2008")


def test_get_attr():
    e = e3.env.BaseEnv()
    e.set_env("x86-linux,rhES5", "x86_64-linux,debian7", "x86-windows,2008")
    assert e.get_attr("host.os.name") == "linux"
    assert e.get_attr("host.os.name2", default_value="hello") == "hello"
    assert e.get_attr("host.cpu.bits", forced_value="gotit") == "gotit"

    e.my_attr = 3
    assert e.get_attr("my_attr") == 3

    e.my_attr = None
    assert e.get_attr("my_attr", default_value=4) == 4

    assert e.my_attr is None

    with pytest.raises(AttributeError):
        print(e.does_not_exist)


def test_add_path():
    e = e3.env.Env()
    saved_path = os.environ["PATH"]
    e.store()
    e.add_path("/dummy_for_test")
    assert os.environ["PATH"].startswith("/dummy_for_test")
    e.add_path("/dummy_for_test", append=True)
    assert os.environ["PATH"].endswith("/dummy_for_test")
    e.restore()
    assert saved_path == os.environ["PATH"]


def test_add_dll_path():
    e = e3.env.Env()
    saved_path = os.environ.get(e.dll_path_var)
    e.store()
    e.add_dll_path("/dummy_for_test")
    assert os.environ[e.dll_path_var].startswith("/dummy_for_test")
    e.add_dll_path("/dummy_for_test", append=True)
    assert os.environ[e.dll_path_var].endswith("/dummy_for_test")
    e.restore()
    assert saved_path == os.environ.get(e.dll_path_var)


def test_discriminants():
    e = e3.env.Env()
    e.store()
    assert "native" in e.discriminants
    e.set_target("arm-elf")
    assert "native" not in e.discriminants

    e.set_build("x86-windows")
    assert "NT" in e.discriminants
    e.restore()


def test_tmp():
    e = e3.env.Env()
    current_dir = os.getcwd()
    os.environ["TMPDIR"] = current_dir
    assert e.tmp_dir == current_dir


def test_to_dict():
    assert e3.env.Env().to_dict()["is_cross"] is False


def test_store():
    c = e3.env.Env()

    c.abc = "foo"

    c.store()

    c.abc = "bar"

    c.restore()

    assert c.abc == "foo"

    c.store()
    c.abc = "one"
    c.store("store")
    c.abc = "two"
    c.restore("store")
    assert c.abc == "one"
    c.restore()
    assert c.abc == "foo"

    # calling .restore() when there is nothing to restore is a no-op
    # this test is run through env_protect (defined in conftest.py)
    # so Env().store() has already been called, call it twice here
    c.restore()
    c.restore()

    assert not hasattr(c, "abc")


def test_from_platform_name():
    e = e3.env.BaseEnv.from_platform_name("arm-linux-linux")
    assert e.target.platform == "arm-linux"
    assert e.build.platform == "x86-linux"
    e = e3.env.BaseEnv.from_platform_name("arm-linux-linux64")
    assert e.target.platform == "arm-linux"
    assert e.build.platform == "x86_64-linux"
    e = e3.env.BaseEnv.from_platform_name("x86_64-linux-darwin")
    assert e.target.platform == "x86_64-linux"
    assert e.build.platform == "x86_64-darwin"
    assert e.is_cross
    e = e3.env.BaseEnv.from_platform_name("x86_64-linux")
    assert e.target.platform == "x86_64-linux"
    assert e.build.platform == "x86_64-linux"
    assert not e.is_cross
    e = e3.env.BaseEnv.from_platform_name("avr-elf-solaris")
    assert e.target.platform == "avr-elf"
    assert e.build.platform == "sparc-solaris"
    assert e.is_cross

    e = e3.env.BaseEnv.from_platform_name("what-linux-linux")
    assert e is None


def test_copy():
    e = e3.env.BaseEnv()
    new_e = e.copy(target="arm-elf")

    assert new_e.target.platform == "arm-elf"


def test_build_os_propagation():
    """Ensure that OS version is preserved when build platform is changed."""
    winenv = e3.env.BaseEnv(
        build=e3.platform.Platform.get(
            platform_name="x86-windows", version="2012", machine="mywindows"
        )
    )

    winenv.set_env(build="x86_64-windows")

    assert winenv.build.os.version == "2012"
