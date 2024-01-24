from __future__ import annotations
from e3.python.wheel import Wheel
from e3.os.process import Run
from e3.sys import python_script
from e3.fs import mkdir
from e3.python.pypi import PyPIClosure, PyPIError

import yaml
import os
import pytest


def generate_py_pkg_source(
    name: str, requires: list[str] | None = None, version="1.0.0"
):
    mkdir(name)
    if requires:
        requires_str = ",".join([f'"{el}"' for el in requires])
    with open(os.path.join(name, "setup.py"), "w") as fd:
        fd.write("from setuptools import setup, find_packages\n")
        fd.write(f"setup(name='{name}',\n")
        fd.write(f"      version='{version}',\n")
        if requires:
            fd.write(f"    install_requires=[{requires_str}],\n")
        fd.write("       packages=find_packages())\n")
    mkdir(os.path.join(name, name))
    with open(os.path.join(name, name, "__init__.py"), "w") as fd:
        fd.write(f"# This is package {name}")
    return Wheel.build(source_dir=name, dest_dir=".")


def test_wheel():
    wheel1 = generate_py_pkg_source("src1")
    assert os.path.isfile(wheel1.path)
    assert not wheel1.requirements

    wheel2 = generate_py_pkg_source("src2", requires=["src1<=2.0.0"])
    assert os.path.isfile(wheel2.path)
    assert len(wheel2.requirements) == 1

    mkdir(".cache")

    with PyPIClosure(
        python3_version=10,
        platforms=[
            "x86_64-linux",
            "aarch64-linux",
            "x86_64-windows",
            "aarch64-darwin",
            "x86_64-darwin",
        ],
        cache_dir=".cache",
        cache_file=".pypi.cache",
    ) as pypi:
        pypi.add_wheel(wheel1.path)
        pypi.add_wheel(wheel2.path)
        pypi.add_requirement("src2==1.0.0")
        pypi.add_requirement("src1<2.0.0")
        pypi.add_requirement("src1>0.5.0")
        pypi.add_requirement("src1>=0.6.0")
        pypi.add_requirement("src1!=0.4.2")
        pypi.add_requirement("src1~=1.0.0")
        assert len(pypi.file_closure()) == 2
        assert len(pypi.closure_as_requirements()) == 2
        assert len(pypi.closure()) == 2

    with PyPIClosure(
        python3_version=10,
        platforms=[
            "x86_64-linux",
            "aarch64-linux",
            "x86_64-windows",
            "aarch64-darwin",
            "x86_64-darwin",
        ],
        cache_dir=".cache",
        cache_file=".pypi.cache",
    ) as pypi:
        pypi.add_requirement("src2==1.0.0")
        pypi.add_requirement("src1")
        assert len(pypi.file_closure()) == 2
        assert len(pypi.closure_as_requirements()) == 2
        assert len(pypi.closure()) == 2


def test_pypi_closure_tool():
    generate_py_pkg_source("src1")
    generate_py_pkg_source("src2", requires=["src1<=2.0.0"])
    with open("config.yml", "w") as fd:
        fd.write(
            yaml.safe_dump(
                {
                    "wheels": {"src1": "ssh://url/src1", "src2": "ssh://url/src2"},
                    "platforms": ["x86_64-linux"],
                }
            )
        )
    p = Run(
        python_script("e3-pypi-closure")
        + ["--python3-version=10", "--local-clones=.", "config.yml", "dist"]
    )
    assert p.status == 0, p.out
    file_list = set(os.listdir("dist"))
    assert file_list == {
        "requirements.txt",
        "src1-1.0.0-py3-none-any.whl",
        "src2-1.0.0-py3-none-any.whl",
    }


def test_star_requirements():
    """Test package requirements ending with * with != operator."""
    wheel1 = generate_py_pkg_source("src1", version="1.0.4")
    assert os.path.isfile(wheel1.path)
    assert not wheel1.requirements

    wheel2 = generate_py_pkg_source("src2", requires=["src1!=1.0.*"])
    assert os.path.isfile(wheel2.path)
    assert len(wheel2.requirements) == 1

    wheel3 = generate_py_pkg_source("src1", version="1.1.4")
    assert os.path.isfile(wheel3.path)
    assert not wheel3.requirements

    mkdir(".cache")

    with PyPIClosure(
        python3_version=10,
        platforms=[
            "x86_64-linux",
        ],
        cache_dir=".cache",
        cache_file=".pypi.cache",
    ) as pypi:
        pypi.add_wheel(wheel1.path)
        pypi.add_wheel(wheel2.path)
        with pytest.raises(PyPIError, match="Cannot satisfy constraint src1!=1.0.*"):
            pypi.add_requirement("src2==1.0.0")

    with PyPIClosure(
        python3_version=10,
        platforms=[
            "x86_64-linux",
        ],
        cache_dir=".cache",
        cache_file=".pypi.cache",
    ) as pypi:
        pypi.add_wheel(wheel2.path)
        pypi.add_wheel(wheel3.path)
        pypi.add_requirement("src2==1.0.0")
        assert len(pypi.closure()) == 2


def test_yanked(pypi_server):
    with pypi_server:
        print("OK")
    raise AssertionError("Expected")
