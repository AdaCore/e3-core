from __future__ import annotations
import os
import zipfile
import tempfile
from packaging.requirements import Requirement
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
                    Requirement(line.split(":", 1)[1].strip().replace('"', "'"))
                    for line in fd.read().decode("utf-8").splitlines()
                    if line.startswith("Requires-Dist:")
                }

    @classmethod
    def build(
        cls,
        source_dir: str,
        dest_dir: str,
        python_tag: str = "py3",
        build_args: list[str] | None = None,
    ) -> Wheel:
        """Create a wheel package from a source directory.

        :param source_dir: location of the sources
        :param dest_dir: directory in which the wheel will be saved
        :param python_tag: python tag (default: py3)
        :param build_args: extra `pip wheel` build arguments
        :return: a Wheel object
        """
        with tempfile.TemporaryDirectory() as build_dir:
            cmd = python_script("pip") + [
                "wheel",
                ".",
                "-q",
                "--no-deps",
                f"-C--python-tag={python_tag}",
                "-w",
                build_dir,
            ]

            if build_args is not None:
                cmd += build_args
            p = Run(cmd, cwd=source_dir)
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
