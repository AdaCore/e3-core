import os
import subprocess

from e3.fs import echo_to_file, rm
from e3.os.fs import unixpath
from e3.vcs.git import GitError, GitRepository

import pytest
import tempfile
from contextlib import closing


@pytest.mark.git
def test_git_non_utf8():
    """Test with non utf-8 encoding in changelog."""
    working_tree = os.path.join(os.getcwd(), "working_tree")
    repo = GitRepository(working_tree)
    repo.init()
    os.chdir(working_tree)
    new_file = os.path.join(working_tree, "new.txt")
    commit_msg = os.path.join(working_tree, "commit.txt")

    with open(commit_msg, "wb") as fd:
        fd.write(b"\x03\xff")

    with open(new_file, "wb") as fd:
        fd.write(b"\x03\xff")

    repo.git_cmd(["add", "new.txt"])
    repo.git_cmd(["config", "user.email", "e3-core@example.net"])
    repo.git_cmd(["config", "user.name", "e3 core"])
    repo.git_cmd(["commit", "-F", commit_msg])

    with closing(tempfile.NamedTemporaryFile(mode="w", delete=False)) as fd:
        repo.write_log(fd)
        tmp_filename = fd.name
    try:
        with open(tmp_filename) as fd:
            commits = [commit for commit in repo.parse_log(fd, max_diff_size=1024)]
    finally:
        rm(tmp_filename)

    assert "\\x03\\xff" in commits[0]["diff"]


@pytest.mark.git
def test_git_repo():
    working_tree = os.path.join(os.getcwd(), "working_tree")
    working_tree2 = os.path.join(os.getcwd(), "working_tree2")
    repo = GitRepository(working_tree)
    repo.init()
    os.chdir(working_tree)
    new_file = os.path.join(working_tree, "new.txt")
    echo_to_file(new_file, "new\n")

    commit_note = unixpath(os.path.join(working_tree, "commit_note.txt"))
    echo_to_file(
        commit_note,
        "\n".join(
            (
                "Code-Review+2: Nobody <nobody@example.com>",
                "Submitted-by: Nobody <nobody@example.com>",
                "Submitted-at: Thu, 08 Jun 2017 18:40:11 +0200",
            )
        ),
    )

    repo.git_cmd(["add", "new.txt"])
    repo.git_cmd(["config", "user.email", "e3-core@example.net"])
    repo.git_cmd(["config", "user.name", "e3 core"])
    repo.git_cmd(["commit", "-m", "new file"])
    repo.git_cmd(["tag", "-a", "-m", "new tag", "20.0855369232"])
    repo.git_cmd(["notes", "--ref", "review", "add", "HEAD", "-F", commit_note])

    # try with gerrit notes
    with open("log.txt", "w") as f:
        repo.write_log(f, with_gerrit_notes=True)
    with open("log.txt", "r") as f:
        commits = list(repo.parse_log(f))
        assert "nobody@example.com" in commits[0]["notes"]["Code-Review+2"]

    # try with an invalid note
    repo.git_cmd(
        ["notes", "--ref", "review", "add", "HEAD", "-f", "-m", "invalid-note"]
    )
    with open("log.txt", "w") as f:
        repo.write_log(f, with_gerrit_notes=True)
    with open("log.txt", "r") as f:
        commits = list(repo.parse_log(f))
        assert commits[0]["notes"] is None

    # try again without gerrit notes
    with open("log.txt", "w") as f:
        repo.write_log(f)
    with open("log.txt", "r") as f:
        commits = list(repo.parse_log(f))
        assert "new file" in commits[0]["message"]
        assert commits[0]["email"] == "e3-core@example.net"
        new_sha = commits[0]["sha"]

    assert "20.0855369232" in repo.describe()
    assert new_sha == repo.rev_parse()

    with pytest.raises(GitError) as err:
        repo.describe("g")
    assert "describe --always g" in str(err)

    echo_to_file(new_file, "new line\n", append=True)

    with open("commit1.diff", "wb") as f:
        repo.write_local_diff(f)

    with open("commit1.diff", "rb") as f:
        assert b"+new line" in f.read()

    echo_to_file(new_file, 10000 * "*")

    repo.git_cmd(["commit", "-a", "-m", "file update"])
    with open("log2.txt", "w") as f:
        repo.write_log(f)
    with open("log2.txt", "r") as f:
        commits = list(repo.parse_log(f, max_diff_size=1000))
        # assert b'diff too long' not in commits[1]['diff']
        assert "file update" in commits[0]["message"]
        assert "diff too long" in commits[0]["diff"]
        assert "new file" in commits[1]["message"]
        assert commits[1]["sha"] != commits[0]["sha"]
        assert commits[1]["diff"] != commits[0]["diff"]

    repo2 = GitRepository(working_tree2)
    giturl = "file://%s" % working_tree.replace("\\", "/")
    repo2.init(url=giturl, remote="tree1")
    repo2.update(url=giturl, refspec="master")
    repo2.rev_parse() == repo.rev_parse()

    repo2.fetch_gerrit_notes(url=giturl)
    p = repo2.git_cmd(
        ["notes", "--ref=review", "show", new_sha], output=subprocess.PIPE
    )
    assert "invalid-note" in p.out
