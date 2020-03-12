"""High-Level interface to SVN repository.

Example::
    svn = SVNRepository(working_copy='/tmp/working_dir')
    svn.update(url='file:///path_to_local_repo', revision=1,
               force_and_clean=True)
"""


import os.path
import re
import sys
from subprocess import PIPE

import e3.log
import e3.os.fs
import e3.os.process
from e3.fs import mkdir, rm
from e3.vcs import VCSError

logger = e3.log.getLogger("vcs.svn")


class SVNError(VCSError):
    pass


class SVNRepository(object):
    """Interface to a SVN Repository.

    :cvar svn_bin: path to the SVN binary
    :cvar log_stream: stream where the log commands will be redirected
        (default is stdout)
    :ivar working_copy: path to the SVN working copy
    """

    svn_bin = None
    log_stream = sys.stdout

    def __init__(self, working_copy):
        """Initialize a SVNRepository object.

        :param working_copy: working copy of the SVNRepository
        :type working_copy: str
        """
        self.working_copy = working_copy

    @classmethod
    def is_unix_svn(cls):
        """Check if svn is handling unix paths or windows paths.

        :return: True if unix paths should be used
        :rtype: bool
        """
        if sys.platform != "win32":
            return True
        else:
            svn_version = e3.os.process.Run(["svn", "--version"]).out
            if "cygwin" in svn_version:
                return True
            else:
                return False

    @classmethod
    def local_url(cls, repo_path):
        """Return the url of a svn repository hosted locally.

        :param repo_path: path to the repo
        :type repo_path: str
        :return: the url that can be used as repository url
        :rtype: str
        """
        repo_path = os.path.abspath(repo_path)
        if not cls.is_unix_svn():
            if len(repo_path) > 1 and repo_path[1] == ":":
                # svn info returns the URL with an uppercase letter drive
                repo_path = repo_path[0].upper() + repo_path[1:]
            return "file:///" + repo_path.replace("\\", "/")
        else:  # windows: no cover
            return "file://" + e3.os.fs.unixpath(repo_path)

    @classmethod
    def create(cls, repo_path, initial_content_path=None):
        """Create a local subversion repository.

        This creates a local repository (not a working copy) that can be
        referenced by using file:// protocol. The purpose of the this function
        is mainly to test svn-related functions without relying on a remote
        repository.

        :param repo_path: a local directory where to create the repository
        :type repo_path: str
        :param initial_content_path: directory containing the initial content
            of the repository. If set to None an empty repository is created.
        :type initial_content_path: str | None
        :return: the URL of the newly created repository
        :rtype: str
        """
        repo_path = os.path.abspath(repo_path)
        p = e3.os.process.Run(["svnadmin", "create", repo_path], output=cls.log_stream)

        if cls.is_unix_svn():
            initial_content_path = e3.os.fs.unixpath(initial_content_path)

        if p.status != 0:
            raise SVNError(
                "cannot create svn repository in %s" % repo_path, origin="create"
            )
        if initial_content_path is not None:
            p = e3.os.process.Run(
                [
                    "svn",
                    "import",
                    initial_content_path,
                    cls.local_url(repo_path),
                    "-m",
                    "Initial import from %s" % initial_content_path,
                ],
                output=cls.log_stream,
            )
            if p.status != 0:
                raise SVNError(
                    "cannot perform initial import of %s into %s"
                    % (initial_content_path, repo_path),
                    origin="create",
                )
        return cls.local_url(repo_path)

    def svn_cmd(self, cmd, **kwargs):
        """Run a svn command.

        Add the non-interactive option to all command (accepted on all SVN.
        subcommands from version 1.5).
        :param cmd: the command line as a list of string, all None entries will
            be discarded
        :type cmd: list[str | None]
        :param kwargs: additional parameters to provide to e3.os.process.Run
        :type kwargs: dict
        :return: Result of the Run of the SVN command
        :rtype: Run object
        :raise: SVNError
        """
        if self.__class__.svn_bin is None:
            svn_binary = e3.os.process.which("svn", default=None)
            if svn_binary is None:  # defensive code
                raise SVNError("cannot find svn", "svn_cmd")
            self.__class__.svn_bin = e3.os.fs.unixpath(svn_binary)

        if "output" not in kwargs:
            kwargs["output"] = self.log_stream

        p_cmd = [arg for arg in cmd if arg is not None]
        p_cmd.insert(0, self.__class__.svn_bin)
        p_cmd.append("--non-interactive")

        p = e3.os.process.Run(p_cmd, cwd=self.working_copy, **kwargs)
        if p.status != 0:
            raise SVNError(
                "%s failed (exit status: %d)"
                % (e3.os.process.command_line_image(p_cmd), p.status),
                origin="svn_cmd",
                process=p,
            )
        return p

    def get_info(self, item):
        """Return a specific item shown by svn info.

        The --show-item option is only available from 1.9.
        :rtype: str
        :raise: SVNError
        """
        info = self.svn_cmd(["info"], output=PIPE).out
        m = re.search(r"^{item}: *(.*)\n".format(item=item), info, flags=re.M)
        if m is None:
            logger.debug("svn info result:\n%s", info)
            raise SVNError(
                "Cannot fetch item %s from svn_info" % item, origin="get_info"
            )
        return m.group(1).strip()

    @property
    def url(self):
        """Return the last URL used for the checkout.

        :rtype: str
        :raise: SVNError
        """
        return self.get_info("URL")

    @property
    def current_revision(self):
        """Return the current revision.

        :rtype: str
        :raise: SVNError
        """
        try:
            return self.get_info("Last Changed Rev")
        except Exception:
            logger.exception("Cannot fetch last changed rev")
            raise SVNError("Cannot fetch last changed rev", "svn_cmd")

    def update(self, url=None, revision=None, force_and_clean=False):
        """Update a working copy or checkout a new one.

        If the directory is already a checkout, it tries to update it.
        If the directory is not associated to a (good) checkout or is empty
        it will checkout.
        The option --remove-unversioned of the svn subcommand
        cleanup exists only from svn version 1.9.
        :param url: URL of a SVN repository
        :type url: str
        :param revision: specific revision (default is last)
        :type revision: str | None
        :param force_and_clean: if True: erase the content of non empty
        working_copy and use '--force' option for the svn update/checkout
        command
        :type force_and_clean: bool
        :return: True if any local changes detected in the working copy
        :rtype: bool
        :raise: SVNError
        """

        def is_clean_svn_dir(dir_path):
            """Return a tuple (True if dir is SVN directory, True if clean)."""
            if os.path.exists(os.path.join(dir_path, ".svn")):
                try:
                    status = self.svn_cmd(["status"], output=PIPE).out.strip()
                except SVNError:  # defensive code
                    return False, False
                if "warning: W" in status:
                    return False, False
                return True, status == ""
            return False, False

        def is_empty_dir(dir_path):
            """Return True if the path is a directory and is empty."""
            return os.path.isdir(dir_path) and not os.listdir(dir_path)

        options = ["--ignore-externals"]
        if revision:
            options += ["-r", revision]
        if force_and_clean:
            options += ["--force"]

        is_svn_dir, is_clean = is_clean_svn_dir(self.working_copy)
        if (
            is_svn_dir
            and (is_clean or not force_and_clean)
            and (not url or self.url == url)
        ):
            self.svn_cmd(["update"] + options)
            return not is_clean
        if os.path.exists(self.working_copy):
            if not is_empty_dir(self.working_copy) and not force_and_clean:
                raise SVNError(
                    "not empty {}".format(self.working_copy, url), origin="update"
                )
            if is_svn_dir and not url:
                url = self.url
            rm(self.working_copy, recursive=True)

        mkdir(self.working_copy)
        self.svn_cmd(["checkout", url, "."] + options)
        return not is_clean
