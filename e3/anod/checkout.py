from __future__ import absolute_import, division, print_function

import hashlib
import json
import os
from subprocess import PIPE

import e3.log
from e3.anod.status import ReturnValue
from e3.fs import rm
from e3.vcs.git import GitRepository, GitError
from e3.vcs.svn import SVNRepository, SVNError

logger = e3.log.getLogger('e3.anod.checkout')


class CheckoutManager(object):
    """Helper class to manage checkouts done by Anod tools."""

    def __init__(self, name, working_dir):
        """Initialize CheckoutManager instance.

        :param name: a symbolic name for that checkout
        :type name: str
        :param working_dir: working directory in which checkouts are
            performed. Note that the checkout will be done in the
            ```name``` subdirectory.
        :type working_dir: str
        """
        self.name = name
        self.working_dir = os.path.abspath(
            os.path.join(working_dir, self.name))
        self.metadata_file = self.working_dir + '_checkout.json'
        self.checksum_file = self.working_dir + '_checkout.checksums'

    def update_fingerprint(self, fingerprint, is_prediction=False):
        """Given a fingerprint amend it with metadata of the current checkout.

        :param fingerprint: initial fingerprint
        :type fingerprint: Fingerprint
        :param is_prediction: if True this is an attempt to compute the
            fingerprint before doing an update. For a checkout the returned
            value in that case is always the None.
            See e3.job.walk.compute_fingerprint for more information.
        :type is_prediction: bool
        :return: a fingerprint
        :rtype: None | Fingerprint
        """
        if is_prediction:
            return None

        try:
            if os.path.isfile(self.checksum_file):
                with open(self.checksum_file) as fd:
                    checksums = json.load(fd)
                for path, checksum in checksums.items():
                    fingerprint.add(
                        "file.%s" % path,
                        checksum)
            else:
                with open(self.metadata_file) as fd:
                    vcs_info = json.load(fd)
                fingerprint.add(
                    self.name, (vcs_info['url'],
                                vcs_info['new_commit']))
            return fingerprint
        except Exception:
            logger.exception(
                'Got exception while trying to compute fingerprints')
            return None

    def update(self, vcs, url, revision=None):
        """Update content of the working directory.

        :param vcs: vcd kind
        :type vcs: str
        :param url: repository url
        :type url: str
        :param revision: revision
        :type revision: str | None
        """
        # Reset metadata and checksum list
        if os.path.isfile(self.metadata_file):
            rm(self.metadata_file)
        if os.path.isfile(self.checksum_file):
            rm(self.checksum_file)
        if vcs == 'git':
            update = self.update_git
        elif vcs == 'svn':
            update = self.update_svn
        else:
            logger.error('Invalid repository type: %s' % vcs)
            return ReturnValue.failure

        result, old_commit, new_commit = update(url=url, revision=revision)

        with open(self.metadata_file, 'w') as fd:
            json.dump(
                {'name': self.name,
                 'url': url,
                 'old_commit': old_commit,
                 'new_commit': new_commit,
                 'revision': revision}, fd)
        return result

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
        if isinstance(url, unicode):
            remote_name = hashlib.sha256(url.encode('utf-8')).hexdigest()
        else:
            remote_name = hashlib.sha256(url).hexdigest()
        g.init()

        # Do the remote addition manually as in that context we can ignore
        # safely any error returned by this command.
        try:
            g.git_cmd(['remote', 'add', remote_name, url])
        except Exception:
            # Ignore exception as it probably means that remote already exist
            # In case of real error the failure will be detected later.
            pass

        try:
            old_commit = g.rev_parse()

            # Using fetch + checkout ensure caching is effective
            g.git_cmd(['fetch', '-f', remote_name,
                       '%s:refs/e3-checkout' % revision])
            g.checkout("refs/e3-checkout", force=True)
            new_commit = g.rev_parse()

            # Verify that there is no local change
            p = g.git_cmd(['status', '--porcelain'], output=PIPE)
            if p.out:
                logger.error('Repository %s is locally modified, saving '
                             'diff in stash\n%s', self.name, p.out)
                g.git_cmd(['stash', 'save', '-u'])

            # Create a file with all the file checksums
            with open(self.checksum_file, 'w') as fd:
                json.dump(g.file_checksums(), fd)

            if old_commit == new_commit:
                result = ReturnValue.unchanged
            else:
                # We have removed local changes or updated the git repository
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
                logger.error('Unable to get SVN informations form the %s '
                             'working dir', self.name)
        try:
            # Remove local change and update the working copy
            local_change_detected = working_copy.update(
                url=url, revision=revision, force_and_clean=True)
        except SVNError:  # impossible to update, potential local changes
            logger.error('Impossible to update the working copy of %s',
                         self.name)
            result = ReturnValue.failure
        else:
            new_commit = working_copy.current_revision
            if local_change_detected:
                logger.error('Repository %s was locally modified,'
                             ' clean done.', self.name)
            if old_commit == new_commit:
                result = ReturnValue.unchanged
            else:
                result = ReturnValue.success
        return result, old_commit, new_commit
