from __future__ import absolute_import, division, print_function

import os

from e3.anod.error import SandBoxError
from e3.anod.loader import AnodSpecRepository

import pytest


class TestLoader(object):

    spec_dir = os.path.join(os.path.dirname(__file__), 'data')
    spec2_dir = os.path.join(os.path.dirname(__file__), 'data2')

    def test_spec_does_not_exist(self):
        with pytest.raises(SandBoxError) as err:
            AnodSpecRepository('/foo/bar')

        assert str(err.value).startswith(
            'spec directory /foo/bar does not exist')

    def test_spec_loader1(self):
        spec_repo = AnodSpecRepository(self.spec_dir)
        s = spec_repo.load('loader1')
        assert s.name == 'loader1'

    def test_spec_loader2(self):
        spec_repo = AnodSpecRepository(self.spec_dir)

        with pytest.raises(SandBoxError) as err:
            spec_repo.load('loader2')
        assert str(err.value).startswith(
            'load: cannot find Anod subclass in')

    def test_invalid_spec(self):
        """Ensure that loading an invalid spec result in a SandboxError."""
        spec_repo = AnodSpecRepository(self.spec_dir)
        with pytest.raises(SandBoxError) as err:
            spec_repo.load('invalid_spec')

        assert 'invalid spec code' in str(err.value)

    def test_spec_loader_prolog(self):
        spec_repo = AnodSpecRepository(self.spec_dir, spec_config=True)
        anod_class = spec_repo.load('prolog_test')

        # We should be able to load a spec twice
        anod_class = spec_repo.load('prolog_test')

        anod_instance = anod_class('prolog_test', '', 'build')
        assert anod_instance.prolog_test, 'prolog not executed properly'

    def test_spec_inheritance(self):
        """Load a spec that inherit from another spec."""
        spec_repo = AnodSpecRepository(self.spec_dir)
        anod_class = spec_repo.load('child')
        anod_instance = anod_class('load', '', 'build')
        assert anod_instance.parent_info == 'from_parent'

    def test_multiple_spec_repository(self):
        """Ensure that spec function is context dependent."""
        spec_repo = AnodSpecRepository(self.spec_dir)
        spec2_repo = AnodSpecRepository(self.spec2_dir)
        anod_class = spec_repo.load('child')
        anod_instance = anod_class('load', '', 'build')
        assert anod_instance.parent_info == 'from_parent'
        anod_class2 = spec2_repo.load('child')
        anod_instance2 = anod_class2('load', '', 'build')
        assert anod_instance2.parent_info == 'from_parent2'

    def test_load_all(self):
        spec_repo = AnodSpecRepository(self.spec_dir)
        with pytest.raises(SandBoxError):
            spec_repo.load_all()

        spec_repo = AnodSpecRepository(self.spec2_dir)
        spec_repo.load_all()
        assert 'parent' in spec_repo
        assert 'child' in spec_repo
        assert 'unknown' not in spec_repo
