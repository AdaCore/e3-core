import os

import e3.anod.driver
import e3.anod.sandbox
import e3.anod.spec

import pytest


def test_simple_driver():
    sandbox = e3.anod.sandbox.SandBox()

    class Simple(e3.anod.spec.Anod):
        @e3.anod.spec.Anod.primitive()
        def download():
            pass

    with pytest.raises(e3.anod.spec.AnodError):
        anod_instance = Simple(qualifier="", kind="build")
        anod_instance.sandbox = None
        e3.anod.driver.AnodDriver(anod_instance=anod_instance, store=None).activate(
            sandbox, None
        )

    sandbox.root_dir = os.getcwd()
    anod_instance = Simple(qualifier="", kind="build")
    anod_instance.sandbox = sandbox
    driver = e3.anod.driver.AnodDriver(anod_instance=anod_instance, store=None)

    assert driver.call("why") is False
    with pytest.raises(e3.anod.spec.AnodError) as err:
        driver.download()

    assert ".activate() has not been called" in str(err)


def test_deps_driver():
    class Deps(e3.anod.spec.Anod):
        build_deps = [e3.anod.spec.Anod.Dependency(name="parent")]

        @e3.anod.spec.Anod.primitive()
        def build(self):
            return self.deps["parent"].parent_info

    sandbox = e3.anod.sandbox.SandBox()
    sandbox.root_dir = os.getcwd()
    anod_instance = Deps(qualifier="", kind="build")
    anod_instance.sandbox = sandbox

    spec_dir = os.path.join(os.path.dirname(__file__), "data")
    spec_repo = e3.anod.loader.AnodSpecRepository(spec_dir)

    e3.anod.driver.AnodDriver(anod_instance=anod_instance, store=None).activate(
        sandbox, spec_repo
    )

    anod_instance.build_space.create()
    assert anod_instance.build() == "from_parent"
