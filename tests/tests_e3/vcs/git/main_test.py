"""Tests for e3.vcs.git."""

from pathlib import Path
import os
import subprocess

from e3.fs import echo_to_file, rm
from e3.os.fs import unixpath
from e3.vcs.git import GitError, GitRepository

import pytest
import tempfile
from contextlib import closing


def test_git_non_utf8(git) -> None:
    """Test with non utf-8 encoding in changelog."""
    working_tree = Path.cwd() / "working_tree"
    repo = GitRepository(str(working_tree))
    repo.init()
    os.chdir(working_tree)
    new_file = working_tree / "new.txt"
    commit_msg = working_tree / "commit.txt"

    with commit_msg.open("wb") as fd:
        fd.write(b"\x03\xff")

    with new_file.open("wb") as fd:
        fd.write(b"\x03\xff")

    repo.git_cmd(["add", "new.txt"])
    repo.git_cmd(["config", "user.email", "e3-core@example.net"])
    repo.git_cmd(["config", "user.name", "e3 core"])
    repo.git_cmd(["commit", "-F", str(commit_msg)])

    with closing(tempfile.NamedTemporaryFile(mode="w", delete=False)) as fd:
        repo.write_log(fd)
        tmp_filename = fd.name
    try:
        with Path(tmp_filename).open() as fd:
            commits = list(repo.parse_log(fd, max_diff_size=1024))
    finally:
        rm(tmp_filename)

    assert "\\x03\\xff" in commits[0]["diff"]


def test_git_repo(git) -> None:
    working_tree = Path.cwd() / "working_tree"
    working_tree2 = Path.cwd() / "working_tree2"
    repo = GitRepository(str(working_tree))
    repo.init()
    os.chdir(working_tree)
    new_file = str(working_tree / "new.txt")
    echo_to_file(new_file, "new\n")

    commit_note = unixpath(working_tree / "commit_note.txt")
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

    repo.git_cmd(["-c", "core.safecrlf=false", "add", "new.txt"])
    repo.git_cmd(["config", "user.email", "e3-core@example.net"])
    repo.git_cmd(["config", "user.name", "e3 core"])
    repo.git_cmd(["commit", "-m", "new file"])

    main_branch = repo.git_cmd(["branch", "--show-current"]).out

    repo.git_cmd(["tag", "-a", "-m", "new tag", "20.0855369232"])
    repo.git_cmd(["notes", "--ref", "review", "add", "HEAD", "-F", commit_note])

    # try with gerrit notes
    with Path("log.txt").open("w") as f:
        repo.write_log(f, with_gerrit_notes=True)
    with Path("log.txt").open() as f:
        commits = list(repo.parse_log(f))
        assert "nobody@example.com" in commits[0]["notes"]["Code-Review+2"]

    # try with an invalid note
    repo.git_cmd(
        ["notes", "--ref", "review", "add", "HEAD", "-f", "-m", "invalid-note"]
    )
    with Path("log.txt").open("w") as f:
        repo.write_log(f, with_gerrit_notes=True)
    with Path("log.txt").open() as f:
        commits = list(repo.parse_log(f))
        assert commits[0]["notes"] is None

    # try again without gerrit notes
    with Path("log.txt").open("w") as f:
        repo.write_log(f)
    with Path("log.txt").open() as f:
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

    with Path("commit1.diff").open("wb") as f:
        repo.write_local_diff(f)

    with Path("commit1.diff").open("rb") as f:
        assert b"+new line" in f.read()

    echo_to_file(new_file, 10000 * "*")

    repo.git_cmd(["commit", "-a", "-m", "file update"])
    with Path("log2.txt").open("w") as f:
        repo.write_log(f)
    with Path("log2.txt").open() as f:
        commits = list(repo.parse_log(f, max_diff_size=1000))
        # assert b'diff too long' not in commits[1]['diff']
        assert "file update" in commits[0]["message"]
        assert "diff too long" in commits[0]["diff"]
        assert "new file" in commits[1]["message"]
        assert commits[1]["sha"] != commits[0]["sha"]
        assert commits[1]["diff"] != commits[0]["diff"]

    repo2 = GitRepository(working_tree2)
    giturl = "file://{}".format(str(working_tree).replace("\\", "/"))
    repo2.init(url=giturl, remote="tree1")
    repo2.update(url=giturl, refspec=main_branch)
    assert repo2.rev_parse() == repo.rev_parse()

    repo2.fetch_gerrit_notes(url=giturl)
    p = repo2.git_cmd(
        ["notes", "--ref=review", "show", new_sha], output=subprocess.PIPE
    )
    assert "invalid-note" in p.out
