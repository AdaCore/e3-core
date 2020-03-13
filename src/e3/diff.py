import fnmatch
import io
import re
from difflib import unified_diff

import e3.error
import e3.log
import e3.os.process

logger = e3.log.getLogger("diff")


class DiffError(e3.error.E3Error):
    pass


def diff(
    a, b, ignore=None, item1name="expected", item2name="output", ignore_white_chars=True
):
    """Compute diff between two files or list of strings.

    :param a: a filename or a list of strings
    :type a: str | list[str]
    :param b: a filename or a list of strings
    :type b: str | list[str]
    :param ignore: all lines matching this pattern in both files are
        ignored during comparison. If set to None, all lines are considered.
    :type ignore: str | None
    :param str item1name: name to display for a in the diff
    :param str item2name: name to display for b in the diff
    :param bool ignore_white_chars: if True (default) then empty lines,
        trailing and leading white chars on each line are ignored

    :return: A diff string. If the string is equal to '' it means that there
        is no difference
    :rtype: str
    """
    contents = [[], []]
    """:type: list[list[str]]"""

    # Read first item
    if isinstance(a, list):
        contents[0] = a
    else:
        try:
            with open(a, "r") as f:
                contents[0] = f.readlines()
        except IOError:
            contents[0] = []

    # Do same thing for the second one
    if isinstance(b, list):
        contents[1] = b
    else:
        try:
            with open(b, "r") as f:
                contents[1] = f.readlines()
        except IOError:
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


def patch(patch_file, working_dir, discarded_files=None, filtered_patch=None):
    """Apply a patch, ignoring changes in files matching discarded_files.

    :param patch_file: the file containing the patch to apply
    :type patch_file: str
    :param working_dir: the directory where to apply the patch
    :type working_dir: str
    :param discarded_files: list of files or glob patterns (or function taking
        a filename and returning a boolean - True if the file should be
        discarded)
    :type discarded_files: list[str] | (str) -> bool | None
    :param filtered_patch: name of the filtered patch. By default append
        '.filtered' to the patch_file name
    :type filtered_patch: str | None
    """

    def apply_patch(fname):
        """Run the patch command.

        :type fname: str
        :raise DiffError: when the patch command fails
        """
        cmd = ["patch", "-p0", "-f"]
        p = e3.os.process.Run(cmd, cwd=working_dir, input=fname)
        if p.status != 0:
            raise DiffError(
                origin="patch",
                message="running %s < %s in %s failed with %s"
                % (" ".join(cmd), fname, working_dir, p.out),
            )
        logger.debug(p.out)

    if discarded_files is None:
        apply_patch(patch_file)
        return

    if filtered_patch is None:
        filtered_patch = patch_file + ".filtered"

    files_to_patch = 0

    with io.open(patch_file, "r", newline="") as f, io.open(
        filtered_patch, "w", newline=""
    ) as fdout:

        # Two line headers that mark beginning of patches
        header1 = ()
        header2 = ()
        header2_regexp = None
        # whether the current patch line should discarded
        discard = False

        def write_line(l):
            """Write line in filtered patch.

            :param l: the line to write
            :type l: str
            """
            if not discard:
                fdout.write(l)

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
                discard = False
                path_list = [fn for fn in (header1[1], header2[1]) if fn != "/dev/null"]
                if callable(discarded_files):
                    for fn in path_list:
                        if discarded_files(fn):
                            logger.debug("patch %s discarding %s" % (patch_file, fn))
                            discard = True
                            break
                else:
                    for pattern in discarded_files:
                        for fn in path_list:
                            if fnmatch.fnmatch(fn, pattern):
                                logger.debug(
                                    "patch %s discarding %s" % (patch_file, fn)
                                )
                                discard = True
                                break
                        if discard:
                            break
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

    if files_to_patch:
        apply_patch(filtered_patch)
    else:
        logger.debug("All %s content has been discarded", patch_file)
