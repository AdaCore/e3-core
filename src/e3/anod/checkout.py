import hashlib
import json
import os
import tempfile
from contextlib import closing
from subprocess import PIPE

import e3.log
from e3.anod.status import ReturnValue
from e3.fs import get_filetree_state, rm, sync_tree, VCS_IGNORE_LIST
from e3.vcs.git import GitRepository, GitError
from e3.vcs.svn import SVNRepository, SVNError

logger = e3.log.getLogger("e3.anod.checkout")


class CheckoutManager(object):
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

    def __init__(self, name, working_dir, compute_changelog=True):
        """Initialize CheckoutManager instance.

        :param name: a symbolic name for that checkout
        :type name: str
        :param working_dir: working directory in which checkouts are
            performed. Note that the checkout will be done in the
            ```name``` subdirectory.
        :type working_dir: str
        :param compute_changelog: if True compute a changelog of changes
            done since last update
        :type compute_changelog: bool
        """
        self.name = name
        self.compute_changelog = compute_changelog
        self.working_dir = os.path.abspath(os.path.join(working_dir, self.name))
        self.metadata_file = self.working_dir + "_checkout.json"
        self.changelog_file = self.working_dir + "_changelog.json"

    def update(self, vcs, url, revision=None):
        """Update content of the working directory.

        :param vcs: vcd kind
        :type vcs: str
        :param url: repository url
        :type url: str
        :param revision: revision
        :type revision: str | None
        """
        # Reset changelog file
        if os.path.isfile(self.changelog_file):
            rm(self.changelog_file)

        if vcs == "git":
            update = self.update_git
        elif vcs == "svn":
            update = self.update_svn
        elif vcs == "external":
            update = self.update_external
        else:
            logger.error("Invalid repository type: %s" % vcs)
            return ReturnValue.failure

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

    def update_external(self, url, revision):
        """Update working dir using a local directory.

        :param url: path to the repository
        :type url: str
        :param revision: ignored
        :type revision: None
        """
        # Expand env variables and ~
        url = os.path.expandvars(os.path.expanduser(url))

        if os.path.isdir(self.working_dir):
            old_commit = get_filetree_state(self.working_dir)
        else:
            old_commit = ""
        ignore_list = []

        if os.path.isdir(os.path.join(url, ".git")):
            # It seems that this is a git repository. Get the list of files to
            # ignore
            try:
                g = GitRepository(working_tree=url)
                ignore_list = g.git_cmd(
                    [
                        "ls-files",
                        "-o",
                        "--ignored",
                        "--exclude-standard",
                        "--directory",
                    ],
                    output=PIPE,
                ).out
                ignore_list = [
                    "/%s" % l.strip().rstrip("/") for l in ignore_list.splitlines()
                ]
                logger.debug("Ignore in external: %s", ignore_list)
            except Exception:
                # don't crash on exception
                pass

        sync_tree(
            url,
            self.working_dir,
            preserve_timestamps=False,
            delete_ignore=True,
            ignore=list(VCS_IGNORE_LIST) + ignore_list,
        )

        new_commit = get_filetree_state(self.working_dir)
        if new_commit == old_commit:
            return ReturnValue.unchanged, old_commit, new_commit
        else:
            return ReturnValue.success, old_commit, new_commit

    def update_git(self, url, revision):
        """Update working dir using a Git repository.

        :param url: git repository url
        :type url: str
        :param revision: git revision
        :type revision: str
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
        if isinstance(url, str):
            remote_name = hashlib.sha256(url.encode("utf-8")).hexdigest()
        else:
            remote_name = hashlib.sha256(url).hexdigest()
        g.init()

        # Do the remote addition manually as in that context we can ignore
        # safely any error returned by this command.
        try:
            remote_list = g.git_cmd(["remote"], output=PIPE).out.splitlines()
            if remote_name not in remote_list:
                g.git_cmd(["remote", "add", remote_name, url])
        except Exception:
            # Ignore exception as it probably means that remote already exist
            # In case of real error the failure will be detected later.
            pass

        try:
            old_commit = g.rev_parse()

            # Using fetch + checkout ensure caching is effective
            g.git_cmd(["fetch", "-f", remote_name, "%s:refs/e3-checkout" % revision])
            g.checkout("refs/e3-checkout", force=True)
            new_commit = g.rev_parse()

            # Verify that there is no local change
            p = g.git_cmd(["status", "--porcelain"], output=PIPE)
            if p.out:
                logger.error(
                    "Repository %s is locally modified, saving " "diff in stash\n%s",
                    self.name,
                    p.out,
                )
                g.git_cmd(["stash", "save", "-u"])

            if old_commit == new_commit:
                result = ReturnValue.unchanged
            elif self.compute_changelog:
                # Fetch the change log and dump it into the changelog file
                with closing(tempfile.NamedTemporaryFile(mode="w", delete=False)) as fd:
                    g.write_log(fd, rev_range="%s..%s" % (old_commit, new_commit))
                    tmp_filename = fd.name
                try:
                    with open(tmp_filename) as fd:
                        commits = [
                            commit for commit in g.parse_log(fd, max_diff_size=1024)
                        ]
                finally:
                    rm(tmp_filename)

                with open(self.changelog_file, "w") as fd:
                    json.dump(commits, fd)
                # We have removed local changes or updated the git repository
                result = ReturnValue.success
            else:
                result = ReturnValue.success

        except GitError:
            logger.exception("Error during git update %s" % self.name)
            result = ReturnValue.failure
        return result, old_commit, new_commit

    def update_svn(self, url, revision):
        """Update working dir using a SVN repository.

        :param url: git repository url
        :type url: str
        :param revision: git revision
        :type revision: str
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
                    "Unable to get SVN informations form the %s " "working dir",
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
                    "Repository %s was locally modified," " clean done.", self.name
                )
            if old_commit == new_commit:
                result = ReturnValue.unchanged
            else:
                result = ReturnValue.success
        return result, old_commit, new_commit
