from __future__ import absolute_import, division, print_function

import os

import e3.anod.sandbox
import e3.env
import e3.fs
import e3.os.process


def test_deploy_sandbox():
    sandbox_dir = os.getcwd()
    e3.os.process.Run(
        ['e3-sandbox', '-v', '-v', 'create', sandbox_dir], output=None)
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


def test_SandBoxCreate_git():
    sandbox_dir = os.getcwd()
    specs_dir = os.path.join(os.path.dirname(__file__), 'specs')
    result = e3.os.process.Run(
        ['e3-sandbox', '-v',
         'create',
         '--spec-git-url', os.path.abspath(specs_dir),
         sandbox_dir], output=None)
    assert 'fatal' not in result.out


def test_sandbox_exec_missing():
    sandbox_dir = os.path.join(os.getcwd(), 'sbx')
    specs_dir = os.path.join(os.path.dirname(__file__), 'specs')
    e3.os.process.Run(
        ['e3-sandbox', 'create', sandbox_dir], output=None)

    no_specs = e3.os.process.Run(
                ['e3-sandbox', 'exec',
                 '--spec-dir', 'toto',
                 '--plan', 'toto', sandbox_dir])
    assert 'spec directory toto does not exist' in no_specs.out

    no_plan = e3.os.process.Run(
                ['e3-sandbox', 'exec',
                 '--spec-dir', specs_dir,
                 '--plan', 'toto', sandbox_dir])
    assert 'SandBoxExec.run: plan file toto does not exist' in no_plan.out


def test_sandbox_exec_success():
    sandbox_dir = os.path.join(os.getcwd(), 'sbx')
    specs_dir = os.path.join(os.path.dirname(__file__), 'specs')
    e3.os.process.Run(
        ['e3-sandbox', 'create', sandbox_dir], output=None)
    with open(os.path.join(sandbox_dir, 'test.plan'), 'w') as fd:
        fd.write("anod_build('e3')\n")
        fd.write("anod_test('e3')")
    # Test with local specs
    result = e3.os.process.Run(
                ['e3-sandbox', 'exec',
                 '--spec-dir', specs_dir,
                 '--plan', os.path.join(sandbox_dir, 'test.plan'),
                 sandbox_dir])
    assert 'root node' in result.out

    # Test with git module
    result = e3.os.process.Run(
                ['e3-sandbox', 'exec',
                 '--spec-git-url', os.path.abspath(specs_dir),
                 '--plan', os.path.join(sandbox_dir, 'test.plan'),
                 '--create-sandbox', 'sbxtoto'])
    print(result.out)
    assert 'root node' in result.out
