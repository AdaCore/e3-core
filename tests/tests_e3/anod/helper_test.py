from __future__ import absolute_import

import tempfile

from e3.anod.driver import AnodDriver
from e3.anod.helper import Make, Configure, text_replace
from e3.anod.sandbox import SandBox
from e3.anod.spec import Anod
import e3.fs


def test_make():
    tempd = tempfile.mkdtemp()

    class AnodMake(Anod):

        @Anod.primitive()
        def build(self):
            m1 = Make(self, makefile='/tmp/makefile')
            m1.set_var('prefix', '/foo')
            m2 = Make(self, jobs=2)
            return (m1.cmdline()['cmd'],
                    m2.cmdline(['clean', 'install'])['cmd'],
                    m2.cmdline('all')['cmd'])

    try:
        Anod.sandbox = SandBox()
        Anod.sandbox.root_dir = tempd
        Anod.sandbox.create_dirs()

        am = AnodMake(qualifier='', kind='build', jobs=10)
        AnodDriver(anod_instance=am, store=None).activate()
        am.build_space.create()
        assert am.build() == (
            ['make', '-f', '/tmp/makefile', '-j', '10', 'prefix=/foo'],
            ['make', '-j', '2', 'clean', 'install'],
            ['make', '-j', '2', 'all'])

    finally:
        e3.fs.rm(tempd, True)


def test_configure():
    tempd = tempfile.mkdtemp()

    class AnodConf(Anod):

        @Anod.primitive()
        def build(self):
            c = Configure(self)
            return c.cmdline()

    try:
        Anod.sandbox = SandBox()
        Anod.sandbox.root_dir = tempd
        Anod.sandbox.create_dirs()

        ac = AnodConf(qualifier='', kind='build', jobs=10)
        AnodDriver(anod_instance=ac, store=None).activate()
        ac.build_space.create()
        assert ac.build()['cmd'] == [
            '../src/configure', '--build=%s' % ac.env.build.triplet]

    finally:
        e3.fs.rm(tempd, True)


def test_text_replace():
    tempf = tempfile.NamedTemporaryFile(delete=False)
    tempf.write('what who when')
    tempf.close()
    try:
        text_replace(tempf.name, [('who', 'replaced')])
        with open(tempf.name) as f:
            assert f.read() == 'what replaced when'
    finally:
        e3.fs.rm(tempf.name)
