from __future__ import absolute_import, division, print_function

import os

import e3.anod.sandbox
import e3.env
import e3.fs
import e3.os.process
import e3.platform
from e3.vcs.git import GitRepository

import pytest


PROLOG = r"""# prolog file loaded before all specs


def main():
    import yaml
    import os

    with open(os.path.join(
            __spec_repository.spec_dir, 'conf.yaml')) as f:
        conf = yaml.load(f)
        __spec_repository.api_version = conf['api_version']
        __spec_repository.repos = conf['repositories']


main()
del main
"""

E3Fake = r"""api_version: '1.4'
repositories:
    e3-fake-github:
        vcs: git
        url: %s
        revision: master
"""
E3FakeNoGit = r"""api_version: '1.4'
repositories:
    e3-fake-github:
        vcs: svn
        url: %s
        revision: master
"""


def create_prolog(prolog_dir):
    """Create prolog.py file on the fly to prevent checkstyle error."""
    if os.path.isfile(os.path.join(prolog_dir, 'prolog.py')):
        return
    with open(os.path.join(prolog_dir, 'prolog.py'), 'w') as f:
        f.write(PROLOG)


@pytest.fixture
def git_specs_dir(git, tmpdir):
    """Create a git repo to check out specs from it."""
    del git  # skip or fail when git is not installed

    # Create a e3-specs git repository for all tests in this module
    specs_dir = str(tmpdir.mkdir('e3-specs-git-repo'))

    try:
        specs_source_dir = os.path.join(os.path.dirname(__file__), 'specs')
        for spec_file in os.listdir(specs_source_dir):
            if os.path.isfile(os.path.join(specs_source_dir, spec_file)):
                e3.fs.cp(os.path.join(specs_source_dir, spec_file),
                         os.path.join(specs_dir, spec_file))
        # Put prolog file
        create_prolog(specs_dir)
        if os.path.isdir(os.path.join(specs_dir, '.git')):
            return
        g = GitRepository(specs_dir)
        g.init()
        g.git_cmd(['config', 'user.email', '"test@example.com"'])
        g.git_cmd(['config', 'user.name', '"test"'])
        g.git_cmd(['add', '-A'])
        g.git_cmd(['commit', '-m', "'add all'"])
        yield 'file://%s' % specs_dir.replace('\\', '/')
    finally:
        e3.fs.rm(specs_dir, True)


@pytest.fixture
def e3fake_git_dir(git, tmpdir):
    """Create a fake e3 git repo for the test suite."""
    del git  # skip or fail when git is not installed

    # Create a e3-fake git repository
    e3_fake_git_dir = str(tmpdir.mkdir('e3-fake-git-repo'))

    try:
        e3_fake_dir = os.path.join(os.path.dirname(__file__), 'e3-fake')
        for source_file in os.listdir(e3_fake_dir):
            if os.path.isfile(os.path.join(e3_fake_dir, source_file)):
                e3.fs.cp(os.path.join(e3_fake_dir, source_file),
                         os.path.join(e3_fake_git_dir, source_file))

        if os.path.isdir(os.path.join(e3_fake_git_dir, '.git')):
            return
        g = GitRepository(e3_fake_git_dir)
        g.init()
        g.git_cmd(['config', 'user.email', '"test@example.com"'])
        g.git_cmd(['config', 'user.name', '"test"'])
        g.git_cmd(['add', '-A'])
        g.git_cmd(['commit', '-m', "'add all'"])
        yield e3_fake_git_dir
    finally:
        e3.fs.rm(e3_fake_git_dir, True)


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


def test_sandbox_create_git(git_specs_dir):
    """Check if sandbox create can load the specs from a git repo."""
    root_dir = os.getcwd()
    sandbox_dir = os.path.join(root_dir, 'sbx')
    with_git = e3.os.process.Run(
        ['e3-sandbox', '-v',
         'create',
         '--spec-git-url', git_specs_dir,
         sandbox_dir], output=None)
    assert with_git.status == 0
    # Test structure
    for test_dir in ['bin', 'log', 'meta', 'patch',
                     'specs', 'src', 'tmp', 'vcs']:
                    assert os.path.isdir(os.path.join(sandbox_dir, test_dir))
    # Test specs files if created
    specs_files = ['anod.anod', 'e3.anod', 'python-virtualenv.anod',
                   'conf.yaml', 'prolog.py']
    for filename in specs_files:
        assert os.path.isfile(os.path.join(sandbox_dir, 'specs', filename))


def test_sandbox_exec_missing_spec_dir(git_specs_dir):
    """Test sandbox exec exception.

    - Check if sandbox exec raises exception if spec-dir is missing
    """
    root_dir = os.getcwd()
    sandbox_dir = os.path.join(root_dir, 'sbx')

    e3.os.process.Run(['e3-sandbox', 'create', sandbox_dir], output=None)

    # Specs dir is missing
    no_specs = e3.os.process.Run(['e3-sandbox', 'exec',
                                  '--spec-dir', 'nospecs',
                                  '--plan',
                                  'noplan', sandbox_dir])
    assert no_specs.status != 0
    assert 'spec directory nospecs does not exist' in no_specs.out


def test_sandbox_exec_missing_plan_file(git_specs_dir):
    """Test sandbox exec exception.

    - Check if sandbox exec raises exception if plan file is missing
    """
    root_dir = os.getcwd()
    sandbox_dir = os.path.join(root_dir, 'sbx')

    e3.os.process.Run(['e3-sandbox', 'create', sandbox_dir], output=None)

    # Plan file is missing
    no_plan = e3.os.process.Run(['e3-sandbox', 'exec',
                                 '--spec-git-url', git_specs_dir,
                                 '--plan', 'noplan',
                                 '--create-sandbox',
                                 sandbox_dir])
    assert no_plan.status != 0
    assert 'SandBoxExec.run: plan file noplan does not exist' in no_plan.out


