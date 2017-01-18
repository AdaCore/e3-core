from __future__ import absolute_import, division, print_function

import os

import pytest
from e3.anod.driver import AnodDriver
from e3.anod.error import AnodError
from e3.anod.sandbox import SandBox
from e3.anod.spec import Anod, has_primitive


def test_simple_spec():

    class Simple(Anod):

        test_qualifier_format = (
            ('with_bar', False),)

        build_source_list = [
            Anod.Source('foo-src', publish=False),
            Anod.Source('bar-src', publish=True)]

        @property
        def test_source_list(self):
            result = [Anod.Source('foo-test-src', publish=False)]
            if self.parsed_qualifier.get('with_bar'):
                result.append(
                    Anod.Source('bar-test-src', publish=False))
            return result

    simple_build = Simple('', kind='build')
    assert len(simple_build.build_source_list) == 2

    simple_test = Simple('', kind='test')
    assert len(simple_test.test_source_list) == 1

    simple_test_with_bar = Simple('with_bar=true', kind='test')
    assert len(simple_test_with_bar.test_source_list) == 2


def test_primitive():

    class NoPrimitive(Anod):

        def build(self):
            return 2

    no_primitive = NoPrimitive('', 'build')
    assert has_primitive(no_primitive, 'build') is False

    class WithPrimitive(Anod):

        build_qualifier_format = (
            ('error', False),)

        package = Anod.Package(prefix='mypackage', version=lambda: '42')

        @Anod.primitive()
        def build(self):
            if 'error' in self.parsed_qualifier:
                raise ValueError(self.parsed_qualifier['error'])
            return 3

    with_primitive = WithPrimitive('', 'build')
    with_primitive2 = WithPrimitive('error=foobar', 'build')

    Anod.sandbox = SandBox()
    Anod.sandbox.root_dir = os.getcwd()
    Anod.sandbox.spec_dir = os.path.join(
        os.path.dirname(__file__),
        'data')
    Anod.sandbox.create_dirs()
    # Activate the logging
    AnodDriver(anod_instance=with_primitive, store=None).activate()
    AnodDriver(anod_instance=with_primitive2, store=None).activate()

    with_primitive.build_space.create()

    assert has_primitive(with_primitive, 'build') is True
    assert with_primitive.build() == 3

    with_primitive2.build_space.create()

    with pytest.raises(AnodError) as err:
        with_primitive2.build()
    assert 'foobar' in str(err.value)

    assert with_primitive2.package.name.startswith('mypackage')
