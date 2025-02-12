from __future__ import annotations
from e3.python.wheel import Wheel
from e3.os.process import Run
from e3.sys import python_script
from e3.fs import mkdir
from e3.python.pypi import PyPIClosure, PyPIError

import yaml
from os import listdir
from os.path import join as path_join, isfile, basename
import pytest


def generate_py_pkg_source(
    name: str, requires: list[str] | None = None, version="1.0.0"
):
    mkdir(name)
    if requires:
        requires_str = ",".join([f'"{el}"' for el in requires])
    with open(path_join(name, "setup.py"), "w") as fd:
        fd.write("from setuptools import setup, find_packages\n")
        fd.write(f"setup(name='{name}',\n")
        fd.write(f"      version='{version}',\n")
        if requires:
            fd.write(f"    install_requires=[{requires_str}],\n")
        fd.write("       packages=find_packages())\n")
    mkdir(path_join(name, name))
    with open(path_join(name, name, "__init__.py"), "w") as fd:
        fd.write(f"# This is package {name}")
    return Wheel.build(
        source_dir=name, dest_dir=".", build_args=["--no-build-isolation", "--no-index"]
    )


def test_wheel():
    wheel1 = generate_py_pkg_source("src1")
    assert isfile(wheel1.path)
    assert not wheel1.requirements

    wheel2 = generate_py_pkg_source("src2", requires=["src1<=2.0.0"])
    assert isfile(wheel2.path)
    assert len(wheel2.requirements) == 1

    mkdir(".cache")

    with PyPIClosure(
        python3_version="3.10",
        platforms=[
            "x86_64-linux",
            "aarch64-linux",
            "x86_64-windows",
            "aarch64-darwin",
            "x86_64-darwin",
        ],
        cache_dir=".cache",
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
        assert len(pypi.requirements_closure()) == 2

    with PyPIClosure(
        python3_version="3.10",
        platforms=[
            "x86_64-linux",
            "aarch64-linux",
            "x86_64-windows",
            "aarch64-darwin",
            "x86_64-darwin",
        ],
        cache_dir=".cache",
    ) as pypi:
        pypi.add_requirement("src2==1.0.0")
        pypi.add_requirement("src1")
        assert len(pypi.file_closure()) == 2
        assert len(pypi.requirements_closure()) == 2


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
        + [
            "--python3-version=10",
            "--local-clones=.",
            "config.yml",
            "dist",
            "--wheel-build-arg=--no-build-isolation",
            "--wheel-build-arg=--no-index",
        ]
    )
    assert p.status == 0, p.out
    file_list = set(listdir("dist"))
    assert file_list == {
        "requirements.txt",
        "src1-1.0.0-py3-none-any.whl",
        "src2-1.0.0-py3-none-any.whl",
    }


def test_star_requirements():
    """Test package requirements ending with * with != operator."""
    wheel1 = generate_py_pkg_source("src1", version="1.0.4")
    assert isfile(wheel1.path)
    assert not wheel1.requirements

    wheel2 = generate_py_pkg_source("src2", requires=["src1!=1.0.*"])
    assert isfile(wheel2.path)
    assert len(wheel2.requirements) == 1

    wheel3 = generate_py_pkg_source("src1", version="1.1.4")
    assert isfile(wheel3.path)
    assert not wheel3.requirements

    mkdir(".cache")

    with PyPIClosure(
        python3_version="3.10",
        platforms=[
            "x86_64-linux",
        ],
        cache_dir=".cache",
    ) as pypi:
        pypi.add_wheel(wheel1.path)
        pypi.add_wheel(wheel2.path)
        pypi.add_requirement("src2==1.0.0")
        with pytest.raises(PyPIError, match="Impossible resolution"):
            pypi.requirements_closure()

    with PyPIClosure(
        python3_version="3.10",
        platforms=[
            "x86_64-linux",
        ],
        cache_dir=".cache",
    ) as pypi:
        pypi.add_wheel(wheel2.path)
        pypi.add_wheel(wheel3.path)
        pypi.add_requirement("src2==1.0.0")
        assert len(pypi.requirements_closure()) == 2


@pytest.mark.parametrize(
    "arguments,expected",
    [
        ((None, None), "setuptools_scm-7.1.0-py3-none-any.whl"),
        ((["setuptools-scm"], None), "setuptools_scm-8.0.0-py3-none-any.whl"),
        ((["setuptools_scm"], None), "setuptools_scm-8.0.0-py3-none-any.whl"),
        ((None, "setuptools_scm==8"), None),
    ],
)
def test_yanked(pypi_server, arguments, expected):
    allowed_yanked, invalid_wheel = arguments
    expected_wheel = expected

    mkdir("cache")

    with pypi_server:
        with PyPIClosure(
            python3_version="3.11",
            platforms=[
                "x86_64-linux",
            ],
            cache_dir="cache",
            allowed_yanked=allowed_yanked,
        ) as pypi:
            if invalid_wheel:
                pypi.add_requirement(invalid_wheel)

                with pytest.raises(
                    PyPIError,
                    match=("Impossible resolution"),
                ):
                    pypi.requirements_closure()
            else:
                pypi.add_requirement("setuptools_scm >= 6.2, <= 8")
                all_filenames = [basename(f) for f in pypi.file_closure()]
                assert expected_wheel in all_filenames
