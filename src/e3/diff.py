from __future__ import annotations

import fnmatch
import re
from difflib import unified_diff
from typing import TYPE_CHECKING

import e3.error
import e3.log
import e3.os.process

if TYPE_CHECKING:
    from typing import Callable, List, Optional, Tuple

logger = e3.log.getLogger("diff")


class DiffError(e3.error.E3Error):
    pass


def diff(
    a: str | List[str],
    b: str | List[str],
    ignore: Optional[str] = None,
    item1name: str = "expected",
    item2name: str = "output",
    ignore_white_chars: bool = True,
) -> str:
    """Compute diff between two files or list of strings.

    :param a: a filename or a list of strings
    :param b: a filename or a list of strings
    :param ignore: all lines matching this pattern in both files are
        ignored during comparison. If set to None, all lines are considered.
    :param item1name: name to display for a in the diff
    :param item2name: name to display for b in the diff
    :param ignore_white_chars: if True (default) then empty lines,
        trailing and leading white chars on each line are ignored

    :return: A diff string. If the string is equal to '' it means that there
        is no difference
    """
    contents: List[List[str]] = [[], []]

    # Read first item
    if isinstance(a, list):
        contents[0] = a
    else:
        try:
            with open(a) as f:
                contents[0] = f.readlines()
        except OSError:
            contents[0] = []

    # Do same thing for the second one
    if isinstance(b, list):
        contents[1] = b
    else:
        try:
            with open(b) as f:
                contents[1] = f.readlines()
        except OSError:
            contents[1] = []

    # Filter empty lines in both items and ignore white chars at beginning
    # and ending of lines
    for k in (0, 1):
        if ignore_white_chars:
            contents[k] = [
                "%s\n" % line.strip() for line in contents[k] if line.strip()
            ]
        else:
            # Even if white spaces are not ignored we should ensure at
            # that we don't depend on platform specific newline
            contents[k] = ["%s\n" % line.rstrip("\r\n") for line in contents[k]]

        # If we have a filter apply it now
        if ignore is not None:
            contents[k] = [
                line for line in contents[k] if re.search(ignore, line) is None
            ]

    return "".join(unified_diff(contents[0], contents[1], item1name, item2name, n=1))


def patch(
    patch_file: str,
    working_dir: str,
    discarded_files: Optional[List[str] | Callable[[str], bool]] = None,
    filtered_patch: Optional[str] = None,
) -> None:
    """Apply a patch, ignoring changes in files matching discarded_files.

    :param patch_file: the file containing the patch to apply
    :param working_dir: the directory where to apply the patch
    :param discarded_files: list of files or glob patterns (or function taking
        a filename and returning a boolean - True if the file should be
        discarded)
    :param filtered_patch: name of the filtered patch. By default append
        '.filtered' to the patch_file name
    """
    # Detect if we can use git apply. I.e if the patch was generated with git
    # with default prefixes.
    is_git_patch = False

    with open(patch_file) as f:
        content = f.read()
        if re.search(r"^diff --git a/.* b/", content, flags=re.M):
            is_git_patch = True

    def apply_patch(fname: str) -> None:
        """Run the patch command.

        :raise DiffError: when the patch command fails
        """
        if is_git_patch:
            cmd = ["git", "apply", fname]
            p = e3.os.process.Run(cmd, cwd=working_dir)
        else:
            cmd = ["patch", "-p0", "-f"]
            p = e3.os.process.Run(cmd, cwd=working_dir, input=fname)
        if p.status != 0:
            raise DiffError(
                origin="patch",
                message="running %s < %s in %s failed with:\n%s"
                % (" ".join(cmd), fname, working_dir, p.out),
            )
        logger.debug(p.out)

    def discard_patch(path: str) -> bool:
        """Check if a file should be discarded.

        :param path: the path as encountered in the patch
        :return: True if the patch for that file should be discarded
        """
        if discarded_files is None:
            return False

        if path == "/dev/null":
            return False

        if is_git_patch and len(path) >= 2 and path[0] in "ab" and path[1] in "/\\":
            path = path[2:]

        if callable(discarded_files):
            if discarded_files(path):
                logger.debug(f"patch {patch_file} discarding {path}")
                return True
            else:
                return False
        else:
            for pattern in discarded_files:
                if fnmatch.fnmatch(path, pattern):
                    logger.debug(f"patch {patch_file} discarding {path}")
                    return True
            return False

    if discarded_files is None:
        apply_patch(patch_file)
        return

    if filtered_patch is None:
        filtered_patch = patch_file + ".filtered"

    def process_regular_patch() -> int:
        """Process a patch not formatted with git diff.

        :return: the number of files to patch after filtering
        """
        assert filtered_patch is not None
        files_to_patch = 0
        with open(patch_file, newline="") as f, open(
            filtered_patch, "w", newline=""
        ) as fdout:

            # Two line headers that mark beginning of patches
            header1: Tuple | Tuple[str, str] = ()
            header2: Tuple | Tuple[str, str] = ()
            header2_regexp = None
            # whether the current patch line should discarded
            discard = False

            def write_line(line: str) -> None:
                """Write line in filtered patch.

                :param l: the line to write
                """
                if not discard:
                    fdout.write(line)

            for line in f:
                if not header1:
                    # Check if we have a potential start of a 2 lines patch header
                    m = re.search(r"^[\*-]{3} ([^ \t\n]+)", line)
                    if m is None:
                        write_line(line)
                    else:
                        header1 = (line, m.group(1))
                        if line[0] == "-":
                            header2_regexp = r"^\+{3} ([^ \n\t]+)"
                        else:
                            header2_regexp = r"^-{3} ([^ \n\t]+)"
                elif not header2:
                    # Check if line next to a header first line confirm that that
                    # this is the start of a new patch
                    assert header2_regexp is not None
                    m = re.search(header2_regexp, line)
                    if m is None:
                        write_line(header1[0])
                        header1 = ()
                        write_line(line)
                    else:
                        header2 = (line, m.group(1))
                else:
                    # This is the start of patch. Decide whether to discard it or
                    # not
                    path_list = [header1[1], header2[1]]
                    discard = any((discard_patch(fn) for fn in path_list))

                    if not discard:
                        files_to_patch += 1
                        write_line(header1[0])
                        write_line(header2[0])
                        write_line(line)
                    header1 = ()
                    header2 = ()
            # Dangling lines
            if header1:
                write_line(header1[0])
            if header2:  # defensive code
                write_line(header2[0])
        return files_to_patch

    def process_git_patch() -> int:
        """Process a patch formatted with git diff.

        :return: the number of files to patch after filtering
        """
        assert filtered_patch is not None
        files_to_patch = 0
        with open(patch_file, newline="") as f, open(
            filtered_patch, "w", newline=""
        ) as fdout:
            discard = False
            for line in f:
                m = re.match("diff --git ([^ \n\t]+) ([^ \n\t]+)\r?\n?$", line)
                if m is not None:
                    # This is the start of a git patch
                    path_list = [m.group(1), m.group(2)]
                    discard = any((discard_patch(fn) for fn in path_list))

                    if not discard:
                        files_to_patch += 1

                if not discard:
                    fdout.write(line)
        return files_to_patch

    if is_git_patch:
        files_to_patch = process_git_patch()
    else:
        files_to_patch = process_regular_patch()
    if files_to_patch:
        apply_patch(filtered_patch)
    else:
        logger.debug("All %s content has been discarded", patch_file)
