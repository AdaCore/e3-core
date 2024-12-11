#!/usr/bin/env python
"""Build the wheel.

The number of commits since the last tagged version is automatically
added to the version of the package as the patch version.

For that, a tag v<major>.<minor>.0 must be manually added after the
merge when a major or minor version change occurs.
"""
from __future__ import annotations
import sys
from pathlib import Path
import re
import tomllib

from e3.main import Main
from e3.os.process import Run
from e3.log import getLogger

logger = getLogger("build_wheel")

ROOT_DIR = Path(__file__).parent


def run(cmd: list[str], fail_ok: bool | None = None) -> Run:
    """Print a command, run it, and print the result.

    :param cmd: the command
    :param fail_ok: allow the command to fail
    :return: the Run instance
    """
    logger.info(f"$ {' '.join(cmd)}")
    p = Run(cmd, cwd=str(ROOT_DIR))
    if p.status != 0 and not fail_ok:
        logger.error(p.out)
        sys.exit(1)

    logger.info(p.out)
    return p


def main() -> None:
    """Entrypoint."""
    main = Main()

    parser = main.argument_parser
    parser.description = "Build the wheel"
    parser.add_argument(
        "--last-tag",
        help="Provide the last tagged version",
    )

    main.parse_args()
    assert main.args

    # Find and read version file
    with open(ROOT_DIR / "pyproject.toml", "rb") as f:
        version_config = tomllib.load(f)["tool"]["setuptools"]["dynamic"]["version"]

    version_path = ROOT_DIR / (
        version_config["file"]
        if "file" in version_config
        else f'src/{version_config["attr"].replace(".", "/")}.py'
    )
    with open(version_path) as f:
        version_content = f.read()

    # Extract the <major>.<minor>(.<patch>)? part.
    # We will replace the patch version by the number of commits since the most
    # recent tagged version
    match = re.search(
        r"(?P<version>(?P<major>\d+)\.(?P<minor>\d+)(\.\w+)?)",
        version_content,
    )
    if not match:
        logger.error(
            f"No <major>.<minor>(.<patch>)? version found in {version_path.name}"
        )
        sys.exit(1)

    version_major = match.group("major")
    version_minor = match.group("minor")
    version = match.group("version")
    logger.info(f"Version is {version}")

    # Find previous version from the most recent tag
    last_tag = main.args.last_tag
    if not last_tag:
        # Need to unshallow the clone so we get the list of tags.
        # That command can fail for an already complete clone
        run(["git", "fetch", "--unshallow", "--tags"], fail_ok=True)
        # Describe the most recent tag
        p = run(["git", "describe", "--tags"])
        output = p.out
        assert output is not None
        last_tag = output.strip()

    # Format is v<major>.<minor>.<patch>(-<commits>)? with commits omitted if
    # the current commit is also the one tagged
    match = re.match(
        r"v(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\w+)(\-(?P<commits>\d+))?",
        last_tag,
    )
    if not match:
        logger.error(
            f"Expected v<major>.<minor>.<patch>(-<commits>)? format for tag {last_tag}"
        )
        sys.exit(1)

    # Ensure the major and minor versions match.
    # Also ensure the patch version is 0 because multiple tags for the same
    # <major>.<minor> would mess up with the versioning system and then only
    # <major>.<minor>.0 should exist
    tagged_version_major = match.group("major")
    tagged_version_minor = match.group("minor")
    tagged_version_patch = match.group("patch")
    if (version_major, version_minor, "0") != (
        tagged_version_major,
        tagged_version_minor,
        tagged_version_patch,
    ):
        logger.error(
            "Found tag "
            f"v{tagged_version_major}.{tagged_version_minor}.{tagged_version_patch} "
            f"but was expecting v{version_major}.{version_minor}.0. "
            "Please manually create the tag if not done yet or make sure this "
            "is the most recent tag"
        )
        sys.exit(1)

    # match.group("commits") is None only if the current commit is also
    # the one tagged so there is 0 commits since that tag
    new_version = "{}.{}.{}".format(
        version_major,
        version_minor,
        match.group("commits") or "0",
    )

    # Replace the version in the file
    logger.info(f"Set version to {new_version}")
    with open(version_path, "w") as f:
        f.write(version_content.replace(version, new_version))

    try:
        # Build the wheel
        run(
            [
                sys.executable,
                "-m",
                "pip",
                "wheel",
                ".",
                "-q",
                "--no-deps",
                "-C--python-tag=py3",
                "-w",
                "build",
            ]
        )
    finally:
        # Revert change to version file
        run(["git", "restore", str(version_path)], fail_ok=True)


if __name__ == "__main__":
    main()
