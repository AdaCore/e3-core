from __future__ import annotations
import os
import sys
import zipfile
import tempfile
from pkg_resources import Requirement
from e3.os.process import Run
from e3.fs import ls, mv
from e3.error import E3Error
from e3.sys import python_script


class WheelError(E3Error):
    pass


class Wheel:
    """Handle Python wheel packages."""

    def __init__(self, path: str) -> None:
        """Initialize a wheel object.

        :param path: path to the wheel object
        """
        self.path = os.path.abspath(path)

    @property
    def metadata_path(self) -> str:
        """Relative path in a wheel package to the metadata."""
        return (
            "-".join(os.path.basename(self.path).split("-")[0:2])
            + ".dist-info/METADATA"
        )

    @property
    def requirements(self) -> set[Requirement]:
        """Return the set of Requirements for the wheel."""
        with zipfile.ZipFile(self.path) as zipfd:
            with zipfd.open(self.metadata_path) as fd:
                return {
                    Requirement.parse(line.split(":", 1)[1].strip().replace('"', "'"))
                    for line in fd.read().decode("utf-8").splitlines()
                    if line.startswith("Requires-Dist:")
                }

    @classmethod
    def build(cls, source_dir: str, dest_dir: str, python_tag: str = "py3") -> Wheel:
        """Create a wheel package from a source directory.

        :param source_dir: location of the sources
        :param dest_dir: directory in which the wheel will be saved
        :param python_tag: python tag (default: py3)
        :return: a Wheel object
        """
        with tempfile.TemporaryDirectory() as build_dir:
            p = Run(
                [
                    sys.executable,
                    "./setup.py",
                    "-q",
                    "bdist_wheel",
                    f"--python-tag={python_tag}",
                    "-d",
                    build_dir,
                ],
                cwd=source_dir,
            )
            if p.status != 0:
                raise WheelError(f"Error during wheel creation:\n{p.out}")

            tmp_whl_path = ls(os.path.join(build_dir, "*.whl"))[0]
            dest_whl_path = os.path.join(dest_dir, os.path.basename(tmp_whl_path))
            mv(tmp_whl_path, dest_whl_path)
        return Wheel(path=dest_whl_path)

    def install(self) -> None:
        """Install a wheel."""
        p = Run(
            python_script("pip") + ["install", "-U", "--force-reinstall", self.path]
        )
        if p.status != 0:
            raise WheelError(f"Error during installation of {self.path}:\n{p.out}")
