import e3.anod.deps

import pytest


def test_buildvar():
    with pytest.raises(AssertionError):
        e3.anod.deps.BuildVar("foo", [1, 2])

    b = e3.anod.deps.BuildVar("foo", "bar")
    assert b.kind == "var"
    assert str(b) == "foo=bar"


def test_dependency():
    d = e3.anod.deps.Dependency("dep", product_verison="20.0855369232", build="default")

    parent_env = e3.env.BaseEnv(build=e3.platform.Platform.get("arm-ios"))

    class MockAnod:
        pass

    parent_anod_instance = MockAnod()
    parent_anod_instance.env = parent_env

    defaultenv = e3.env.BaseEnv(build=e3.platform.Platform.get("arm-linux"))

    assert (
        d.env(parent_anod_instance, default_env=defaultenv).build.platform
        == defaultenv.build.platform
    )
    assert (
        d.env(parent_anod_instance, default_env=defaultenv).host.platform
        == defaultenv.build.platform
    )
    assert (
        d.env(parent_anod_instance, default_env=defaultenv).target.platform
        == defaultenv.build.platform
    )


def test_dependency2():
    d = e3.anod.deps.Dependency("dep", product_verison="20.0855369232", host="default")

    parent_env = e3.env.BaseEnv(build=e3.platform.Platform.get("arm-ios"))

    class MockAnod:
        pass

    parent_anod_instance = MockAnod()
    parent_anod_instance.env = parent_env

    defaultenv = e3.env.BaseEnv(build=e3.platform.Platform.get("arm-linux"))

    assert (
        d.env(parent_anod_instance, default_env=defaultenv).host.platform
        == defaultenv.build.platform
    )
    assert (
        d.env(parent_anod_instance, default_env=defaultenv).target.platform
        == defaultenv.build.platform
    )


def test_dependency3():
    d = e3.anod.deps.Dependency(
        "dep", product_verison="20.0855369232", target="default"
    )

    parent_env = e3.env.BaseEnv(build=e3.platform.Platform.get("arm-ios"))

    class MockAnod:
        pass

    parent_anod_instance = MockAnod()
    parent_anod_instance.env = parent_env

    defaultenv = e3.env.BaseEnv(build=e3.platform.Platform.get("arm-linux"))

    assert (
        d.env(parent_anod_instance, default_env=defaultenv).target.platform
        == defaultenv.build.platform
    )
