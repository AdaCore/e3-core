from __future__ import absolute_import, division, print_function

import os

from e3.anod.error import SandBoxError
from e3.anod.loader import AnodSpecRepository

import pytest


class TestLoader(object):

    def test_spec_does_not_exist(self):
        with pytest.raises(SandBoxError) as err:
            AnodSpecRepository('/foo/bar')

        assert str(err.value).startswith(
            'spec directory /foo/bar does not exist')

    def test_spec_loader1(self):
        spec_dir = os.path.join(
            os.path.dirname(__file__),
            'data')

        spec_repo = AnodSpecRepository(spec_dir)
        s = spec_repo.load('loader1')
        assert s.name == 'loader1'

    def test_spec_loader2(self):
        spec_dir = os.path.join(
            os.path.dirname(__file__),
            'data')

        spec_repo = AnodSpecRepository(spec_dir)

        with pytest.raises(SandBoxError) as err:
            spec_repo.load('loader2')
        assert str(err.value).startswith(
            'load: cannot find Anod subclass in')
