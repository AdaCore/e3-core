#!/usr/bin/env python
"""Build the wheel.

The number of commits since the last major/minor version change is automatically
added to the version of the package as the patch version.
"""
from __future__ import annotations
import sys
from pathlib import Path
import re
import tomllib
from datetime import datetime, timezone

from e3.main import Main
from e3.os.process import Run
from e3.log import getLogger

logger = getLogger("build_wheel")


def run(cmd: list[str], cwd: Path, fail_ok: bool | None = None) -> str:
    """Run a command and check the status.

    :param cmd: the command
    :param cwd: the directory where to run the command
    :param fail_ok: allow the command to fail
    :return: the output of the command
    """
    p = Run(cmd, cwd=cwd)
    if p.status != 0 and not fail_ok:
        logger.error(p.out)
        sys.exit(1)

    output = p.out
    assert output is not None
    return output


def main() -> None:
    """Entrypoint."""
    main = Main()

    parser = main.argument_parser
    parser.description = "Build the wheel"
    parser.add_argument(
        "--project",
        default="pyproject.toml",
        help="Path to a Python project or pyproject.toml file",
    )
    parser.add_argument(
        "--template", default="{major}.{minor}.{patch}", help="Version number template"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not change the version file nor build the wheel",
    )
    parser.add_argument(
        "--no-build", action="store_true", help="Do not build the wheel"
    )
    parser.add_argument(
        "--no-restore",
        action="store_true",
        help="Keep the modified version file with the computed build version",
    )

    main.parse_args()
    assert main.args

    project = Path(main.args.project)
    if project.is_dir():
        project = project / "pyproject.toml"

    logger.debug(f"Project dir: {project.parent}")
    if not project.is_file():
        logger.error(f"{project} is not a file")
        sys.exit(1)

    # Find the path to version file
    with open(project, "rb") as f:
        version_config = (
            tomllib.load(f)
            .get("tool", {})
            .get("setuptools", {})
            .get("dynamic", {})
            .get("version")
        )

    if version_config is None:
        logger.error("Missing the version key in [tool.setuptools.dynamic] section")
        sys.exit(1)

    version_path = (
        version_config["file"]
        if "file" in version_config
        else f'src/{version_config["attr"].replace(".", "/")}.py'
    )
    logger.debug(f"Version path: {version_path}")

    # Read the version
    root_dir = project.parent
    version_abspath = root_dir / version_path
    with open(version_abspath) as f:
        version_content = f.read()

    # Extract the <major>.<minor>(.<patch>)? part.
    # We will replace the patch version by the number of commits since the most
    # recent tagged version
    version_pattern = r"(?P<version>(?P<major>\d+)\.(?P<minor>\d+)(\.\w+)?)"
    match = re.search(version_pattern, version_content)
    if not match:
        logger.error(f"No <major>.<minor>(.<patch>)? version found in {version_path}")
        sys.exit(1)

    version_major = match.group("major")
    version_minor = match.group("minor")
    version = match.group("version")
    logger.debug(f"Version: {version}")

    # Need to unshallow the clone to get all commits.
    # That command can fail for an already complete clone
    run(["git", "fetch", "--unshallow", "--tags"], cwd=root_dir, fail_ok=True)

    # Walk through the commits on the main branch only that modified the version file
    output = run(
        ["git", "log", "--first-parent", "--format=format:%H", version_path],
        cwd=root_dir,
    )

    # Find the SHA when the major/minor version changed
    previous_commit_sha = "HEAD"
    for commit_sha in output.strip().splitlines():
        output = run(["git", "show", f"{commit_sha}:{version_path}"], cwd=root_dir)
        match = re.search(version_pattern, output)
        if (
            not match
            or version_major != match.group("major")
            or version_minor != match.group("minor")
        ):
            logger.debug(f"Different version found at commit {commit_sha}")
            break

        previous_commit_sha = commit_sha

    # Count the number of commits since that SHA.
    output = run(
        ["git", "rev-list", f"{previous_commit_sha}..HEAD", "--count"],
        cwd=root_dir,
    )

    # Get the build version from custom version template
    date = datetime.now(tz=timezone.utc)
    build_version = main.args.template.format(
        major=version_major,
        minor=version_minor,
        patch=output.strip(),
        year=f"{date.year:04}",
        month=f"{date.month:02}",
        day=f"{date.day:02}",
    )
    logger.info(f"{version_major}.{version_minor} -> {build_version}")

    if not main.args.dry_run:
        # Replace the version in the file
        with open(version_abspath, "w") as f:
            f.write(version_content.replace(version, build_version))

        try:
            # Build the wheel
            if not main.args.no_build:
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
                    ],
                    cwd=root_dir,
                )
        finally:
            # Revert change to version file
            if not main.args.no_restore:
                run(["git", "restore", version_path], cwd=root_dir, fail_ok=True)


if __name__ == "__main__":
    main()
