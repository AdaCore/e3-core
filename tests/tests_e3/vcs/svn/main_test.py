import os
import sys

from e3.fs import echo_to_file, mkdir, rm
from e3.os.fs import touch, unixpath
from e3.os.process import Run
from e3.vcs.svn import SVNError, SVNRepository

import pytest


def file_url(path, unix=False):
    if sys.platform == "win32":
        if len(path) > 1 and path[1] == ":":
            # svn info returns the URL with an uppercase letter drive
            path = path[0].upper() + path[1:]
        if unix:
            return "file://" + unixpath(path)
        else:
            return "file:///" + path.replace("\\", "/")
    else:
        return "file://" + path


@pytest.mark.svn
def test_svn_repo():
    cwd = os.getcwd()

    # --- create local project
    project_path = os.path.join(cwd, "test_project")
    mkdir(project_path)
    mkdir(os.path.join(project_path, "trunk"))
    hello_relative_path = os.path.join("trunk", "hello.txt")
    hello_path = os.path.join(project_path, hello_relative_path)
    echo_to_file(hello_path, "hello")

    # --- create a SVN repository from that project
    repos_path = os.path.join(cwd, "repos")
    project_url = SVNRepository.create(repo_path=repos_path)
    project_url = project_url + "/Test_Project"
    p = Run(["svn", "import", project_path, project_url, "-m", "initial import"])
    assert p.status == 0, p.out

    # --- checkout project into working dir A
    working_copy_a_path = os.path.join(cwd, "working_copy_a")
    svn_a = SVNRepository(working_copy_a_path)
    with pytest.raises(SVNError):
        svn_a.update()
    with pytest.raises(SVNError):
        svn_a.update(url=file_url("bad_url"))
    local_change = svn_a.update(project_url)
    assert local_change
    local_change = svn_a.update()
    assert not local_change
    # verify the content of the working dir A and its revision
    assert svn_a.url == project_url
    assert os.path.exists(
        os.path.join(working_copy_a_path, hello_relative_path)
    ), "checkout failed"
    assert svn_a.current_revision == "1"
    # modify the working dir, commit the change,
    # update the working dir and verify the new current revision
    echo_to_file(os.path.join(working_copy_a_path, hello_relative_path), "bye")
    svn_a.svn_cmd(["commit", "-m", "modify hello"])
    svn_a.update()
    assert svn_a.current_revision == "2"
    svn_a.update(revision="1")
    assert svn_a.current_revision == "1"
    with pytest.raises(SVNError):
        svn_a.update(revision="404")

    # make local changes in the working dir B before updating it
    working_copy_b_path = os.path.join(cwd, "working_copy_b")
    svn_b = SVNRepository(working_copy_b_path)
    svn_b.update(project_url)
    foo_path = os.path.join(working_copy_b_path, "trunk", "foo")
    touch(foo_path)
    hello_b_path = os.path.join(working_copy_b_path, hello_relative_path)
    echo_to_file(hello_b_path, "kitty")
    local_change = svn_b.update()
    assert local_change
    assert os.path.exists(foo_path)
    with open(hello_b_path, "r") as f:
        assert "kitty" in f.read()
    # update and cancel all changes
    svn_b.update(force_and_clean=True)
    assert not os.path.exists(foo_path)
    with open(hello_b_path, "r") as f:
        assert "bye" in f.read()

    # checkout into an existing path (not versioned)
    working_copy_c_path = os.path.join(cwd, "working_copy_c")
    svn_c = SVNRepository(working_copy_c_path)
    touch(working_copy_c_path)
    with pytest.raises(SVNError) as err:
        svn_c.update(url=project_url)
    assert "not empty" in str(err)
    rm(working_copy_c_path)
    mkdir(working_copy_c_path)

    bar_path = os.path.join(working_copy_c_path, "bar")
    touch(bar_path)
    # verify failures without the force option
    with pytest.raises(SVNError) as err:
        svn_c.update(url=project_url)
    assert "not empty" in str(err)
    touch(os.path.join(working_copy_c_path, ".svn"))
    with pytest.raises(SVNError):
        svn_c.update(url=project_url)
    svn_c.update(url=project_url, force_and_clean=True)
    # verify that the working dir C is clean
    assert not os.path.exists(bar_path)

    # modify a working dir and update it with a new project
    svn_d = SVNRepository(working_copy_c_path)
    touch(bar_path)
    svn_d.update()  # update with the last URL used for this dir
    svn_d.update(url=project_url)  # update with the same URL
    assert os.path.exists(bar_path)
    project2_url = project_url + "2"
    p = Run(["svn", "import", project_path, project2_url, "-m", "initial import"])
    assert p.status == 0, p.out
    with pytest.raises(SVNError) as err:
        svn_d.update(url=project2_url)  # update with new URL
    assert "not empty" in str(err)
    svn_d.update(url=project2_url, force_and_clean=True)
    assert svn_d.url == project2_url
