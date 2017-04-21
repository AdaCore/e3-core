from __future__ import absolute_import, division, print_function

import os

import e3.anod.sandbox
import e3.env
import e3.fs
import e3.os.process


def test_deploy_sandbox():
    sandbox_dir = os.getcwd()
    p = e3.os.process.Run(
        ['e3-sandbox', '-vv', 'create', sandbox_dir])
    assert p.status == 0, p.out
    assert os.path.isdir('log')

    assert 'sandbox = %s' % sandbox_dir in e3.os.process.Run(
        ['e3-sandbox', 'show-config', sandbox_dir]).out

    e3.fs.mkdir('specs')

    with open(os.path.join('specs', 'a.anod'), 'w') as fd:
        fd.write('from e3.anod.spec import Anod\n')
        fd.write('class A(Anod):\n')
        fd.write('    pass\n')

    assert 'no primitive download' in e3.os.process.Run(
        [os.path.join('bin', 'anod'),
         'download', 'a']).out

    with open(os.path.join('specs', 'b.anod'), 'w') as fd:
        fd.write('from e3.anod.spec import Anod\n')
        fd.write('class B(Anod):\n\n')
        fd.write('    @Anod.primitive()\n')
        fd.write('    def download(self):\n')
        fd.write('        pass\n')

    assert 'cannot get resource metadata from store' in e3.os.process.Run(
        [os.path.join('bin', 'anod'),
         'download', 'b']).out


def test_sandbox_env():
    os.environ['GPR_PROJECT_PATH'] = '/foo'
    sandbox = e3.anod.sandbox.SandBox()
    sandbox.set_default_env()
    assert os.environ['GPR_PROJECT_PATH'] == ''
