from __future__ import absolute_import, division, print_function

import os
import sys

from e3.fs import echo_to_file
from e3.os.fs import unixpath
from e3.vcs.git import GitError, GitRepository

import pytest


@pytest.mark.git
def test_git_repo():
    working_tree = unixpath(os.path.join(os.getcwd(), 'working_tree'))
    working_tree2 = os.path.join(os.getcwd(), 'working_tree2')
    repo = GitRepository(working_tree)
    repo.init()
    os.chdir(working_tree)
    new_file = unixpath(os.path.join(working_tree, 'new.txt'))
    echo_to_file(new_file, 'new\n')
    repo.git_cmd(['add', 'new.txt'])
    repo.git_cmd(['config', 'user.email', 'e3-core@example.net'])
    repo.git_cmd(['config', 'user.name', 'e3 core'])
    repo.git_cmd(['commit', '-m', 'new file'])
    repo.git_cmd(['tag', '-a', '-m', 'new tag', '20.0855369232'])

    with open('log.txt', 'w') as f:
        repo.write_log(f)
    with open('log.txt', 'r') as f:
        commits = list(repo.parse_log(f))
        assert 'new file' in commits[0]['message']
        assert commits[0]['email'] == 'e3-core@example.net'
        new_sha = commits[0]['sha']

    assert '20.0855369232' in repo.describe()
    assert new_sha == repo.rev_parse()

    with pytest.raises(GitError) as err:
        repo.describe('g')
    assert 'describe --always g' in str(err)

    echo_to_file(new_file, 'new line\n', append=True)

    with open('commit1.diff', 'wb') as f:
        repo.write_local_diff(f)

    with open('commit1.diff', 'rb') as f:
        assert b'+new line' in f.read()

    echo_to_file(new_file, 10000 * '*')

    repo.git_cmd(['commit', '-a', '-m', 'file update'])
    with open('log2.txt', 'w') as f:
        repo.write_log(f)
    with open('log2.txt', 'r') as f:
        commits = list(repo.parse_log(f, max_diff_size=1000))
        # assert b'diff too long' not in commits[1]['diff']
        assert 'file update' in commits[0]['message']
        assert 'diff too long' in commits[0]['diff']
        assert 'new file' in commits[1]['message']
        assert commits[1]['sha'] != commits[0]['sha']
        assert commits[1]['diff'] != commits[0]['diff']

    repo2 = GitRepository(working_tree2)
    repo2.init(url=working_tree, remote='tree1')
    try:
        repo2.update(url=working_tree, refspec='master')
    except GitError:
        if sys.platform == 'win32':
            # some git versions on windows do not support that well
            # ignore this test for now???
            pass
    else:
        repo2.rev_parse() == repo.rev_parse()
