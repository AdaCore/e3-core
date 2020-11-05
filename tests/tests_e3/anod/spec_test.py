import os
import subprocess
import sys

from e3.anod.driver import AnodDriver
from e3.anod.error import AnodError, SpecError
from e3.anod.sandbox import SandBox
from e3.anod.spec import Anod, __version__, check_api_version, has_primitive

import pytest


def test_simple_spec():
    class Simple(Anod):

        test_qualifier_format = (("with_bar", False),)

        build_source_list = [
            Anod.Source("foo-src", publish=False),
            Anod.Source("bar-src", publish=True),
        ]

        @property
        def test_source_list(self):
            result = [Anod.Source("foo-test-src", publish=False)]
            if self.parsed_qualifier.get("with_bar"):
                result.append(Anod.Source("bar-test-src", publish=False))
            return result

    simple_build = Simple("", kind="build")
    assert len(simple_build.build_source_list) == 2

    simple_test = Simple("", kind="test")
    assert len(simple_test.test_source_list) == 1

    simple_test_with_bar = Simple("with_bar=true", kind="test")
    assert len(simple_test_with_bar.test_source_list) == 2


def test_spec_buildvars():
    """Build vars are used by the driver and not visible in deps."""

    class MySpec(Anod):

        build_deps = [Anod.BuildVar("key", "value")]

        @Anod.primitive()
        def build(self):
            pass

    ms = MySpec("", kind="build")
    assert len(ms.deps) == 0


def test_spec_wrong_dep():
    """Check exception message when wrong dependency is set."""
    with pytest.raises(SpecError) as err:
        Anod.Dependency("foo", require="invalid")

    assert (
        "require should be build_tree, installation or source_pkg not "
        "invalid" in str(err)
    )


def test_primitive():
    class NoPrimitive(Anod):
        def build(self):
            return 2

    no_primitive = NoPrimitive("", "build")
    assert has_primitive(no_primitive, "build") is False

    class WithPrimitive(Anod):

        build_qualifier_format = (("error", False),)

        package = Anod.Package(prefix="mypackage", version=lambda: "42")

        @Anod.primitive()
        def build(self):
            if "error" in self.parsed_qualifier:
                raise ValueError(self.parsed_qualifier["error"])
            elif "error2" in self.parsed_qualifier:
                self.shell(sys.executable, "-c", "import sys; sys.exit(2)")
            else:
                hello = self.shell(
                    sys.executable, "-c", 'print("world")', output=subprocess.PIPE
                )
                return hello.out.strip()

    with_primitive = WithPrimitive("", "build")
    with_primitive2 = WithPrimitive("error=foobar", "build")
    with_primitive3 = WithPrimitive("error2", "build")
    with_primitive4 = WithPrimitive("error3", "build")

    Anod.sandbox = SandBox(root_dir=os.getcwd())
    Anod.sandbox.spec_dir = os.path.join(os.path.dirname(__file__), "data")
    Anod.sandbox.create_dirs()
    # Activate the logging
    AnodDriver(anod_instance=with_primitive, store=None).activate(Anod.sandbox, None)
    AnodDriver(anod_instance=with_primitive2, store=None).activate(Anod.sandbox, None)
    AnodDriver(anod_instance=with_primitive3, store=None).activate(Anod.sandbox, None)
    AnodDriver(anod_instance=with_primitive4, store=None)  # don't activate

    with_primitive.build_space.create()

    assert has_primitive(with_primitive, "build") is True
    assert with_primitive.build() == "world"

    with_primitive2.build_space.create()

    with pytest.raises(AnodError):
        with_primitive2.build()

    assert with_primitive2.package.name.startswith("mypackage")

    # Check __getitem__
    # PKG_DIR returns the path to the pkg directory
    assert with_primitive2["PKG_DIR"].endswith("pkg")

    with_primitive3.build_space.create()
    with pytest.raises(AnodError):
        with_primitive3.build()


def test_api_version():
    # __version__ is supported
    check_api_version(__version__)

    with pytest.raises(AnodError):
        check_api_version("0.0")
