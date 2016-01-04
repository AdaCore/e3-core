from __future__ import absolute_import

import os
import tempfile

import e3.fs
import e3.os.process


def test_deploy_sandbox():
    tempd = tempfile.mkdtemp(suffix='pytest-e3-core')
    e3.os.process.Run(
        ['e3-sandbox', 'create', tempd])
    assert os.path.isdir(os.path.join(
        tempd, 'log'))

    assert 'sandbox = %s' % tempd in e3.os.process.Run(
        ['e3-sandbox', 'show-config', tempd]).out

    e3.fs.mkdir(os.path.join(tempd, 'specs'))

    with open(os.path.join(tempd, 'specs', 'a.anod'), 'w') as fd:
        fd.write('from e3.anod.spec import Anod\n')
        fd.write('class A(Anod):\n')
        fd.write('    pass\n')

    assert 'no primitive download' in e3.os.process.Run(
        [os.path.join(tempd, 'bin', 'anod'),
         'download', 'a']).out
