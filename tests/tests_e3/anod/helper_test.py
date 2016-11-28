from __future__ import absolute_import, division, print_function

import os

from e3.anod.driver import AnodDriver
from e3.anod.helper import Configure, Make, text_replace
from e3.anod.sandbox import SandBox
from e3.anod.spec import Anod


def test_make():

    class AnodMake(Anod):

        @Anod.primitive()
        def build(self):
            m1 = Make(self, makefile='/tmp/makefile')
            m1.set_var('prefix', '/foo')
            m2 = Make(self, jobs=2)
            return (m1.cmdline()['cmd'],
                    m2.cmdline(['clean', 'install'])['cmd'],
                    m2.cmdline('all')['cmd'])

    Anod.sandbox = SandBox()
    Anod.sandbox.root_dir = os.getcwd()
    Anod.sandbox.create_dirs()

    am = AnodMake(qualifier='', kind='build', jobs=10)
    AnodDriver(anod_instance=am, store=None).activate()
    am.build_space.create()
    assert am.build() == (
        ['make', '-f', '/tmp/makefile', '-j', '10', 'prefix=/foo'],
        ['make', '-j', '2', 'clean', 'install'],
        ['make', '-j', '2', 'all'])


def test_configure():

    class AnodConf(Anod):

        @Anod.primitive()
        def build(self):
            c = Configure(self)
            return c.cmdline()

    Anod.sandbox = SandBox()
    Anod.sandbox.root_dir = os.getcwd()
    Anod.sandbox.create_dirs()

    ac = AnodConf(qualifier='', kind='build', jobs=10)
    AnodDriver(anod_instance=ac, store=None).activate()
    ac.build_space.create()

    # Configure() can add $CONFIG_SHELL in the command line
    # Check that the two other arguments are as expected
    assert ac.build()['cmd'][-2:] == [
        '../src/configure', '--build=%s' % ac.env.build.triplet]


def test_text_replace():
    with open('myfile', 'w') as f:
        f.write('what who when')
    text_replace('myfile', [(b'who', b'replaced')])
    with open('myfile') as f:
        assert f.read() == 'what replaced when'