def test_sandbox_exec_success(git_specs_dir):
    """Test if sandbox exec works with local specs and a git repo."""
    root_dir = os.getcwd()
    sandbox_dir = os.path.join(root_dir, 'sbx')

    platform = e3.platform.Platform.get().platform

    e3.os.process.Run(['e3-sandbox', 'create', sandbox_dir], output=None)
    with open(os.path.join(sandbox_dir, 'test.plan'), 'w') as fd:
        fd.write("anod_build('e3')\n")

    specs_source_dir = os.path.join(os.path.dirname(__file__), 'specs')
    local_spec_dir = os.path.join(root_dir, 'specs')

    e3.fs.sync_tree(specs_source_dir, local_spec_dir)
    create_prolog(local_spec_dir)

    # Test with local specs
    p = e3.os.process.Run(['e3-sandbox', 'exec',
                           '--spec-dir', os.path.join(root_dir, 'specs'),
                           '--plan',
                           os.path.join(sandbox_dir, 'test.plan'),
                           sandbox_dir])
    assert 'build e3 for %s' % platform in p.out

    # Test with git module
    p = e3.os.process.Run(['e3-sandbox', 'exec',
                           '--spec-git-url', git_specs_dir,
                           '--plan',
                           os.path.join(sandbox_dir, 'test.plan'),
                           '--create-sandbox', sandbox_dir])
    assert 'build e3 for %s' % platform in p.out


def test_anod_plan(git_specs_dir):
    """Test if sandbox exec works with local specs and a git repo."""
    root_dir = os.getcwd()
    sandbox_dir = os.path.join(root_dir, 'sbx')

    # create sandbox
    with_git = e3.os.process.Run(['e3-sandbox', '-v',
                                  'create',
                                  '--spec-git-url', git_specs_dir,
                                  sandbox_dir], output=None)
    assert with_git.status == 0

    # Test anod build
    platform = e3.platform.Platform.get().platform

    # Build action
    with open(os.path.join(root_dir, 'e3_build.plan'), 'w') as fd:
        fd.write("anod_build('e3')")

    command = ['e3-sandbox', '-v', 'exec',
               '--plan', os.path.join(root_dir, 'e3_build.plan'),
               '--dry-run', sandbox_dir]
    p = e3.os.process.Run(command)
    assert p.status == 0
    actions = ['build e3 for %s' % platform, ]
    for action in actions:
        assert action in p.out
    # Install action
    with open(os.path.join(root_dir, 'e3_build.plan'), 'w') as fd:
        fd.write("anod_install('e3')")
    p = e3.os.process.Run(command)
    assert p.status == 0
    actions = ['download binary of %s.e3' % platform,
               'install e3 for %s' % platform]
    for action in actions:
        assert action in p.out

    # Test action
    with open(os.path.join(root_dir, 'e3_build.plan'), 'w') as fd:
        fd.write("anod_test('e3')")
    p = e3.os.process.Run(command)
    assert p.status == 0
    actions = ['checkout e3-core-github',
               'build python-virtualenv for %s' % platform,
               'get source e3-core-src',
               'install source e3-core-src',
               'test e3 for %s' % platform]
    for action in actions:
        assert action in p.out
    # Test with download source resolver
    command = ['e3-sandbox', '-v', 'exec',
               '--plan', os.path.join(root_dir, 'e3_build.plan'),
               '--dry-run',
               '--resolver', 'always_download_source_resolver',
               sandbox_dir]
    p = e3.os.process.Run(command)
    assert p.status == 0
    actions = ['download source e3-core-src',
               'build python-virtualenv for %s' % platform,
               'get source e3-core-src',
               'install source e3-core-src',
               'test e3 for %s' % platform]
    for action in actions:
        assert action in p.out


def test_anodtest(git_specs_dir, e3fake_git_dir):
    """Test the procedure of anodtest('e3fake')."""
    root_dir = os.getcwd()
    sandbox_dir = os.path.join(root_dir, 'sbx')
    plan_file = os.path.join(root_dir, 'e3_test.plan')
    p = e3.os.process.Run(['e3-sandbox', '-v', 'create',
                           '--spec-git-url', git_specs_dir,
                           sandbox_dir])
    assert p.status == 0

    with open(plan_file, 'w') as plan_fd:
        plan_fd.write("anod_test('e3fake')")
    # Add the git path
    conf_dir = os.path.join(sandbox_dir, 'specs', 'conf.yaml')
    git_repo_entry = E3Fake % e3fake_git_dir
    with open(conf_dir, 'w') as conf_fd:
        conf_fd.write(git_repo_entry)
    command = ['e3-sandbox', '-v', 'exec',
               '--plan', plan_file,
               sandbox_dir]
    p = e3.os.process.Run(command)
    assert p.status == 0
    # Test for buildspaces
    platform = e3.platform.Platform.get().platform
    dirs = [platform,
            os.path.join(platform, 'e3fake'),
            os.path.join(platform, 'python-virtualenv')]
    for dir_test in dirs:
        assert os.path.exists(os.path.join(sandbox_dir, dir_test))
    # Test for vcs failure
    git_repo_entry = E3FakeNoGit % e3fake_git_dir
    with open(conf_dir, 'w') as conf_fd:
        conf_fd.write(git_repo_entry)
    p = e3.os.process.Run(command)
    assert 'svn vcs type not supported' in p.out
