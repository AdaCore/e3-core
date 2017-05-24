from __future__ import absolute_import, division, print_function

import os

from e3.anod.action import Build
from e3.anod.context import AnodContext, SchedulingError
from e3.anod.error import AnodError
from e3.anod.loader import AnodSpecRepository
from e3.env import BaseEnv

import pytest


class TestContext(object):

    spec_dir = os.path.join(os.path.dirname(__file__), 'context_data')

    def create_context(self):
        # Create a context for a x86-linux machine
        asr = AnodSpecRepository(self.spec_dir)
        asr.repos['spec1-git'] = 'spec1-git'
        asr.repos['spec8-git'] = 'spec8-git'
        asr.repos['spec2-git'] = 'spec2-git'
        env = BaseEnv()
        env.set_build('x86-linux', 'rhes6', 'mylinux')
        ac = AnodContext(asr, default_env=env)
        return ac

    def test_context_init(self):
        # Create a context using:
        # 1. the local default configuration
        # 2. forcing a x86-linux configuration
        asr = AnodSpecRepository(self.spec_dir)
        ac = AnodContext(asr)
        assert ac.default_env.build == BaseEnv().build
        assert ac.default_env.host == BaseEnv().host
        assert ac.default_env.target == BaseEnv().target
        self.create_context()

    def test_load(self):
        # Load a simple build specification that declares a single source
        ac = self.create_context()
        ac.load('spec1', env=ac.default_env, qualifier='', kind='build')

        # Load it a second time should use the cache data
        ac.load('spec1', env=None, qualifier='', kind='build')

        # One source should have been registered
        assert len(ac.sources) == 1 and 'spec1-src' in ac.sources, \
            'spec1-src source from spec1.anod has not been registered'

        # One spec instance should have been registered in the cache
        assert len(ac.cache) == 1, \
            'caching of anod instances broken'

    def test_add_anod_action(self):
        # Load spec1 with build primitive
        ac = self.create_context()
        node = ac.add_anod_action('spec1', primitive='build')
        # ??? spec1 does not have a build primitive ???
        # ??? should we consider a default build primitive exist or no ???

        # spec1 is a simple spec we expect only 2 nodes root and build node
        assert len(ac.tree) == 2, ac.tree.as_dot()
        assert isinstance(node, Build)
        assert set(ac.tree.vertex_data.keys()) == \
            set(('root', 'mylinux.x86-linux.spec1.build'))

        # the result should be schedulable
        result = ac.schedule(ac.always_download_source_resolver)
        assert len(result) == 2, result.as_dot()
        assert set(result.vertex_data.keys()) == \
            set(('root', 'mylinux.x86-linux.spec1.build'))

    def test_add_anod_action2(self):
        # Simple spec with sources associated to the build primitive
        ac = self.create_context()
        ac.add_anod_action('spec2', primitive='build')
        assert len(ac.tree) == 8, ac.tree.as_dot()

        result = ac.schedule(ac.always_download_source_resolver)
        assert len(result) == 5, result.as_dot()
        assert set(result.vertex_data.keys()) == \
            set(('root',
                 'mylinux.x86-linux.spec2.build',
                 'source_get.spec2-src',
                 'mylinux.x86-linux.spec2.source_install.spec2-src',
                 'download.spec2-src'))

    def test_add_anod_action3(self):
        # Simple spec with both install and build primitive and a package
        # declared
        ac = self.create_context()
        ac.add_anod_action('spec3', primitive='build')
        assert len(ac.tree) == 5, ac.tree.as_dot()
        result = ac.schedule(ac.always_download_source_resolver)
        assert len(result) == 3, result.as_dot()
        assert set(result.vertex_data.keys()) == \
            set(('root',
                 'mylinux.x86-linux.spec3.build',
                 'mylinux.x86-linux.spec3.install'))

    def test_add_anod_action4(self):
        # Simple spec with:
        #   install primitive, package, component
        #   build primitive
        ac = self.create_context()
        ac.add_anod_action('spec4', primitive='build')
        assert len(ac.tree) == 6, ac.tree.as_dot()
        result = ac.schedule(ac.always_download_source_resolver)
        assert len(result) == 4, result.as_dot()
        assert set(result.vertex_data.keys()) == \
            set(('root',
                 'mylinux.x86-linux.spec4.build',
                 'mylinux.x86-linux.spec4.install',
                 'mylinux.x86-linux.spec4.upload_bin'))

    def test_add_anod_action4_2(self):
        # Same previous example but calling install primitive instead of build
        ac = self.create_context()
        ac.add_anod_action('spec4', primitive='install')
        assert len(ac.tree) == 5, ac.tree.as_dot()
        result = ac.schedule(ac.always_download_source_resolver)
        assert len(result) == 3, result.as_dot()
        assert set(result.vertex_data.keys()) == \
            set(('root',
                 'mylinux.x86-linux.spec4.download_bin',
                 'mylinux.x86-linux.spec4.install'))

    def test_add_anod_action4_3(self):
        # Same as previous example but calling test primitive
        ac = self.create_context()
        ac.add_anod_action('spec4', primitive='test')
        assert len(ac.tree) == 2, ac.tree.as_dot()
        result = ac.schedule(ac.always_download_source_resolver)
        assert len(result) == 2, result.as_dot()
        assert set(result.vertex_data.keys()) == \
            set(('root',
                 'mylinux.x86-linux.spec4.test'))

    def test_add_anod_action5(self):
        # Case in which a source component should be uploaded (i.e: no binary
        # package declared)
        ac = self.create_context()
        ac.add_anod_action('spec5', primitive='build')
        assert len(ac.tree) == 3, ac.tree.as_dot()
        result = ac.schedule(ac.always_download_source_resolver)
        assert len(result) == 3, result.as_dot()
        assert set(result.vertex_data.keys()) == \
            set(('root',
                 'mylinux.x86-linux.spec5.build',
                 'mylinux.x86-linux.spec5.upload_bin'))

    def test_add_anod_action6(self):
        # Calling install on a spec without install primitive result in a build
        # ??? should we allow that ???
        ac = self.create_context()
        ac.add_anod_action('spec6', primitive='install')
        assert len(ac.tree) == 2, ac.tree.as_dot()
        result = ac.schedule(ac.always_download_source_resolver)
        assert len(result) == 2, result.as_dot()
        assert set(result.vertex_data.keys()) == \
            set(('root',
                 'mylinux.x86-linux.spec6.build'))

    def test_add_anod_action6_2(self):
        # Same as previous example. Just ensure that if the spec is called
        # twice with different qualifiers that have no effect on build space
        # name then the result is only one install. (and thus qualifier value
        # for that node won't be deterministic.
        # ??? Should we raise issues on such cases ???
        ac = self.create_context()
        ac.add_anod_action('spec6', primitive='install')
        ac.add_anod_action('spec6', primitive='install', qualifier='myqualif')
        assert len(ac.tree) == 2, ac.tree.as_dot()
        result = ac.schedule(ac.always_download_source_resolver)
        assert len(result) == 2, result.as_dot()
        assert set(result.vertex_data.keys()) == \
            set(('root',
                 'mylinux.x86-linux.spec6.build'))

    def test_add_anod_action7(self):
        # Ensure that build_deps = None is accepted
        ac = self.create_context()
        ac.add_anod_action('spec7', primitive='build')
        result = ac.schedule(ac.always_download_source_resolver)
        assert len(result) == 2, result.as_dot()
        assert set(result.vertex_data.keys()) == \
            set(('root',
                 'mylinux.x86-linux.spec7.build'))

    def test_add_anod_action8(self):
        """Simple spec with source that does not exist."""
        ac = self.create_context()
        with pytest.raises(AnodError):
            ac.add_anod_action('spec8', primitive='build')

    def test_add_anod_action9(self):
        """Test source dependency."""
        ac = self.create_context()
        ac.add_anod_action('spec9', primitive='build')
        result = ac.schedule(ac.always_download_source_resolver)
        assert 'download.spec2-src' in result.vertex_data.keys()

    def test_add_anod_action10(self):
        """Verify that requiring both build and install fails."""
        ac = self.create_context()
        ac.add_anod_action('spec3', primitive='install')
        ac.add_anod_action('spec3', primitive='build')

        with pytest.raises(SchedulingError):
            ac.schedule(ac.always_download_source_resolver)
