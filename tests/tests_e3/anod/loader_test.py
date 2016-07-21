from __future__ import absolute_import
from __future__ import print_function

import e3.anod.loader
from e3.anod.loader import spec
from e3.anod.error import SandBoxError
from e3.anod.sandbox import SandBox

import e3.fs

import os
import pytest


class TestLoader(object):

    def test_spec_does_not_exist(self):
        e3.anod.loader.sandbox = SandBox()
        e3.anod.loader.sandbox.spec_dir = '/foo/bar'
        with pytest.raises(SandBoxError) as err:
            spec('/does/not/exist')
        assert str(err.value).startswith(
            'load: the spec /does/not/exist.anod does not exist')

    def test_spec_loader1(self):
        e3.anod.loader.sandbox = SandBox()
        e3.anod.loader.sandbox.spec_dir = os.path.join(
            os.path.dirname(__file__),
            'data')

        s = spec('loader1')
        assert s.name == 'loader1'
        assert s.sandbox == e3.anod.loader.sandbox

    def test_spec_loader2(self):
        e3.anod.loader.sandbox = SandBox()
        e3.anod.loader.sandbox.spec_dir = os.path.join(
            os.path.dirname(__file__),
            'data')

        with pytest.raises(SandBoxError) as err:
            spec('loader2')
        assert str(err.value).startswith(
            'load: cannot find Anod subclass in')
