"""High-Level interface to SVN repository.

Example::
    svn = SVNRepository(working_copy='/tmp/working_dir')
    svn.update(url='file:///path_to_local_repo', revision=1,
               force_and_clean=True)
"""

from __future__ import absolute_import, division, print_function

import os.path
import re
import sys
from subprocess import PIPE

import e3.log
import e3.os.fs
import e3.os.process
from e3.fs import mkdir, rm
from e3.vcs import VCSError

logger = e3.log.getLogger('vcs.svn')


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
            svn_binary = e3.os.process.which('svn', default=None)
            if svn_binary is None:  # defensive code
                raise SVNError('cannot find svn', 'svn_cmd')
            self.__class__.svn_bin = e3.os.fs.unixpath(svn_binary)

        if 'output' not in kwargs:
            kwargs['output'] = self.log_stream

        p_cmd = [arg for arg in cmd if arg is not None]
        p_cmd.insert(0, self.__class__.svn_bin)
        p_cmd.append('--non-interactive')

        p = e3.os.process.Run(p_cmd, cwd=self.working_copy, **kwargs)
        if p.status != 0:
            raise SVNError('%s failed (exit status: %d)' %
                           (e3.os.process.command_line_image(p_cmd), p.status),
                           origin='svn_cmd', process=p)
        return p

    def get_info(self, item):
        """Return a specific item shown by svn info.

        The --show-item option is only available from 1.9.
        :rtype: str
        :raise: SVNError
        """
        info = self.svn_cmd(['info'], output=PIPE).out
        m = re.search(r'^{item}: *(.*)\n'.format(item=item), info, flags=re.M)
        return m.group(1).strip()

    @property
    def url(self):
        """Return the last URL used for the checkout.

        :rtype: str
        :raise: SVNError
        """
        return self.get_info('URL')

    @property
    def current_revision(self):
        """Return the current revision.

        :rtype: str
        :raise: SVNError
        """
        return self.get_info('Last Changed Rev')

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
            if os.path.exists(os.path.join(dir_path, '.svn')):
                try:
                    status = self.svn_cmd(['status'], output=PIPE).out.strip()
                except SVNError:  # defensive code
                    return False, False
                if 'warning: W' in status:
                    return False, False
                return True, status == ''
            return False, False

        def is_empty_dir(dir_path):
            """Return True if the path is a directory and is empty."""
            return os.path.isdir(dir_path) and not os.listdir(dir_path)

        options = ['--ignore-externals']
        if revision:
            options += ['-r', revision]
        if force_and_clean:
            options += ['--force']

        is_svn_dir, is_clean = is_clean_svn_dir(self.working_copy)
        if is_svn_dir and (is_clean or not force_and_clean) and \
                (not url or self.url == url):
            self.svn_cmd(['update'] + options)
            return not is_clean
        if os.path.exists(self.working_copy):
            if not is_empty_dir(self.working_copy) and not force_and_clean:
                raise SVNError('not empty {}'.format(
                    self.working_copy, url), origin='update')
            if is_svn_dir and not url:
                url = self.url
            rm(self.working_copy, recursive=True)

        mkdir(self.working_copy)
        self.svn_cmd(['checkout', url, '.'] + options)
        return not is_clean
