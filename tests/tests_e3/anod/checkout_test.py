import sys
import logging
import os
import pytest

from e3.anod.checkout import CheckoutManager
from e3.anod.status import ReturnValue
from e3.vcs.svn import SVNRepository
from e3.vcs.git import GitRepository
from e3.fs import mkdir
from e3.os.fs import touch
import uuid
import time


def test_rsync_mode():
    """Check that rsync mode is faster than default mode."""
    mkdir("work")
    mkdir("work2")
    GitRepository.create("git")
    for _ in range(1000):
        name = str(uuid.uuid1(clock_seq=int(1000 * time.time())))
        touch(os.path.join("git", name + ".py"))
        touch(os.path.join("git", name + ".pyc"))
        touch(os.path.join("git", name + ".o"))
        touch(os.path.join("git", name + ".ali"))

    with open("git/.gitignore", "w") as fd:
        fd.write("*.pyc\n")
        fd.write("*.o\n")
        fd.write("*.ali\n")

    m = CheckoutManager(name="myrepo", working_dir="work")
    m.update(vcs="external", url=os.path.abspath("git"))

    os.environ["E3_ENABLE_FEATURE"] = "use-rsync"

    m = CheckoutManager(name="myrepo", working_dir="work2")
    m.update(vcs="external", url=os.path.abspath("git"))


