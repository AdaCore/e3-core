from __future__ import absolute_import, division, print_function

import os

import e3.error
import e3.log
import e3.os.process
from e3.fs import mkdir, rm

logger = e3.log.getLogger('buildspace')


class BuildSpace(object):
    """Build space located inside a sandbox."""

    DIRS = ('binary',
            'build',
            'install',
            'log',
            'pkg',
            'results',
            'src',
            'test',
            'tmp',
            'src')

    def __init__(self, root_dir):
        """Initialise a build space.

        :param root_dir: build space root dir
        :type root_dir: str
        """
        self.directory_mapping = {k: k for k in self.DIRS}
        self.root_dir = os.path.abspath(root_dir)
        self.initialized = False

    @property
    def dirs(self):
        return self.directory_mapping.values()

    def subdir(self, name):
        if name not in self.DIRS:
            raise ValueError('invalid subdir %s' % name)
        return os.path.join(self.root_dir, self.directory_mapping[name])

    def __getattr__(self, name):
        if name.endswith('_dir') and name[:-4] in self.DIRS:
            return self.subdir(name[:-4])
        raise AttributeError('unknown build space attribute: %s' % name)

    def __getitem__(self, key):
        if key.isupper() and key.endswith('_DIR'):
            return getattr(self, key.lower(), None)
        raise KeyError('invalid build space key: %s' % key)

    def create(self, quiet=False):
        """Create a build space.

        The function create all the necessary directories and files to have
        a valid build space. If the build space already exists, only tmp
        directory content is reset.

        :param quiet: do not print info messages
        :type quiet: bool
        """
        rm(self.tmp_dir, recursive=True)

        for d in self.DIRS:
            mkdir(self.subdir(name=d), quiet=quiet)

        self.initialized = True

    def reset(self, keep=None):
        """Reset build space.

        The function delete the complete buildspace. The only elements that
        are not deleted are the logs, the testsuite results and any
        subdirectories in keep parameter

        A call to self.create() is needed after calling this function.

        :param keep: a list of directory to keep in addition
            to results and log. Each element should be part of BuildSpace.DIRS
        :type keep: list[str] | None
        """
        keep = set(keep) if keep is not None else set()
        keep.update(('results', 'log'))

        dirs_to_reset = set(self.DIRS) - keep

        for d in dirs_to_reset:
            rm(self.subdir(name=d), recursive=True)
        self.initialized = False
