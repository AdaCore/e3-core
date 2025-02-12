from __future__ import annotations
from e3.python.pypi import PyPIClosure, fetch_from_registry
from e3.python.wheel import Wheel
from e3.anod.checkout import CheckoutManager
from packaging.requirements import Requirement
from e3.main import Main
from e3.fs import mkdir, cp
from datetime import datetime
import argparse
import os
import re
import yaml
import logging
from sys import version_info as python_version_info

DESCRIPTION = """
This script generates a directory containing the full closure of a set
of Python requirements for a set of platforms and a given Python version

Config file has the following format:

    wheels:
        name1: url1#branch1
        name2: url2
    update_wheel_version_file: true
    requirements:
        - "req1"
        - "req2"
        - "req3"
    discard_from_closure: "regexp"
    frozen_requirement_file: "requirements.txt"

    platforms:
        - x86_64-linux
        - x86_64-windows
        - aarch64-linux

wheels contains the optional list of wheel that should be locally built
from source located at a git repository url (branch is specified after
a #, if no branch is specified master is assumed

update_wheel_version_file is an optional parameter to force version
update during generation of the wheels based on sources. The update
works only if the version is stored in a file called VERSION and the
version in this file has MAJOR.MINOR format. In that case during
generation the version is updated to MAJOR.MINOR.YYYYMMDD

requirements are additional python requirements as string

discard_from_closure are packages that should not be copied into the
target dir (packages do not appears also in the generated requirement
file)

frozen_requirement_file is the basename of the generated frozen requirement
file.

platforms is the list of platforms for which wheel should be fetched
"""


def main() -> None:
    m = Main()
    m.argument_parser.formatter_class = argparse.RawDescriptionHelpFormatter
    m.argument_parser.description = DESCRIPTION.strip()
    m.argument_parser.add_argument("config_file", help="configuration files")
    m.argument_parser.add_argument(
        "--python3-version",
        type=int,
        default=python_version_info.minor,
        help="python 3 version (default: %(default)s)",
    )
    m.argument_parser.add_argument("target_dir", help="target directory")
    m.argument_parser.add_argument(
        "--cache-dir", help="cache directory (default: %(default)s)", default="./cache"
    )
    m.argument_parser.add_argument(
        "--skip-repo-updates",
        action="store_true",
        help="don't update clones in the cache",
    )
    m.argument_parser.add_argument(
        "--local-clones",
        help="use local clones. When set look for git clones in a directory",
        default=None,
    )
    m.argument_parser.add_argument(
        "--allow-prerelease",
        dest="allowed_prerelease",
        metavar="PACKAGE",
        nargs="+",
        default=None,
        help="allow to use pre-release version for some requirements",
    )
    m.argument_parser.add_argument(
        "--allow-yanked",
        dest="allowed_yanked",
        metavar="PACKAGE",
        nargs="+",
        default=None,
        help="allow to use yanked version for some requirements (See: PEP_592)",
    )

    m.argument_parser.add_argument(
        "--wheel-build-arg",
        dest="wheel_build_args",
        action="append",
        help=argparse.SUPPRESS,
    )
    m.argument_parser.add_argument(
        "--check-target-registry",
        type=str,
        help="Checks whether the complete closure is present in the registry passed as "
        "a parameter. This option will only log errors if a package is missing.",
    )
    m.parse_args()
    assert m.args is not None

    vcs_cache_dir = os.path.abspath(os.path.join(m.args.cache_dir, "vcs"))
    wheel_cache_dir = os.path.abspath(os.path.join(m.args.cache_dir, "wheels"))
    mkdir(vcs_cache_dir)
    mkdir(wheel_cache_dir)
    mkdir(m.args.target_dir)

    # Load the configuration file
    with open(m.args.config_file) as fd:
        config = yaml.safe_load(fd.read())

    # First build the local wheels
    local_wheels = []

    # Should we attempt to update VERSION files for wheels
    update_version_file = config.get("update_wheel_version_file", False)

    for name, url in config.get("wheels", {}).items():
        logging.info(f"Fetch {name} sources")
        if "#" in url:
            url, rev = url.split("#", 1)
        else:
            rev = "master"
        checkout_manager = CheckoutManager(
            name=name, working_dir=os.path.join(vcs_cache_dir), compute_changelog=False
        )

        if m.args.local_clones is not None:
            checkout_manager.update(
                vcs="external",
                url=os.path.join(m.args.local_clones, url.split("/")[-1]),
                revision=rev,
            )
        else:
            if not m.args.skip_repo_updates:
                checkout_manager.update(vcs="git", url=url, revision=rev)

        if update_version_file:
            # Try to update the version file for the given repository. Update
            # is one only if there is file called VERSION and that the version
            # has the format MAJOR.MINOR
            version_file = os.path.join(checkout_manager.working_dir, "VERSION")
            if os.path.isfile(version_file):
                with open(version_file) as fd:
                    version = fd.read().strip()
                logging.info(f"Wheel {name} has version {version}")
                split_version = version.split(".")
                if len(split_version) == 2:
                    # We have a major and minor but no patch so add it automatically
                    version = f"{version}.{datetime.today().strftime('%Y%m%d%H%M')}"
                    with open(version_file, "w") as fd:
                        fd.write(version)

                    logging.info(f"Wheel {name} version updated to {version}")

        local_wheels.append(
            Wheel.build(
                source_dir=checkout_manager.working_dir,
                dest_dir=wheel_cache_dir,
                build_args=m.args.wheel_build_args,
            )
        )

    # Compute the list of toplevel requirements
    toplevel_reqs = {Requirement(wheel) for wheel in config.get("wheels", {})} | {
        Requirement(r) for r in config.get("requirements", [])
    }

    with PyPIClosure(
        cache_dir=wheel_cache_dir,
        python3_version=f"3.{m.args.python3_version}",
        platforms=config["platforms"],
        allowed_prerelease=m.args.allowed_prerelease,
        allowed_yanked=m.args.allowed_yanked,
    ) as pypi:
        for wheel in local_wheels:
            logging.info(f"Register wheel {wheel.path}")
            pypi.add_wheel(wheel.path)

        for req in toplevel_reqs:
            logging.info(f"Add top-level requirement {str(req)}")
            pypi.add_requirement(req)

        packages: set[str] = set()
        for f in pypi.file_closure():
            pkg_name = os.path.basename(f).split("-")[0].replace("_", "-")
            if "discard_from_closure" not in config or not re.search(
                config["discard_from_closure"], pkg_name
            ):
                cp(f, m.args.target_dir)
            packages.add(pkg_name)

        if m.args.check_target_registry:
            fetch_from_registry(
                packages, m.args.check_target_registry, log_missing_packages=True
            )

        with open(
            os.path.join(
                m.args.target_dir,
                config.get("frozen_requirement_file", "requirements.txt"),
            ),
            "w",
        ) as fd:
            for req in pypi.requirements_closure():
                if "discard_from_closure" not in config or not re.search(
                    config["discard_from_closure"], req.name
                ):
                    fd.write(f"{str(req)}\n")
