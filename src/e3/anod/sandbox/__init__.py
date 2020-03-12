from pkg_resources import get_distribution

from e3.env import Env
from e3.fs import mkdir, rm

from e3.anod.error import SandBoxError
import e3.log
import e3.os.process

import os
import sys
import yaml

from e3.os.fs import chmod
from e3.anod.buildspace import BuildSpace

logger = e3.log.getLogger("sandbox")


class SandBox(object):
    def __init__(self):
        self.__root_dir = None
        self.build_id = None
        self.build_date = None
        self.build_version = None

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

        self.meta_dir = None
        self.tmp_dir = None
        self.tmp_cache_dir = None
        self.src_dir = None
        self.log_dir = None
        self.vcs_dir = None
        self.patch_dir = None
        self.bin_dir = None
        self.__specs_dir = None
        self.is_alternate_specs_dir = False

        # Contains the loaded version of user.yaml if present
        self.user_config = None

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

    def set_default_env(self):
        """Reset all env variables that can influence the build outcome."""
        for k, v in self.default_env.items():
            logger.debug('export %s="%s"', k, v)
            os.environ[k] = v

    @property
    def root_dir(self):
        """Root path of the sandbox.

        :raise SandBoxError: when the sandbox is not initialized
        :rtype: str
        """
        if self.__root_dir is None:
            raise SandBoxError(
                origin="root_dir", message="sandbox not loaded. Please call load()"
            )
        return self.__root_dir

    @root_dir.setter
    def root_dir(self, d):
        new_dir = os.path.realpath(d)
        if new_dir == self.__root_dir:
            return  # nothing to do

        self.__root_dir = new_dir

        # For each directory create an attribute containing its path
        for d in self.dirs:
            setattr(
                self, ("%s_dir" % d).replace(os.path.sep, "_"), os.path.join(new_dir, d)
            )

        # specs_dir path can be changed by a configuration in user.yaml
        user_yaml = os.path.join(new_dir, "user.yaml")
        if os.path.exists(user_yaml):
            with open(user_yaml) as f:
                self.user_config = yaml.safe_load(f)

            # Accept both specs_dir and module_dir key (in that order) to
            # get the path to the anod specification files
            specs_dir = self.user_config.get(
                "specs_dir", self.user_config.get("module_dir")
            )
            if specs_dir is not None:
                self.specs_dir = specs_dir
        else:
            self.__specs_dir = os.path.join(new_dir, "specs")

    @property
    def specs_dir(self):
        """Return where to find anod specification files."""
        return self.__specs_dir

    @specs_dir.setter
    def specs_dir(self, d):
        """Set an alternate specs dir.

        :param d: directory where to find anod specification files
        :type d: str
        """
        # Expand ~, environment variables and eliminate symbolic links
        self.__specs_dir = os.path.realpath(os.path.expandvars(os.path.expanduser(d)))
        self.is_alternate_specs_dir = True
        logger.info("using alternate specs dir %s", d)

    def create_dirs(self):
        """Create all required sandbox directories."""
        for d in self.dirs:
            mkdir(getattr(self, ("%s_dir" % d).replace(os.path.sep, "_")))

    def get_build_space(self, name, platform=None):
        """Get build space.

        :param name: build space name
        :type name: str
        :param platform: platform name (if None use the default platform)
        :type platform: str | None

        :return: A BuildSpace object
        :rtype: BuildSpace
        """
        if platform is None:
            platform = Env().platform
        return BuildSpace(root_dir=os.path.join(self.root_dir, platform, name))

    def dump_configuration(self):
        # Compute command line for call to e3-sandbox create. Ensure that the
        # paths are made absolute (path to sandbox, script).
        cmd_line = [sys.executable, os.path.abspath(__file__)]
        cmd_line += sys.argv[1:]
        sandbox_conf = os.path.join(self.meta_dir, "sandbox.yaml")
        with open(sandbox_conf, "w") as f:
            yaml.safe_dump({"cmd_line": cmd_line}, f)

    def get_configuration(self):
        sandbox_conf = os.path.join(self.meta_dir, "sandbox.yaml")
        with open(sandbox_conf, "r") as f:
            return yaml.safe_load(f)

    def write_scripts(self):
        from setuptools.command.easy_install import get_script_args

        # Retrieve sandbox_scripts entry points
        e3_distrib = get_distribution("e3-core")

        class SandboxDist(object):
            def get_entry_map(self, group):
                if group != "console_scripts":
                    return {}
                return e3_distrib.get_entry_map("sandbox_scripts")

            def as_requirement(self):
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
