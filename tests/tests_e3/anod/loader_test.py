from __future__ import absolute_import

import e3.anod.loader
from e3.anod.loader import spec
from e3.anod.error import SandBoxError
from e3.anod.sandbox import SandBox

import os
import pytest
import tempfile


class TestLoader(object):

    def test_spec_does_not_exist(self):
        e3.anod.loader.sandbox = SandBox()
        e3.anod.loader.sandbox.spec_dir = '/foo/bar'
        with pytest.raises(SandBoxError) as err:
            spec('/does/not/exist')
            assert err.value.message.startswith(
                'the spec /does/not/exist does not exist')

    def test_spec_without_anod(self):
        anod_file = tempfile.NamedTemporaryFile(delete=False)
        try:
            anod_file.write(b'import os\n')
            e3.anod.loader.sandbox = SandBox()
            e3.anod.loader.sandbox.spec_dir = os.path.dirname(anod_file.name)

            with pytest.raises(SandBoxError) as err:
                spec('/does/not/exist')
                assert err.value.message.startswith(
                    'Cannot find Anod subclass in')
        finally:
            anod_file.close()

    def test_spec_loader1(self):
        e3.anod.loader.sandbox = SandBox()
        e3.anod.loader.sandbox.spec_dir = os.path.join(
            os.path.dirname(__file__),
            'data')

        s = spec('loader1')
        assert s.name == 'loader1'
        assert s.sandbox == e3.anod.loader.sandbox
