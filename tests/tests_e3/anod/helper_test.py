from __future__ import absolute_import

import tempfile

from e3.anod.helper import Make, Configure
from e3.anod.sandbox import SandBox
from e3.anod.spec import Anod
import e3.fs


def test_make():
    tempd = tempfile.mkdtemp()

    class AnodMake(Anod):

        @Anod.primitive()
        def build(self):
            m = Make(self)
            return m.cmdline()

    try:
        Anod.sandbox = SandBox()
        Anod.sandbox.root_dir = tempd
        Anod.sandbox.create_dirs()

        am = AnodMake('qual', 'build', jobs=10)
        am.activate()
        am.build_space.create()
        assert am.build()['cmd'] == ['make', '-j', '10']

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

        ac = AnodConf('qual', 'build', jobs=10)
        ac.activate()
        ac.build_space.create()
        assert ac.build()['cmd'] == [
            '../src/configure', '--build=%s' % ac.env.build.triplet]

    finally:
        e3.fs.rm(tempd, True)
