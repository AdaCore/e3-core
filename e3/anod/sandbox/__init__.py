from __future__ import absolute_import
from __future__ import print_function

from pkg_resources import get_distribution

from e3.env import Env
from e3.fs import mkdir, rm

import e3.error
import e3.log
import e3.os.process

import os
import sys
import yaml

from e3.os.fs import chmod
from e3.anod.buildspace import BuildSpace

logger = e3.log.getLogger('sandbox')


class SandBoxError(e3.error.E3Error):
    pass


class SandBox(object):

    def __init__(self):
        self.__root_dir = None
        self.build_id = None
        self.build_date = None
        self.build_version = None

        # Required directories for a sandbox
        self.dirs = ('meta', 'bin', 'tmp', os.path.join('tmp', 'cache'),
                     'src', 'log', 'etc', 'vcs', 'patch')

        self.spec_dir = None
        self.meta_dir = None
        self.tmp_dir = None
        self.tmp_cache_dir = None
        self.src_dir = None
        self.log_dir = None
        self.etc_dir = None
        self.vcs_dir = None
        self.patch_dir = None
        self.bin_dir = None
        self.conf = None

    @property
    def root_dir(self):
        """Root path of the sandbox.

        :raise SandBoxError: when the sandbox is not initialized
        :rtype: str
        """
        if self.__root_dir is None:
            raise SandBoxError(
                origin='root_dir',
                message='sandbox not loaded. Please call load()')
        return self.__root_dir

    @root_dir.setter
    def root_dir(self, d):
        new_dir = os.path.realpath(d)
        if new_dir == self.__root_dir:
            return  # nothing to do

        self.__root_dir = new_dir

        self.spec_dir = os.path.join(new_dir, 'specs')

        # For each directory create an attribute containing its path
        for d in self.dirs:
            setattr(self, ('%s_dir' % d).replace(os.path.sep, '_'),
                    os.path.join(self.root_dir, d))

    def create_dirs(self):
        """Create all required sandbox directories."""
        for d in self.dirs:
            mkdir(getattr(self, ('%s_dir' % d).replace(os.path.sep, '_')))

    def get_build_space(self, name, primitive, platform=None):
        """Get build space.

        :param name: build space name
        :type name: str
        :param primitive: the primitive name (e.g. build, install...)
        :type primitive: str
        :param platform: platform name (if None use the default platform)
        :type platform: str | None

        :return: A BuildSpace object
        :rtype: BuildSpace
        """
        if platform is None:
            platform = Env().platform
        return BuildSpace(
            root_dir=os.path.join(self.root_dir, platform, name),
            primitive=primitive)

    def dump_configuration(self):
        # Compute command line for call to e3-sandbox create. Ensure that the
        # paths are made absolute (path to sandbox, script).
        cmd_line = [sys.executable, os.path.abspath(__file__)]
        cmd_line += sys.argv[1:]
        sandbox_conf = os.path.join(self.meta_dir, "sandbox.yaml")
        with open(sandbox_conf, 'wb') as f:
            yaml.dump({'cmd_line': cmd_line}, f, encoding='utf-8')

    def get_configuration(self):
        sandbox_conf = os.path.join(self.meta_dir, "sandbox.yaml")
        with open(sandbox_conf, 'rb') as f:
            return yaml.load(f)

    def write_scripts(self):
        from setuptools.command.easy_install import get_script_args

        # Retrieve sandbox_scripts entry points
        e3_distrib = get_distribution('e3-core')

        class SandboxDist(object):
            def get_entry_map(self, group):
                if group != 'console_scripts':
                    return {}
                return e3_distrib.get_entry_map('sandbox_scripts')

            def as_requirement(self):
                return e3_distrib.as_requirement()

        for script in get_script_args(dist=SandboxDist()):
            script_name = script[0]
            script_content = script[1]
            target = os.path.join(self.bin_dir, script_name)
            rm(target)
            if not script_name.endswith('.exe'):
                script_content = script_content.replace(
                    'console_scripts', 'sandbox_scripts')
            with open(target, 'wb') as f:
                if isinstance(script_content, unicode):
                    f.write(script_content.encode('utf-8'))
                else:
                    f.write(script_content)
            chmod('a+x', target)