class TestCheckout:
    repo_data = os.path.join(os.path.dirname(__file__), "vcs_data")
    repo_data2 = os.path.join(os.path.dirname(__file__), "vcs_data2")

    @pytest.mark.parametrize("compute_changelog", [True, False])
    @pytest.mark.parametrize("e3_feature", ["", "git_shallow_fetch"])
    def test_git_clone(self, git, compute_changelog, e3_feature):
        """Test CheckoutManager with Git repositories."""
        os.environ["GIT_AUTHOR_EMAIL"] = "e3-core@example.net"
        os.environ["GIT_AUTHOR_NAME"] = "e3 core"
        os.environ["GIT_COMMITTER_NAME"] = "e3-core@example.net"
        os.environ["GIT_COMMITTER_EMAIL"] = "e3 core"
        os.environ["E3_ENABLE_FEATURE"] = e3_feature

        url3 = GitRepository.create("git", initial_content_path=self.repo_data)
        url4 = GitRepository.create("git2", initial_content_path=self.repo_data2)

        # Get the default branch for a Git repository (all subsequent
        # repositories will have the same)
        main_branch = GitRepository(url4).git_cmd(["branch", "--show-current"]).out

        m = CheckoutManager(
            name="myrepo", working_dir=".", compute_changelog=compute_changelog
        )

        result = m.update(vcs="git", url=url3, revision=main_branch)
        assert result == ReturnValue.success
        assert os.path.isfile(os.path.join("myrepo", "file1.txt"))

        logging.info("Check that we can switch from one git url to another one")
        result = m.update(vcs="git", url=url4, revision=main_branch)
        assert result == ReturnValue.success
        assert os.path.isfile(os.path.join("myrepo", "file1.txt", "data2.txt"))

        logging.info("Check that in case of no changes unchanged is returned")
        result = m.update(vcs="git", url=url4, revision=main_branch)
        assert result == ReturnValue.unchanged

        logging.info("Check that changes are detected in git reposotories")
        with open(os.path.join("git2", "file3.txt"), "w") as fd:
            fd.write("new file!")
        r = GitRepository(os.path.abspath("git2"))
        r.git_cmd(["add", "file3.txt"])
        r.git_cmd(["commit", "-m", "new file"])
        result = m.update(vcs="git", url=url4, revision=main_branch)
        assert result == ReturnValue.success
        assert os.path.isfile(os.path.join("myrepo", "file3.txt"))

        logging.info("Check that local modifications are discarded")
        with open(os.path.join("myrepo", "file3.txt"), "w") as fd:
            fd.write("new file modified!")
        result = m.update(vcs="git", url=url4, revision=main_branch)
        assert result == ReturnValue.unchanged
        with open(os.path.join("myrepo", "file3.txt")) as fd:
            assert fd.read().strip() == "new file!"

        result = m.update(vcs="git", url=url4 + "non-existing", revision=main_branch)
        assert result == ReturnValue.failure

        result = m.update(vcs="git", url=url4)
        assert result == ReturnValue.failure

        # Add a .gitignore and use an external

        touch("git2/file4.txt")
        touch("git2/ignore_file.txt")
        with open("git2/.gitignore", "w") as fd:
            fd.write("/ignore_file.txt")

        result = m.update(vcs="external", url=os.path.abspath("git2"))
        assert os.path.isfile(os.path.join(m.working_dir, "file4.txt"))
        assert not os.path.isfile(os.path.join(m.working_dir, "ignore_file.txt"))
        assert result == ReturnValue.success

        result = m.update(vcs="external", url=os.path.abspath("git2"))
        assert result == ReturnValue.unchanged

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="legacy test using SVN - only minimal testing on Linux",
    )
    @pytest.mark.parametrize("compute_changelog", [True, False])
    def test_svn_checkout(self, svn, compute_changelog):
        """Test CheckoutManager with Subversion repositories."""
        url = SVNRepository.create("svn", initial_content_path=self.repo_data)
        url2 = SVNRepository.create("svn2", initial_content_path=self.repo_data2)
        r = SVNRepository(working_copy=os.path.abspath("svn_checkout"))
        r.update(url=url)

        m = CheckoutManager(
            name="myrepo", working_dir=".", compute_changelog=compute_changelog
        )
        logging.info("update of non existing url")
        result = m.update(vcs="svn", url=url + "wrong_url")
        assert result == ReturnValue.failure

        logging.info("update of existing url")
        result = m.update(vcs="svn", url=url)
        assert result == ReturnValue.success

        logging.info("update of existing url with no changes")
        result = m.update(vcs="svn", url=url)
        assert result == ReturnValue.unchanged

        # Update the repository
        logging.info("Do a checkin in svn repository")
        with open(os.path.join("svn_checkout", "file3.txt"), "w") as fd:
            fd.write("new file!")
        r.svn_cmd(["add", "file3.txt"])
        r.svn_cmd(["commit", "file3.txt", "-m", "checkin"])

        logging.info("Check that we see the update")
        result = m.update(vcs="svn", url=url)
        assert result == ReturnValue.success
        assert os.path.isfile(os.path.join("svn_checkout", "file3.txt"))

        logging.info("Do a local modification in the working dir")
        with open(os.path.join("myrepo", "file3.txt"), "w") as fd:
            fd.write("new file modified!")

        logging.info("And then do an update and check that cleanup was done")
        result = m.update(vcs="svn", url=url)
        assert result == ReturnValue.unchanged
        with open(os.path.join("myrepo", "file3.txt")) as fd:
            assert fd.read().strip() == "new file!"

        logging.info("Check that we can switch from one svn url to another")
        result = m.update(vcs="svn", url=url2)
        assert result == ReturnValue.success
        assert os.path.isfile(os.path.join("myrepo", "file1.txt", "data2.txt"))

    def test_shallow_since_checkout(self):
        os.environ["GIT_AUTHOR_EMAIL"] = "e3-core@example.net"
        os.environ["GIT_AUTHOR_NAME"] = "e3 core"
        os.environ["GIT_COMMITTER_NAME"] = "e3 core"
        os.environ["GIT_COMMITTER_EMAIL"] = "e3-core@example.net"
        os.environ["E3_ENABLE_FEATURE"] = "git_fetch_shallow_since=2020-08-04"
        os.environ["GIT_COMMITTER_DATE"] = "2020-08-01T22:13:13"

        url = GitRepository.create("git3")

        with open(os.path.join("git3", "file3.txt"), "w") as fd:
            fd.write("first file!")
        with open(os.path.join("git3", "file4.txt"), "w") as fd:
            fd.write("second file!")

        m = CheckoutManager(name="myrepo", working_dir=".")

        r = GitRepository(os.path.abspath("git3"))
        main_branch = r.git_cmd(["branch", "--show-current"]).out

        r.git_cmd(["add", "file3.txt"])
        r.git_cmd(["commit", "-m", "first commit", "--date", "2020-08-01T22:13:13"])

        os.environ["GIT_COMMITTER_DATE"] = "2020-08-05T22:13:13"
        r.git_cmd(["add", "file4.txt"])
        r.git_cmd(["commit", "-m", "second commit", "--date", "2020-08-05T22:13:13"])

        result = m.update(vcs="git", url=url, revision=main_branch)

        myrepo = GitRepository(os.path.abspath("myrepo"))
        myrepo.git_cmd(["log", "--pretty=format:%s"], output="log.txt")

        with open("log.txt", "r") as fd:
            log = fd.readlines()

        assert result == ReturnValue.success
        assert os.path.isfile(os.path.join("myrepo", "file3.txt"))
        assert os.path.isfile(os.path.join("myrepo", "file4.txt"))
        assert log == ["second commit"]

    def test_max_depth_checkout(self):
        os.environ["GIT_AUTHOR_EMAIL"] = "e3-core@example.net"
        os.environ["GIT_AUTHOR_NAME"] = "e3 core"
        os.environ["GIT_COMMITTER_NAME"] = "e3 core"
        os.environ["GIT_COMMITTER_EMAIL"] = "e3-core@example.net"
        os.environ["E3_ENABLE_FEATURE"] = "git_fetch_max_depth=2"

        url = GitRepository.create("git4")

        with open(os.path.join("git4", "file3.txt"), "w") as fd:
            fd.write("first file!")
        with open(os.path.join("git4", "file4.txt"), "w") as fd:
            fd.write("second file!")
        with open(os.path.join("git4", "file5.txt"), "w") as fd:
            fd.write("third file!")

        m = CheckoutManager(name="myrepo", working_dir=".")

        r = GitRepository(os.path.abspath("git4"))

        r.git_cmd(["add", "file3.txt"])
        r.git_cmd(["commit", "-m", "first commit"])

        r.git_cmd(["add", "file4.txt"])
        r.git_cmd(["commit", "-m", "second commit"])

        r.git_cmd(["add", "file5.txt"])
        r.git_cmd(["commit", "-m", "third commit"])

        main_branch = r.git_cmd(["branch", "--show-current"]).out
        result = m.update(vcs="git", url=url, revision=main_branch)

        myrepo = GitRepository(os.path.abspath("myrepo"))
        myrepo.git_cmd(["log", "--pretty=format:%s"], output="log.txt")

        with open("log.txt", "r") as fd:
            log = fd.read().splitlines()

        assert result == ReturnValue.success
        assert os.path.isfile(os.path.join("myrepo", "file3.txt"))
        assert os.path.isfile(os.path.join("myrepo", "file4.txt"))
        assert os.path.isfile(os.path.join("myrepo", "file5.txt"))
        assert log == ["third commit", "second commit"]
