import os

from e3.anod.driver import AnodDriver
from e3.anod.helper import Configure, Make, text_replace
from e3.anod.sandbox import SandBox
from e3.anod.spec import Anod
from e3.env import BaseEnv


def test_make():
    class AnodMake(Anod):
        def shell(self, *cmd, **kwargs):
            """Mock for Anod.shell that does not spawn processes."""
            return (cmd, kwargs)

        @Anod.primitive()
        def build(self):
            m1 = Make(self, makefile="/tmp/makefile")
            m1.set_var("prefix", "/foo")
            m2 = Make(self, jobs=2)
            m2.set_default_target("install")
            m2.set_var("profiles", ["dev", "prod"])
            return (
                m1.cmdline()["cmd"],
                m1()[0],
                m1(exec_dir="/foo", timeout=2)[1],
                m2.cmdline()["cmd"],
                m2.cmdline(["clean", "install"])["cmd"],
                m2.cmdline("all")["cmd"],
            )

    Anod.sandbox = SandBox(root_dir=os.getcwd())
    Anod.sandbox.create_dirs()

    am = AnodMake(qualifier="", kind="build", jobs=10)
    AnodDriver(anod_instance=am, store=None).activate(Anod.sandbox, None)
    am.build_space.create()
    assert am.build() == (
        ["make", "-f", "/tmp/makefile", "-j", "10", "prefix=/foo"],
        ("make", "-f", "/tmp/makefile", "-j", "10", "prefix=/foo"),
        {"cwd": "/foo", "timeout": 2},
        ["make", "-j", "2", "profiles=dev prod", "install"],
        ["make", "-j", "2", "profiles=dev prod", "clean", "install"],
        ["make", "-j", "2", "profiles=dev prod", "all"],
    )


def test_configure():
    class AnodConf(Anod):
        @Anod.primitive()
        def build(self):
            c = Configure(self)
            return c.cmdline()

    Anod.sandbox = SandBox(root_dir=os.getcwd())
    Anod.sandbox.create_dirs()

    ac = AnodConf(qualifier="", kind="build", jobs=10)
    AnodDriver(anod_instance=ac, store=None).activate(Anod.sandbox, None)
    ac.build_space.create()

    # Configure() can add $CONFIG_SHELL in the command line
    # Check that the two other arguments are as expected
    assert ac.build()["cmd"][-2:] == [
        "../src/configure",
        "--build=%s" % ac.env.build.triplet,
    ]

    # Check with canadian env

    canadian_env = BaseEnv()
    canadian_env.set_build("x86-windows")
    canadian_env.set_host("x86-linux")
    canadian_env.set_target("arm-elf")
    assert canadian_env.is_canadian

    ac2 = AnodConf(qualifier="", kind="build", jobs=10, env=canadian_env)
    AnodDriver(anod_instance=ac2, store=None).activate(Anod.sandbox, None)
    ac2.build_space.create()

    ac2_cmd = ac2.build()["cmd"]
    assert "--build=i686-pc-mingw32" in ac2_cmd
    assert "--host=i686-pc-linux-gnu" in ac2_cmd
    assert "--target=arm-eabi" in ac2_cmd

    # Check with cross env

    cross_env = BaseEnv()
    cross_env.set_target("arm-elf")

    ac3 = AnodConf(qualifier="", kind="build", jobs=10, env=cross_env)
    AnodDriver(anod_instance=ac3, store=None).activate(Anod.sandbox, None)
    ac3.build_space.create()

    assert "--target=arm-eabi" in ac3.build()["cmd"]


def test_configure_opts():
    """Check configure options."""

    class AnodConf(Anod):
        def shell(self, *cmd, **kwargs):
            """Mock for Anod.shell that does not spawn processes."""
            return (cmd, kwargs)

        @Anod.primitive()
        def build(self):
            c = Configure(self)
            c.add("--with-opt")
            c.add_env("OPT", "VAL")
            return [c.cmdline(), c()]

    os.environ["CONFIG_SHELL"] = "ksh"

    Anod.sandbox = SandBox(root_dir=os.getcwd())
    Anod.sandbox.create_dirs()

    ac = AnodConf(qualifier="", kind="build", jobs=10)
    AnodDriver(anod_instance=ac, store=None).activate(Anod.sandbox, None)
    ac.build_space.create()

    result = ac.build()

    assert result[0]["cmd"][:-1] == ["ksh", "../src/configure", "--with-opt"]
    assert result[0]["options"]["env"] == {"OPT": "VAL"}

    assert result[1][0][:-1] == tuple(result[0]["cmd"][:-1])
    assert result[1][1]["env"] == result[0]["options"]["env"]


def test_text_replace():
    with open("myfile", "w") as f:
        f.write("what who when")
    text_replace("myfile", [(b"who", b"replaced")])
    with open("myfile") as f:
        assert f.read() == "what replaced when"
