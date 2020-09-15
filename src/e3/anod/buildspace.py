from __future__ import annotations

import os
from typing import TYPE_CHECKING

import e3.error
import e3.log
import e3.os.process
from e3.fs import mkdir, rm
from e3.os.fs import touch

logger = e3.log.getLogger("buildspace")


if TYPE_CHECKING:
    from typing import Optional, List


class BuildSpace:
    """Build space located inside a sandbox."""

    DIRS = (
        "binary",
        "build",
        "install",
        "log",
        "pkg",
        "results",
        "src",
        "test",
        "tmp",
        "src",
    )

    def __init__(self, root_dir: str):
        """Initialise a build space.

        :param root_dir: build space root dir
        """
        self.directory_mapping = {k: k for k in self.DIRS}
        self.root_dir = os.path.abspath(root_dir)
        self.initialized = False

    def exists(self) -> bool:
        """Return True if the build space exists on disk.

        This function just checks the contents of self.root_dir,
        and verifies that it appears to be a build space.
        It does so, irrespective of whether self.initialize
        is True or not.

        :return: True if self.root_dir is a buildspace, False otherwise.
        """
        # Start by verifying that the file used as build space markers
        # exists.
        if not os.path.isfile(os.path.join(self.root_dir, ".buildspace")):
            return False
        # Next, verify that all the necessary directories exist as well.
        for d in self.DIRS:
            if not os.path.isdir(self.subdir(name=d)):
                return False
        return True

    @property
    def dirs(self) -> List[str]:
        return list(self.directory_mapping.values())

    def subdir(self, name: str) -> str:
        if name not in self.DIRS:
            raise ValueError(f"invalid subdir {name}")
        return os.path.join(self.root_dir, self.directory_mapping[name])

    def __getattr__(self, name: str) -> str:
        if name.endswith("_dir") and name[:-4] in self.DIRS:
            return self.subdir(name[:-4])
        raise AttributeError(f"unknown build space attribute: {name}")

    def __getitem__(self, key: str) -> str:
        if key.isupper() and key.endswith("_DIR"):
            return getattr(self, key.lower(), None)
        raise KeyError(f"invalid build space key: {key}")

    def create(self, quiet: bool = False) -> None:
        """Create a build space.

        The function create all the necessary directories and files to have
        a valid build space. If the build space already exists, only tmp
        directory content is reset.

        :param quiet: do not print info messages
        """
        rm(self.tmp_dir, recursive=True)

        for d in self.DIRS:
            mkdir(self.subdir(name=d), quiet=quiet)

        # Add a marker that identify a build space
        touch(os.path.join(self.root_dir, ".buildspace"))

        self.initialized = True

    def reset(self, keep: Optional[List[str]] = None) -> None:
        """Reset build space.

        The function delete the complete buildspace. The only elements that
        are not deleted are the logs, the testsuite results and any
        subdirectories in keep parameter

        A call to self.create() is needed after calling this function.

        :param keep: a list of directory to keep in addition
            to results and log. Each element should be part of BuildSpace.DIRS
        """
        dirs_to_keep = set(keep) if keep is not None else set()
        dirs_to_keep.update(("results", "log"))

        dirs_to_reset = set(self.DIRS) - dirs_to_keep

        for d in dirs_to_reset:
            rm(self.subdir(name=d), recursive=True)
        self.initialized = False
