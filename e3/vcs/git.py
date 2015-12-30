"""High-Level interface to Git repository

Example::


    g = GitRepository(working_tree='/tmp/e3-core')
    g.update('ssh://git.adacore.com/anod', refspec='master', force=True)
    with open('/tmp/e3-core-log', 'w') as fd:
        g.write_log(fd, max_count=10)
    with open('/tmp/e3-core-log') as fd:
        authors = []
        for commit in g.parse_log(fd, max_diff_size=1024):
            authors.append(commit['email'])
"""

from __future__ import absolute_import
from subprocess import PIPE
import sys
import tempfile
import e3.error
import e3.fs
import e3.log
import e3.os.process

logger = e3.log.getLogger('vcs.git')

HEAD = 'HEAD'
FETCH_HEAD = 'FETCH_HEAD'


# Implementation note: some git commands can produce a big amount of data (e.g.
# git diff or git log). We always redirect git command result to a file then
# parse it, limiting the size of data read to avoid crashing our program.


class GitError(e3.error.E3Error):
    def __init__(self, message, origin, process=None):
        super(GitError, self).__init__(message, origin)
        self.origin = origin
        self.message = message
        self.process = process


class GitRepository(object):
    """Interface to a Git Repository.

    :cvar git: path to the git binary
    :cvar log_stream: stream where the log commands will be redirected
        (default is stdout)
    :ivar working_tree: path to the git working tree
    """
    git = None
    log_stream = sys.stdout

    def __init__(self, working_tree):
        """Initialize a GitRepository object.

        :param working_tree: working tree of the GitRepository
        :type working_tree: str
        """
        self.working_tree = working_tree

    def git_cmd(self, cmd, **kwargs):
        """Run a git command.

        :param cmd: the command line as a list of string, all None entries will
            be discarded
        :type cmd: list[str | None]
        :param kwargs: additional parameters to provide to e3.os.process.Run
        :type kwargs: dict
        """
        if self.__class__.git is None:
            git_binary = e3.os.process.which('git', default=None)
            if git_binary is None:
                raise GitError('cannot find git', 'git_cmd')
            self.__class__.git = git_binary

        if 'output' not in kwargs:
            kwargs['output'] = self.log_stream

        p_cmd = [arg for arg in cmd if arg is not None]
        p_cmd.insert(0, self.__class__.git)

        p = e3.os.process.Run(p_cmd, cwd=self.working_tree, **kwargs)
        if p.status != 0:
            raise GitError('%s failed (exit status: %d)' %
                           (e3.os.process.command_line_image(p_cmd), p.status),
                           origin='git_cmd', process=p)
        return p

    def init(self, url=None, remote='origin'):
        """Initialize a new Git repository and configure the remote.

        :param url: url of the remote repository, if None create a local git
            repository
        :type url: str | None
        :param remote: name of the remote to create
        :type remote: str
        :raise: GitError
        """
        e3.fs.mkdir(self.working_tree)
        self.git_cmd(['init'])
        if url is not None:
            self.git_cmd(['remote', 'add', remote, url])

    def checkout(self, branch, force=False):
        """Checkout a given refspec.

        :param branch: name of the branch to checkout
        :type branch: str
        :param force: throw away local changes if needed
        :type force: bool
        :raise: GitError
        """
        cmd = ['checkout', '-q', '-f' if force else None, branch]
        self.git_cmd(cmd)

    def describe(self, commit=HEAD):
        """Get a human friendly revision for the given refspec.

        :param commit: commit object to describe.
        :type commit: str
        :return: the most recent tag name with the number of additional commits
            on top of the tagged object and the abbreviated object name of the
            most recent commit (see `git help describe`).
        :rtype: str
        :raise: GitError
        """
        p = self.git_cmd(['describe', '--always', commit], output=PIPE)
        return p.out.strip()

    def write_diff(self, stream, commit=HEAD):
        """Write local changes in the working tree in stream.

        :param commit: write the diff between the first parent of `commit` and
            `cammit`.
        :type commit: str
        :param stream: an open file descriptor
        :type stream: file
        :rtype: str
        :raise: GitError
        """
        cmd = ['--no-pager', 'diff', '%s^!' % commit]
        self.git_cmd(cmd, output=stream, error=PIPE)

    def fetch(self, url, refspec=None):
        """Fetch remote changes.

        :param url: url of the remote repository
        :type url: str
        :param refspec: specifies which refs to fetch and which local refs to
            update.
        :type refspec: str | None
        :raise: GitError
        """
        self.git_cmd(['fetch', url, refspec])

    def update(self, url, refspec, force=False):
        """Fetch remote changes and checkout FETCH_HEAD.

        :param url: url of the remote repository
        :type url: str
        :param refspec: specifies which refs to fetch and which local refs to
            update.
        :type refspec: str
        :param force: throw away local changes if needed
        :type force: bool
        :raise: GitError
        """
        self.fetch(url, refspec)
        self.checkout('FETCH_HEAD', force=force)

    def write_log(self, stream, max_count=50):
        """Write formatted log to a stream.

        :param stream: an open stream where to write the log content
        :type stream: file
        :param max_count: max number of commit to display
        :type max_count: int
        :raise: GitError
        """
        cmd = ['log', '--format=format:%H %ae %cI%n%B',
               '--log-size',
               '--max-count=%d' % max_count if max_count else None]
        self.git_cmd(cmd, output=stream)

    def parse_log(self, stream, max_diff_size=0):
        """Parse a log stream generated with `write_log`.

        :param stream: stream to read
        :type stream: file
        :param max_diff_size: max size of a diff, if <= 0 diff are ignored
        :type max_diff_size: int
        :return: a generator returning commit information (directories with
            the following keys: sha, email, date, message, diff). Note that
            the key diff is only set when max_diff_size is bigger than 0.
        :rtype: collections.Iterable[dict[str][str]]
       """

        def to_commit(object_content):
            """Return commit information.

            :type object_content: str
            """
            sha, email, date, msg = object_content.split(None, 3)
            result = {
                'sha': sha,
                'email': email,
                'date': date,
                'message': msg}

            if max_diff_size > 0:
                diff_fd = tempfile.NamedTemporaryFile()
                self.write_diff(diff_fd, sha)
                diff_size = diff_fd.tell()
                diff_fd.seek(0)
                result['diff'] = diff_fd.read(max_diff_size)
                if diff_size > max_diff_size:
                    result['diff'] += '\n... diff too long ...\n'
            return result

        size_to_read = 0
        while True:
            line = stream.readline()
            if not line.strip():
                # Strip empty line separating two commits
                line = stream.readline()
            if line.startswith('log size '):
                size_to_read = int(line.rsplit(None, 1)[1])
                # Get commit info
            if size_to_read <= 0:
                return
            yield to_commit(stream.read(size_to_read))
            size_to_read = 0

    def rev_parse(self, refspec=HEAD):
        """Get the sha associated to a given refspec.

        :param refspec: refspec.
        :type refspec: str
        :rtype: str
        :raise: GitError
        """
        p = self.git_cmd(['rev-parse', '--revs-only', refspec],
                         output=PIPE,
                         error=PIPE)
        return p.out.strip()
