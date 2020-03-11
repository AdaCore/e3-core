import logging
import os

from e3.anod.checkout import CheckoutManager
from e3.anod.status import ReturnValue
from e3.vcs.svn import SVNRepository
from e3.vcs.git import GitRepository
from e3.os.fs import touch


class TestCheckout(object):
    repo_data = os.path.join(os.path.dirname(__file__), "vcs_data")
    repo_data2 = os.path.join(os.path.dirname(__file__), "vcs_data2")

    def test_svn_checkout(self):
        os.environ["GIT_AUTHOR_EMAIL"] = "e3-core@example.net"
        os.environ["GIT_AUTHOR_NAME"] = "e3 core"
        os.environ["GIT_COMMITTER_NAME"] = "e3-core@example.net"
        os.environ["GIT_COMMITTER_EMAIL"] = "e3 core"

        url = SVNRepository.create("svn", initial_content_path=self.repo_data)
        url2 = SVNRepository.create("svn2", initial_content_path=self.repo_data2)
        url3 = GitRepository.create("git", initial_content_path=self.repo_data)
        url4 = GitRepository.create("git2", initial_content_path=self.repo_data2)

        r = SVNRepository(working_copy=os.path.abspath("svn_checkout"))
        r.update(url=url)

        m = CheckoutManager(name="myrepo", working_dir=".")

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
        with open(os.path.join("myrepo", "file3.txt"), "r") as fd:
            assert fd.read().strip() == "new file!"

        logging.info("Check that we can switch from one svn url to another")
        result = m.update(vcs="svn", url=url2)
        assert result == ReturnValue.success
        assert os.path.isfile(os.path.join("myrepo", "file1.txt", "data2.txt"))

        logging.info("Check that we can switch from one svn url to a git repo")
        result = m.update(vcs="git", url=url3, revision="master")
        assert result == ReturnValue.success
        assert os.path.isfile(os.path.join("myrepo", "file1.txt"))

        logging.info("Check that we can switch from one git url to another one")
        result = m.update(vcs="git", url=url4, revision="master")
        assert result == ReturnValue.success
        assert os.path.isfile(os.path.join("myrepo", "file1.txt", "data2.txt"))

        logging.info("Check that in case of no changes unchanged is returned")
        result = m.update(vcs="git", url=url4, revision="master")
        assert result == ReturnValue.unchanged

        logging.info("Check that changes are detected in git reposotories")
        with open(os.path.join("git2", "file3.txt"), "w") as fd:
            fd.write("new file!")
        r = GitRepository(os.path.abspath("git2"))
        r.git_cmd(["add", "file3.txt"])
        r.git_cmd(["commit", "-m", "new file"])
        result = m.update(vcs="git", url=url4, revision="master")
        assert result == ReturnValue.success
        assert os.path.isfile(os.path.join("myrepo", "file3.txt"))

        logging.info("Check that local modifications are discarded")
        with open(os.path.join("myrepo", "file3.txt"), "w") as fd:
            fd.write("new file modified!")
        result = m.update(vcs="git", url=url4, revision="master")
        assert result == ReturnValue.unchanged
        with open(os.path.join("myrepo", "file3.txt"), "r") as fd:
            assert fd.read().strip() == "new file!"

        result = m.update(vcs="future-vcs", url="dummy")
        assert result == ReturnValue.failure

        result = m.update(vcs="git", url=url4 + "non-existing", revision="master")
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
