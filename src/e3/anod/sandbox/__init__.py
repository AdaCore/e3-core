from __future__ import annotations

import os
import sys

import yaml
from pkg_resources import get_distribution
from typing import TYPE_CHECKING

import e3.log
import e3.os.process
from e3.anod.buildspace import BuildSpace
from e3.env import Env
from e3.fs import mkdir, rm
from e3.os.fs import chmod

logger = e3.log.getLogger("sandbox")


if TYPE_CHECKING:
    from typing import Any, Dict, Optional


class SandBox:
    def __init__(self, root_dir: str) -> None:
        self.root_dir: str = os.path.realpath(root_dir)
        self.build_id: Optional[str] = None
        self.build_date: Optional[str] = None
        self.build_version: Optional[str] = None

        # Required directories for a sandbox
        self.dirs = (
            "meta",
            "bin",
            "tmp",
            os.path.join("tmp", "cache"),
            "src",
            "log",
            "vcs",
            "patch",
        )
        self.meta_dir: str = ""
        self.tmp_dir: str = ""
        self.tmp_cache_dir: str = ""
        self.src_dir: str = ""
        self.log_dir: str = ""
        self.vcs_dir: str = ""
        self.patch_dir: str = ""
        self.bin_dir: str = ""
        self.is_alternate_specs_dir = False
        self.__specs_dir = os.path.join(self.root_dir, "specs")

        # Contains the loaded version of user.yaml if present
        self.user_config: Optional[Dict[str, Any]] = None

        # For each directory create an attribute containing its path
        for d in self.dirs:
            setattr(
                self,
                (f"{d}_dir").replace(os.path.sep, "_"),
                os.path.join(self.root_dir, d),
            )

        # specs_dir path can be changed by a configuration in user.yaml
        user_yaml = os.path.join(self.root_dir, "user.yaml")
        if os.path.exists(user_yaml):
            with open(user_yaml) as f:
                self.user_config = yaml.safe_load(f)

            # Accept both specs_dir and module_dir key (in that order) to
            # get the path to the anod specification files
            specs_dir = (
                self.user_config.get("specs_dir", self.user_config.get("module_dir"))
                if self.user_config is not None
                else None
            )
            if specs_dir is not None:
                self.specs_dir = specs_dir

        self.default_env = {
            "LANG": "C",
            "LC_ALL": "C",
            "LD_LIBRARY_PATH": "",
            "LIBRARY_PATH": "",
            "DYLD_LIBRARY_PATH": "",
            "DYLD_FALLBACK_LIBRARY_PATH": "",
            "PKG_CONFIG_PATH": "",
            "ADA_PROJECT_PATH": "",
            "GPR_PROJECT_PATH": "",
            "CPATH": "",
            "C_INCLUDE_PATH": "",
            "CPLUS_INCLUDE_PATH": "",
            "OBJC_INCLUDE_PATH": "",
            "GPR_RUNTIME_PATH": "",
        }

    def set_default_env(self) -> None:
        """Reset all env variables that can influence the build outcome."""
        for k, v in self.default_env.items():
            logger.debug('export %s="%s"', k, v)
            os.environ[k] = v

    @property
    def specs_dir(self) -> str:
        """Return where to find anod specification files."""
        return self.__specs_dir

    @specs_dir.setter
    def specs_dir(self, d: str) -> None:
        """Set an alternate specs dir.

        :param d: directory where to find anod specification files
        """
        self.__specs_dir = d
        self.is_alternate_specs_dir = True
        logger.debug("using alternate specs dir %s", d)

    def create_dirs(self) -> None:
        """Create all required sandbox directories."""
        for d in self.dirs:
            mkdir(getattr(self, f"{d}_dir".replace(os.path.sep, "_")))

    def get_build_space(self, name: str, platform: Optional[str] = None) -> BuildSpace:
        """Get build space.

        :param name: build space name
        :param platform: platform name (if None use the default platform)

        :return: A BuildSpace object
        """
        if platform is None:
            platform = Env().platform
        return BuildSpace(root_dir=os.path.join(self.root_dir, platform, name))

    def dump_configuration(self) -> None:
        # Compute command line for call to e3-sandbox create. Ensure that the
        # paths are made absolute (path to sandbox, script).
        cmd_line = [sys.executable, os.path.abspath(__file__)]
        cmd_line += sys.argv[1:]
        sandbox_conf = os.path.join(self.meta_dir, "sandbox.yaml")
        with open(sandbox_conf, "w") as f:
            yaml.safe_dump({"cmd_line": cmd_line}, f)

    def get_configuration(self) -> dict:
        sandbox_conf = os.path.join(self.meta_dir, "sandbox.yaml")
        with open(sandbox_conf) as f:
            return yaml.safe_load(f)

    def write_scripts(self) -> None:
        from setuptools.command.easy_install import get_script_args

        # Retrieve sandbox_scripts entry points
        e3_distrib = get_distribution("e3-core")

        class SandboxDist:
            def get_entry_map(self, group):  # type: ignore
                if group != "console_scripts":
                    return {}
                return e3_distrib.get_entry_map("sandbox_scripts")

            def as_requirement(self):  # type: ignore
                return e3_distrib.as_requirement()

        for script in get_script_args(dist=SandboxDist()):
            script_name = script[0]
            script_content = script[1]
            target = os.path.join(self.bin_dir, script_name)
            rm(target)
            if not script_name.endswith(".exe"):
                script_content = script_content.replace(
                    "console_scripts", "sandbox_scripts"
                )
            with open(target, "wb") as f:
                if isinstance(script_content, str):
                    f.write(script_content.encode("utf-8"))
                else:
                    f.write(script_content)
            chmod("a+x", target)
