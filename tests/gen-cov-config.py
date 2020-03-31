#!/usr/bin/env python
# type: ignore


from argparse import ArgumentParser
import os

from e3.env import Env

from configparser import ConfigParser


def main(coverage_rc, omit_list_filename=None):
    os_name = Env().build.os.name
    test_dir = os.path.abspath(os.path.dirname(__file__))

    config = ConfigParser()
    base_conf, target_conf = (
        os.path.join(test_dir, "coverage", "%s.rc" % name) for name in ("base", os_name)
    )

    with open(coverage_rc, "w") as dest:
        config.read(base_conf)
        config.read(target_conf)

        # exclude lines is built with: base.rc config
        exclude_lines = config.get("report", "exclude_lines").splitlines()

        # add all <os>-only patterns
        exclude_lines += [
            "%s-only" % o
            for o in ("darwin", "linux", "solaris", "windows", "bsd", "aix")
            if o != os_name
        ]
        # exclude this specific os
        exclude_lines.append("%s: no cover" % os_name)

        # special case for unix
        if os_name != "windows":
            exclude_lines.append("unix: no cover")

        config.set("report", "exclude_lines", "\n".join(exclude_lines))

        # If the user gave a file with a list of "omit" entries,
        # read it, and append its contents to the run.omit option.

        if omit_list_filename is not None:
            if config.has_option("run", "omit"):
                omit = config.get("run", "omit").splitlines()
            else:
                omit = []
            with open(omit_list_filename) as f:
                for line in f:
                    omit.append(line)
            config.set("run", "omit", "\n".join(omit))

        config.write(dest)


if __name__ == "__main__":
    parser = ArgumentParser(description="Generate a coverage config file")
    parser.add_argument(
        "coverage_rc_filename", help="The name of the coverage configuration file."
    )
    parser.add_argument(
        "--omit-from-file",
        dest="omit_list_filename",
        help=(
            "The name of the file providing a list of files which should"
            " be excluded in the coverage report, with each line being"
            " a glob pattern matching the files that should be omitted."
            " This omit list is in addition to the list of files to"
            " be omitted by default."
        ),
    )

    args = parser.parse_args()
    main(args.coverage_rc_filename, omit_list_filename=args.omit_list_filename)
