"""Helpers classes and functions for ANOD."""


from __future__ import annotations

import io
import os
import re
from typing import TYPE_CHECKING

import e3.log
from e3.anod.spec import Anod, parse_command
from e3.os.fs import unixpath

if TYPE_CHECKING:
    from typing import Dict, List, Optional, Tuple
    from e3.os.process import Run

log = e3.log.getLogger("anod.helpers")


class Make:
    """Wrapper around GNU Make."""

    def __init__(
        self,
        anod_instance: Anod,
        makefile: Optional[str] = None,
        exec_dir: Optional[str] = None,
        jobs: Optional[int] = None,
        make_exe: str = "make",
    ):
        """Initialize a Make object.

        :param anod_instance: an Anod instance
        :param makefile: the Makefile to use
        :param exec_dir: path to the directory from where the make should be
            called. If None use the anod instance buildspace build dir.
        :param jobs: number of jobs to run in parallel
        :param make: make executable to use (by default make on the path)
        """
        self.anod_instance = anod_instance
        self.exec_dir = exec_dir

        if self.exec_dir is None:
            self.exec_dir = self.anod_instance.build_space.build_dir
        self.makefile = makefile
        self.jobs = jobs
        if jobs is None:
            self.jobs = anod_instance.jobs
        self.var_list = {}  # type: Dict[str, str]
        self.default_target = None  # type: Optional[str]
        self.make_exe = make_exe

    def set_var(self, name: str, value: str | List[str]) -> None:
        """Set a Make variable.

        :param name: name of the variable
        :param value: value of the variable, can be a string or a list
            if it's the list, it will be stored in a string with each
            value separated by a space character
        """
        if isinstance(value, str):
            self.var_list[name] = value
        else:
            # Assume we get a list
            self.var_list[name] = " ".join(value)

    def set_default_target(self, target: str) -> None:
        """Set default make target.

        :param target: the target name to use if __call__ is called with
            target=None
        """
        self.default_target = target

    def __call__(
        self,
        target: Optional[str] = None,
        jobs: Optional[int] = None,
        exec_dir: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> Run:
        """Call a make target.

        :param target: the target to use (use default_target if None)
        :param jobs: see __init__ documentation
        :param exec_dir: see __init__ documentation
        :param timeout: timeout to pass to ex.Run
        """
        cmdline = self.cmdline(target, jobs, exec_dir, timeout=timeout)
        cmd = cmdline["cmd"]
        options = cmdline["options"]
        return self.anod_instance.shell(*cmd, **options)  # type: ignore

    def cmdline(
        self,
        target: Optional[str | List[str]] = None,
        jobs: Optional[int] = None,
        exec_dir: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> Dict[str, List[str] | dict]:
        """Return the make command line.

        :param target: optional target or list of targets to use
            (use default_target if None)
        :param jobs: see __init__ documentation
        :param exec_dir: see __init__ documentation
        :param timeout: timeout to pass to ex.Run

        :return: a dictionary with the following keys
           - cmd: containing the command line to pass to gnatpython.ex.Run
           - options: options to pass to gnatpython.ex.Run
        """
        cmd_arg_list = [self.make_exe]

        if self.makefile is not None:
            cmd_arg_list += ["-f", unixpath(self.makefile)]

        cmd_arg_list += ["-j", str(jobs) if jobs is not None else str(self.jobs)]

        for key in self.var_list:
            cmd_arg_list.append("{}={}".format(key, self.var_list[key]))

        if target is None:
            target = self.default_target

        if target is not None:
            if isinstance(target, list):
                cmd_arg_list += target
            else:
                cmd_arg_list.append(target)

        options = {"cwd": exec_dir or self.exec_dir, "timeout": timeout}

        return {
            "cmd": parse_command(
                command=cmd_arg_list, build_space=self.anod_instance.build_space
            ),
            "options": options,
        }


class Configure:
    """Wrapper around ./configure."""

    def __init__(
        self,
        anod_instance: Anod,
        src_dir: Optional[str] = None,
        exec_dir: Optional[str] = None,
        auto_target: bool = True,
    ):
        """Initialize a Configure object.

        :param anod_instance: an Anod instance
        :param src_dir: path to the directory containing the project sources.
            If None then use the anod_instance buildspace source dir.
        :param exec_dir: path to the directory from where the configure should
            be called. If None then use the anod_instance buildspace build
            dir.
        :param auto_target: if True, automatically pass --target, --host and
            --build
        """
        self.anod_instance = anod_instance
        if src_dir is None:
            self.src_dir = self.anod_instance.build_space.src_dir
        else:
            self.src_dir = src_dir
        self.exec_dir = exec_dir
        if self.exec_dir is None:
            self.exec_dir = self.anod_instance.build_space.build_dir
        self.args = []  # type: List[str]

        # Value of the --target, --host and --build arguments
        self.target = None
        self.host = None
        self.build = None

        if auto_target:
            e = anod_instance.env
            if e.is_canadian:
                self.target = e.target.triplet
                self.host = e.host.triplet
                self.build = e.build.triplet
            elif e.is_cross:
                self.target = e.target.triplet
                self.build = e.build.triplet
            else:
                self.build = e.target.triplet

        self.env = {}  # type: dict

    def add(self, *args: str) -> None:
        """Add configure options.

        :param args: list of options to pass when calling configure
        """
        self.args += args

    def add_env(self, key: str, value: str) -> None:
        """Set environment variable when calling configure.

        :param key: environment variable name
        :param value: environment variable value
        """
        self.env[key] = value

    def cmdline(self) -> dict:
        """Return the configure command line.

        :return: a dictionary with the following keys
           - cmd: containing the command line to pass to gnatpython.ex.Run
           - options: options to pass to gnatpython.ex.Run

        If CONFIG_SHELL environment variable is set, the configure will be
        called with this shell.
        """
        cmd = []
        if "CONFIG_SHELL" in os.environ:
            cmd.append(os.environ["CONFIG_SHELL"])

        # Compute the relative path for configure
        configure_path = unixpath(
            os.path.relpath(os.path.join(self.src_dir, "configure"), self.exec_dir)
        )

        # In case the configure is run from its location ensure to
        # add ./ as . is not necessary in PATH.
        if configure_path == "configure":
            configure_path = "./configure"
        cmd += [configure_path]
        cmd += self.args

        if self.target is not None:
            cmd.append("--target=" + self.target)

        if self.host is not None:
            cmd.append("--host=" + self.host)

        if self.build is not None:
            cmd.append("--build=" + self.build)

        cmd_options = {"cwd": self.exec_dir, "ignore_environ": False, "env": self.env}

        return {
            "cmd": parse_command(
                command=cmd, build_space=self.anod_instance.build_space
            ),
            "options": cmd_options,
        }

    def __call__(self) -> Run:
        cmdline = self.cmdline()
        cmd = cmdline["cmd"]
        options = cmdline["options"]
        return self.anod_instance.shell(*cmd, **options)


def text_replace(
    filename: str, pattern: List[Tuple[bytes | str, bytes | str]]
) -> List[int]:
    """Replace patterns in a file.

    :param filename: file path
    :param pattern: list of tuple (pattern, replacement)

    Do not modify the file if no substitution is done. Note that substitutions
    are applied sequentially (order provided by the list `pattern`) and this
    is done line per line.

    :return: the number of substitution performed for each pattern
    """
    output = io.BytesIO()
    nb_substitution = [0 for _ in pattern]
    with open(filename, "rb") as f:
        for line in f:
            for pattern_index, (regexp, replacement) in enumerate(pattern):
                if isinstance(replacement, str):
                    replacement = replacement.encode("utf-8")
                if isinstance(regexp, str):
                    regexp = regexp.encode("utf-8")
                line, count = re.subn(regexp, replacement, line)
                if count:
                    nb_substitution[pattern_index] += count
            output.write(line)
    if any(nb for nb in nb_substitution):
        # file changed, update it
        with open(filename, "wb") as f:
            f.write(output.getvalue())
    output.close()
    return nb_substitution
