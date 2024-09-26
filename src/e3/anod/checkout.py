from __future__ import annotations

import hashlib
import json
import os
import tempfile
from contextlib import closing
from typing import TYPE_CHECKING

import e3.log
from e3.anod.status import ReturnValue
from e3.os.fs import unixpath, which
from e3.os.process import PIPE, Run
from e3.fs import VCS_IGNORE_LIST, get_filetree_state, rm, sync_tree
from e3.vcs.git import GitError, GitRepository
from e3.vcs.svn import SVNError, SVNRepository

if TYPE_CHECKING:
    from typing import Literal
    from collections.abc import Callable
    from e3.mypy import assert_never

logger = e3.log.getLogger("e3.anod.checkout")


class CheckoutManager:
    """Helper class to manage checkouts done by Anod tools.

    When a checkout manager is used in working_dir directory for a repository
    called name. The following structure will be found on disk after an update

        working_dir/name/               The repository checkout
                   /name_checkout.json  A json containing some metadata: name,
                                        url, old_commit, new_commit, revision
                   /name_changelog.json A json containing the list of commit
                                        between two call to update. If this is
                                        the inital checkout or there are no
                                        changes then the file will not be
                                        created
    """

    def __init__(self, name: str, working_dir: str, compute_changelog: bool = True):
        """Initialize CheckoutManager instance.

        :param name: a symbolic name for that checkout
        :param working_dir: working directory in which checkouts are
            performed. Note that the checkout will be done in the
            ```name``` subdirectory.
        :param compute_changelog: if True compute a changelog of changes
            done since last update
        """
        self.name = name
        self.compute_changelog = compute_changelog
        self.working_dir = os.path.abspath(os.path.join(working_dir, self.name))
        self.metadata_file = self.working_dir + "_checkout.json"
        self.changelog_file = self.working_dir + "_changelog.json"

    def update(
        self,
        vcs: Literal["git"] | Literal["svn"] | Literal["external"],
        url: str,
        revision: str | None = None,
    ) -> ReturnValue:
        """Update content of the working directory.

        :param vcs: vcs kind
        :param url: repository url, when vcs is external the url is the path
             to the source directory
        :param revision: revision

        Note that when vcs is set to git or svn, the version control ignore
        setting is taken into account. Additionally, when the vcs is
        external and the source directory contains a .git subdirectory then
        git ignore setting is taken into account.
        """
        # Reset changelog file
        if os.path.isfile(self.changelog_file):
            rm(self.changelog_file)

        update: Callable[[str, str | None], tuple[ReturnValue, str | None, str | None]]
        if vcs == "git":
            update = self.update_git
        elif vcs == "svn":
            update = self.update_svn
        elif vcs == "external":
            update = self.update_external
        else:
            assert_never()

        result, old_commit, new_commit = update(url=url, revision=revision)

        with open(self.metadata_file, "w") as fd:
            json.dump(
                {
                    "name": self.name,
                    "url": url,
                    "old_commit": old_commit,
                    "new_commit": new_commit,
                    "revision": revision,
                },
                fd,
            )
        return result

    def update_external(
        self, url: str, revision: str | None
    ) -> tuple[ReturnValue, str, str]:
        """Update working dir using a local directory.

        :param url: path to the repository
        :param revision: ignored

        If <url>/.git is a directory then git ls-files will be called to get
        the list of files to ignore.
        """
        if os.path.isdir(self.working_dir):
            old_commit = get_filetree_state(self.working_dir, ignore_hidden=False)
        else:
            old_commit = ""
        ignore_list: list[str] = []

        if which("rsync") and "use-rsync" in os.environ.get(
            "E3_ENABLE_FEATURE", ""
        ).split(","):
            # Run rsync using -a but without preserving timestamps. --update switch
            # is also used to skip files that are older in the user directory than
            # in the checkout itself. This ensure rsync remain efficient event when
            # timestamps are not preserved (otherwise rsync has to compute checksum
            # of all file as quick check cannot be used when timestamp is not
            # preserved).
            rsync_cmd = [
                "rsync",
                "--update",
                "-rlpgoD",
                f"{unixpath(url)}/",
                f"{unixpath(self.working_dir)}",
                "--delete-excluded",
            ] + [f"--exclude={el}" for el in VCS_IGNORE_LIST]

            if os.path.isdir(os.path.join(url, ".git")) and os.path.isfile(
                os.path.join(url, ".gitignore")
            ):
                rsync_cmd.append("--filter=:- .gitignore")

            p = Run(rsync_cmd, cwd=url, output=None)
            if p.status != 0:
                raise e3.error.E3Error("rsync failed")
        else:
            # Test for a git repository by looking for ".git" in the current
            # directory - either as a file or as a directory. We check both
            # because, if a normal git clone, ".git" is a directory; if a
            # git clone with `git submodule init`, ".git" is a file.
            if os.path.exists(os.path.join(url, ".git")):
                # It seems that this is a git repository. Get the list of files to
                # ignore
                try:
                    g = GitRepository(working_tree=url)
                    ignore_list_lines = g.git_cmd(
                        [
                            "ls-files",
                            "-o",
                            "--ignored",
                            "--exclude-standard",
                            "--directory",
                        ],
                        output=PIPE,
                    ).out

                    ignore_list = (
                        []
                        if ignore_list_lines is None
                        else [
                            f"/{f.strip().rstrip('/')}"
                            for f in ignore_list_lines.splitlines()
                        ]
                    )
                    logger.debug("Ignore in external: %s", ignore_list)
                except Exception:  # defensive code
                    # don't crash on exception
                    pass

            sync_tree(
                url,
                self.working_dir,
                preserve_timestamps=False,
                delete_ignore=True,
                ignore=[".git", ".svn"] + ignore_list,
            )

        new_commit = get_filetree_state(self.working_dir, ignore_hidden=False)
        if new_commit == old_commit:
            return ReturnValue.unchanged, old_commit, new_commit
        else:
            return ReturnValue.success, old_commit, new_commit

    @staticmethod
    def git_remote_name(url: str) -> str:
        """Return the remote name computed for an url.

        :param url: the git url
        :return: the remote name
        """
        return hashlib.sha256(url.encode("utf-8")).hexdigest()

    def update_git(
        self, url: str, revision: str | None
    ) -> tuple[ReturnValue, str | None, str | None]:
        """Update working dir using a Git repository.

        :param url: git repository url
        :param revision: git revision
        """
        # For git repositories revision cannot be None
        if revision is None:
            return ReturnValue.failure, None, None

        g = GitRepository(working_tree=self.working_dir)
        g.log_stream = e3.log.default_output_stream
        old_commit, new_commit = None, None

        # Create a remote for which name is bind to a an url
        # This ensure that when the url does not change, git will not
        # redownload all the objects on each objects (and thus avoid
        # disk space leaks).
        remote_name = self.git_remote_name(url)

        g.init()

        # Do the remote addition manually as in that context we can ignore
        # safely any error returned by this command.
        try:
            output_str = g.git_cmd(["remote"], output=PIPE).out

            remote_list = output_str.splitlines() if output_str else []

            if remote_name not in remote_list:
                g.git_cmd(["remote", "add", remote_name, url])
        except Exception:  # defensive code
            # Ignore exception as it probably means that remote already exist
            # In case of real error the failure will be detected later.
            pass

        try:
            old_commit = g.rev_parse()

            shallow_cmd: str | None = None

            # Using fetch + checkout ensure caching is effective
            shallow_fetch = "git_shallow_fetch" in os.environ.get(
                "E3_ENABLE_FEATURE", ""
            ).split(",")

            for feature in os.environ.get("E3_ENABLE_FEATURE", "").split(","):
                if "git_fetch_shallow_since" in feature:
                    date = feature.removeprefix("git_fetch_shallow_since=")
                    shallow_cmd = f"--shallow-since={date}"

            for feature in os.environ.get("E3_ENABLE_FEATURE", "").split(","):
                if "git_fetch_max_depth" in feature:
                    depth = feature.removeprefix("git_fetch_max_depth=")
                    shallow_cmd = f"--depth={depth}"

            if shallow_fetch and (not self.compute_changelog or not old_commit):
                shallow_cmd = "--depth=1"

            g.git_cmd(
                [
                    "fetch",
                    "-f",
                    shallow_cmd,
                    remote_name,
                    f"{revision}:refs/e3-checkout",
                ]
            )

            g.checkout("refs/e3-checkout", force=True)
            new_commit = g.rev_parse()

            # Verify that there is no local change
            p = g.git_cmd(["status", "--porcelain"], output=PIPE)
            if p.out:
                logger.error(
                    "Repository %s is locally modified, saving diff in stash\n%s",
                    self.name,
                    p.out,
                )
                g.git_cmd(["stash", "save", "-u"])

            result = (
                ReturnValue.unchanged
                if old_commit == new_commit
                else ReturnValue.success
            )
            if self.compute_changelog:
                # Fetch the change log and dump it into the changelog file
                with closing(tempfile.NamedTemporaryFile(mode="w", delete=False)) as fd:
                    g.write_log(fd, rev_range=f"{old_commit}..{new_commit}")
                    tmp_filename = fd.name
                try:
                    with open(tmp_filename, encoding="utf8") as fd:
                        commits = list(g.parse_log(fd, max_diff_size=1024))
                finally:
                    rm(tmp_filename)

                with open(self.changelog_file, "w") as fd:
                    json.dump(commits, fd)

        except GitError:
            logger.exception(f"Error during git update {self.name}")
            result = ReturnValue.failure
        return result, old_commit, new_commit

    def update_svn(
        self, url: str, revision: str | None
    ) -> tuple[ReturnValue, str | None, str | None]:
        """Update working dir using a SVN repository.

        :param url: git repository url
        :param revision: git revision
        """
        working_copy = SVNRepository(working_copy=self.working_dir)
        working_copy.log_stream = e3.log.default_output_stream
        old_commit, new_commit = None, None
        result = ReturnValue.success

        if os.path.isdir(self.working_dir):  # a possible checkout exists
            try:
                old_commit = working_copy.current_revision
            except SVNError:
                logger.error(
                    "Unable to get SVN informations form the %s working dir",
                    self.name,
                )
        try:
            # Remove local change and update the working copy
            local_change_detected = working_copy.update(
                url=url, revision=revision, force_and_clean=True
            )
        except SVNError:  # impossible to update, potential local changes
            logger.error("Impossible to update the working copy of %s", self.name)
            result = ReturnValue.failure
        else:
            new_commit = working_copy.current_revision
            if local_change_detected:
                logger.error(
                    "Repository %s was locally modified, clean done.", self.name
                )
            if old_commit == new_commit:
                result = ReturnValue.unchanged
            else:
                result = ReturnValue.success
        return result, old_commit, new_commit
