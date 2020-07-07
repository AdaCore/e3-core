import os
import sys

import e3.anod.error
import e3.anod.helper
import e3.anod.sandbox
import e3.env
import e3.fs
import e3.os.process
import e3.platform
import yaml
from e3.vcs.git import GitRepository

import pytest

PROLOG = r"""# prolog file loaded before all specs


def main():
    import yaml
    import os

    with open(os.path.join(
            __spec_repository.spec_dir, 'conf.yaml')) as f:
        conf = yaml.safe_load(f)
        __spec_repository.api_version = conf['api_version']
        __spec_repository.repos = conf['repositories']


main()
del main
"""


def create_prolog(prolog_dir, content=PROLOG):
    """Create prolog.py file on the fly to prevent checkstyle error."""
    if os.path.isfile(os.path.join(prolog_dir, "prolog.py")):
        return
    with open(os.path.join(prolog_dir, "prolog.py"), "w") as f:
        f.write(content)


@pytest.fixture
def git_specs_dir(git, tmpdir):
    """Create a git repo to check out specs from it."""
    del git  # skip or fail when git is not installed

    # Create a e3-specs git repository for all tests in this module
    specs_dir = str(tmpdir.mkdir("e3-specs-git-repo"))

    try:
        specs_source_dir = os.path.join(os.path.dirname(__file__), "specs")
        for spec_file in os.listdir(specs_source_dir):
            if os.path.isfile(os.path.join(specs_source_dir, spec_file)):
                e3.fs.cp(
                    os.path.join(specs_source_dir, spec_file),
                    os.path.join(specs_dir, spec_file),
                )
        # Put prolog file
        create_prolog(specs_dir)
        if os.path.isdir(os.path.join(specs_dir, ".git")):
            return
        g = GitRepository(specs_dir)
        g.init()
        g.git_cmd(["config", "user.email", '"test@example.com"'])
        g.git_cmd(["config", "user.name", '"test"'])
        g.git_cmd(["add", "-A"])
        g.git_cmd(["commit", "-m", "'add all'"])
        yield "file://%s" % specs_dir.replace("\\", "/")
    finally:
        e3.fs.rm(specs_dir, True)


def test_deploy_sandbox():
    sandbox_dir = os.getcwd()
    e3.os.process.Run(["e3-sandbox", "-v", "-v", "create", sandbox_dir], output=None)
    assert os.path.isdir("log")

    assert (
        "sandbox = %s" % sandbox_dir
        in e3.os.process.Run(["e3-sandbox", "show-config", sandbox_dir]).out
    )

    e3.fs.mkdir("specs")

    with open(os.path.join("specs", "a.anod"), "w") as fd:
        fd.write("from e3.anod.spec import Anod\n")
        fd.write("class A(Anod):\n")
        fd.write("    pass\n")

    assert (
        "no primitive download"
        in e3.os.process.Run([os.path.join("bin", "anod"), "download", "a"]).out
    )

    with open(os.path.join("specs", "b.anod"), "w") as fd:
        fd.write("from e3.anod.spec import Anod\n")
        fd.write("class B(Anod):\n\n")
        fd.write("    @Anod.primitive()\n")
        fd.write("    def download(self):\n")
        fd.write("        pass\n")

    assert (
        "no download metadata returned by the download primitive"
        in e3.os.process.Run([os.path.join("bin", "anod"), "download", "b"]).out
    )


def test_sandbox_show_config_err():
    """Check e3-sandbox show-config with invalid sandbox."""
    sandbox_dir = os.getcwd()
    sandbox_conf = os.path.join("meta", "sandbox.yaml")
    e3.os.process.Run(["e3-sandbox", "-v", "-v", "create", sandbox_dir], output=None)
    with open(sandbox_conf) as f:
        conf = yaml.safe_load(f.read())
    conf["cmd_line"].append("--wrong-arg")
    with open(sandbox_conf, "w") as f:
        yaml.safe_dump(conf, stream=f)

    assert (
        "the configuration is invalid"
        in e3.os.process.Run(["e3-sandbox", "show-config", sandbox_dir]).out
    )

    with open(sandbox_conf, "w") as f:
        f.write("invalid")

    assert (
        "the configuration is invalid"
        in e3.os.process.Run(["e3-sandbox", "show-config", sandbox_dir]).out
    )


def test_sandbox_env():
    os.environ["GPR_PROJECT_PATH"] = "/foo"
    sandbox = e3.anod.sandbox.SandBox(root_dir=os.getcwd())
    sandbox.set_default_env()
    assert os.environ["GPR_PROJECT_PATH"] == ""


def test_sandbox_rootdir():
    sandbox = e3.anod.sandbox.SandBox(root_dir="foo")
    assert os.path.relpath(sandbox.tmp_dir, sandbox.root_dir) == "tmp"
    assert (
        os.path.relpath(
            sandbox.get_build_space("bar").root_dir,
            os.path.join("foo", e3.env.Env().platform),
        )
        == "bar"
    )


def test_sandbox_create_git(git_specs_dir):
    """Check if sandbox create can load the specs from a git repo."""
    root_dir = os.getcwd()
    sandbox_dir = os.path.join(root_dir, "sbx")
    with_git = e3.os.process.Run(
        ["e3-sandbox", "-v", "create", "--spec-git-url", git_specs_dir, sandbox_dir],
        output=None,
    )
    assert with_git.status == 0
    # Test structure
    for test_dir in ["bin", "log", "meta", "patch", "specs", "src", "tmp", "vcs"]:
        assert os.path.isdir(os.path.join(sandbox_dir, test_dir))
    # Test specs files if created
    specs_files = ["anod.anod", "dummyspec.anod", "conf.yaml", "prolog.py"]
    for filename in specs_files:
        assert os.path.isfile(os.path.join(sandbox_dir, "specs", filename))


def test_sandbox_exec_missing_spec_dir(git_specs_dir):
    """Test sandbox exec exception.

    - Check if sandbox exec raises exception if spec-dir is missing
    """
    root_dir = os.getcwd()
    sandbox_dir = os.path.join(root_dir, "sbx")

    e3.os.process.Run(["e3-sandbox", "create", sandbox_dir], output=None)

    # Specs dir is missing
    no_specs = e3.os.process.Run(
        [
            "e3-sandbox",
            "exec",
            "--specs-dir",
            "nospecs",
            "--plan",
            "noplan",
            sandbox_dir,
        ]
    )
    assert no_specs.status != 0
    assert "nospecs does not exist" in no_specs.out


def test_sandbox_exec_api_version(git_specs_dir):
    """Test sandbox api version check."""
    root_dir = os.getcwd()
    sandbox_dir = os.path.join(root_dir, "sbx")

    e3.os.process.Run(["e3-sandbox", "create", sandbox_dir], output=None)
    with open(os.path.join(sandbox_dir, "test.plan"), "w") as fd:
        fd.write("anod_build('dummyspec')\n")

    specs_source_dir = os.path.join(os.path.dirname(__file__), "specs")
    local_spec_dir = os.path.join(root_dir, "specs")

    e3.fs.sync_tree(specs_source_dir, local_spec_dir)
    create_prolog(local_spec_dir, "")


def test_sandbox_action_errors(git_specs_dir):
    """Test sandbox action error reporting."""
    root_dir = os.getcwd()
    sandbox_dir = os.path.join(root_dir, "sbx")

    e3.os.process.Run(["e3-sandbox", "create", sandbox_dir], output=None)
    with open(os.path.join(sandbox_dir, "test.plan"), "w") as fd:
        fd.write("anod_build('builderror')\n")

    specs_source_dir = os.path.join(os.path.dirname(__file__), "specs")
    local_spec_dir = os.path.join(root_dir, "specs")

    e3.fs.sync_tree(specs_source_dir, local_spec_dir)
    create_prolog(local_spec_dir)

    # Test with local specs
    p = e3.os.process.Run(
        [
            "e3-sandbox",
            "exec",
            "--specs-dir",
            os.path.join(root_dir, "specs"),
            "--plan",
            os.path.join(sandbox_dir, "test.plan"),
            sandbox_dir,
        ]
    )
    assert "'doesnotexist' is not defined" in p.out
    assert "builderror build fails" in p.out


def test_sandbox_exec_missing_plan_file(git_specs_dir):
    """Test sandbox exec exception.

    - Check if sandbox exec raises exception if plan file is missing
    """
    root_dir = os.getcwd()
    sandbox_dir = os.path.join(root_dir, "sbx")

    e3.os.process.Run(["e3-sandbox", "create", sandbox_dir], output=None)

    # Plan file is missing
    no_plan = e3.os.process.Run(
        [
            "e3-sandbox",
            "exec",
            "--spec-git-url",
            git_specs_dir,
            "--plan",
            "noplan",
            "--create-sandbox",
            sandbox_dir,
        ]
    )
    assert no_plan.status != 0
    assert "SandBoxExec.run: plan file noplan does not exist" in no_plan.out


def test_sandbox_exec_success(git_specs_dir):
    """Test if sandbox exec works with local specs and a git repo."""
    root_dir = os.getcwd()
    sandbox_dir = os.path.join(root_dir, "sbx")

    platform = e3.platform.Platform.get().platform

    e3.os.process.Run(["e3-sandbox", "create", sandbox_dir], output=None)
    with open(os.path.join(sandbox_dir, "test.plan"), "w") as fd:
        fd.write("anod_build('dummyspec')\n")

    specs_source_dir = os.path.join(os.path.dirname(__file__), "specs")
    local_spec_dir = os.path.join(root_dir, "specs")

    e3.fs.sync_tree(specs_source_dir, local_spec_dir)
    create_prolog(local_spec_dir)

    e3.anod.helper.text_replace(
        os.path.join(local_spec_dir, "conf.yaml"),
        [(b"GITURL", git_specs_dir.encode("utf-8"))],
    )

    # Test with local specs
    p = e3.os.process.Run(
        [
            "e3-sandbox",
            "exec",
            "--specs-dir",
            local_spec_dir,
            "--plan",
            os.path.join(sandbox_dir, "test.plan"),
            sandbox_dir,
        ]
    )
    assert "build dummyspec for %s" % platform in p.out
    assert "result: OK" in p.out

    with open(os.path.join(sandbox_dir, "test.plan"), "w") as fd:
        fd.write("anod_build('dummyspec')\n")
        fd.write("anod_test('dummyspec')\n")

    p = e3.os.process.Run(
        [
            "e3-sandbox",
            "exec",
            "--specs-dir",
            local_spec_dir,
            "--plan",
            os.path.join(sandbox_dir, "test.plan"),
            sandbox_dir,
        ]
    )
    assert "build dummyspec for %s" % platform in p.out
    assert "test dummyspec for %s" % platform in p.out
    assert "I am building" in p.out, p.out
    assert "I am testing" in p.out, p.out
    assert p.status == 0

    # Test with git module
    p = e3.os.process.Run(
        [
            "e3-sandbox",
            "exec",
            "--spec-git-url",
            git_specs_dir,
            "--plan",
            os.path.join(sandbox_dir, "test.plan"),
            "--dry-run",
            "--create-sandbox",
            sandbox_dir,
        ]
    )
    assert "build dummyspec for %s" % platform in p.out
    assert "test dummyspec for %s" % platform in p.out


def test_sandbox_source_auto_ignore(git_specs_dir):
    """Test if the new installation do not remove other sources."""
    root_dir = os.getcwd()
    sandbox_dir = os.path.join(root_dir, "sbx")

    e3.os.process.Run(["e3-sandbox", "create", sandbox_dir], output=None)
    with open(os.path.join(sandbox_dir, "test.plan"), "w") as fd:
        fd.write("anod_build('autoignore')\n")

    specs_source_dir = os.path.join(os.path.dirname(__file__), "specs")
    local_spec_dir = os.path.join(root_dir, "specs")

    e3.fs.sync_tree(specs_source_dir, local_spec_dir)
    create_prolog(local_spec_dir)

    e3.anod.helper.text_replace(
        os.path.join(local_spec_dir, "conf.yaml"),
        [(b"GITURL", git_specs_dir.encode("utf-8"))],
    )

    # Test with local specs
    p = e3.os.process.Run(
        [
            "e3-sandbox",
            "exec",
            "--specs-dir",
            local_spec_dir,
            "--plan",
            os.path.join(sandbox_dir, "test.plan"),
            sandbox_dir,
        ]
    )
    assert "found 2" in p.out
    assert "found 1" in p.out
    for subdir in ("3", "3/2", "3/2/1"):
        assert f"found .anod in {subdir}" in p.out
    assert "result: OK" in p.out


def test_sandbox_directory(git_specs_dir):
    """Test if the Source destination exists before prepare_src."""
    root_dir = os.getcwd()
    sandbox_dir = os.path.join(root_dir, "sbx")

    e3.os.process.Run(["e3-sandbox", "create", sandbox_dir], output=None)
    with open(os.path.join(sandbox_dir, "test.plan"), "w") as fd:
        fd.write("anod_build('checkdirectory')\n")

    specs_source_dir = os.path.join(os.path.dirname(__file__), "specs")
    local_spec_dir = os.path.join(root_dir, "specs")

    e3.fs.sync_tree(specs_source_dir, local_spec_dir)
    create_prolog(local_spec_dir)

    e3.anod.helper.text_replace(
        os.path.join(local_spec_dir, "conf.yaml"),
        [(b"GITURL", git_specs_dir.encode("utf-8"))],
    )

    # Test with local specs
    p = e3.os.process.Run(
        [
            "e3-sandbox",
            "exec",
            "--specs-dir",
            local_spec_dir,
            "--plan",
            os.path.join(sandbox_dir, "test.plan"),
            sandbox_dir,
        ]
    )
    assert "found file in destination directory" in p.out


def test_anod_plan(git_specs_dir):
    """Test if sandbox exec works with local specs and a git repo."""
    root_dir = os.getcwd()
    sandbox_dir = os.path.join(root_dir, "sbx")

    # create sandbox
    with_git = e3.os.process.Run(
        ["e3-sandbox", "create", "--spec-git-url", git_specs_dir, sandbox_dir],
        output=None,
    )
    assert with_git.status == 0

    # Test anod build
    platform = e3.platform.Platform.get().platform

    # Build action
    with open(os.path.join(root_dir, "dummy_build.plan"), "w") as fd:
        fd.write("anod_build('dummyspec')")

    command = [
        "e3-sandbox",
        "exec",
        "--plan",
        os.path.join(root_dir, "dummy_build.plan"),
        "--dry-run",
        sandbox_dir,
    ]
    p = e3.os.process.Run(command)
    assert p.status == 0
    assert "build dummyspec for %s" % platform in p.out

    # Install action
    with open(os.path.join(root_dir, "dummy_build.plan"), "w") as fd:
        fd.write("anod_install('dummyspec')")
    p = e3.os.process.Run(command)
    assert p.status == 0
    actions = [
        "download binary of %s.dummyspec" % platform,
        "install dummyspec for %s" % platform,
    ]
    for action in actions:
        assert action in p.out

    # Test action
    with open(os.path.join(root_dir, "dummy_build.plan"), "w") as fd:
        fd.write("anod_test('dummyspec')")
    p = e3.os.process.Run(command)
    assert p.status == 0, p.out
    actions = [
        "checkout dummy-github",
        "create source dummy-src",
        "get source dummy-src",
        "install source dummy-src",
        "test dummyspec for %s" % platform,
    ]
    for action in actions:
        assert action in p.out

    # Test with download source resolver
    command = [
        "e3-sandbox",
        "exec",
        "--plan",
        os.path.join(root_dir, "dummy_build.plan"),
        "--dry-run",
        "--resolver",
        "always_download_source_resolver",
        sandbox_dir,
    ]
    p = e3.os.process.Run(command)
    assert p.status == 0
    actions = [
        "download source dummy-src",
        "get source dummy-src",
        "install source dummy-src",
        "test dummyspec for %s" % platform,
    ]
    for action in actions:
        assert action in p.out


def test_failure_status(git_specs_dir):
    """This test will run sandbox exec with an expected error.

    The error should be propagated throught the DAG and no action
    should be executed once we have the fail
    """
    root_dir = os.getcwd()
    sandbox_dir = os.path.join(root_dir, "sbx")

    with open(os.path.join(root_dir, "test.plan"), "w") as fd:
        fd.write("anod_test('dummyspec')\n")

    specs_source_dir = os.path.join(os.path.dirname(__file__), "specs")
    local_spec_dir = os.path.join(root_dir, "specs")

    e3.fs.sync_tree(specs_source_dir, local_spec_dir)
    create_prolog(local_spec_dir)

    e3.os.process.Run(["e3-sandbox", "create", sandbox_dir], output=None)
    p = e3.os.process.Run(
        [
            "e3-sandbox",
            "-v",
            "exec",
            "--specs-dir",
            local_spec_dir,
            "--plan",
            os.path.join(root_dir, "test.plan"),
            sandbox_dir,
        ]
    )
    # the dag for this plan has 6 actions and thus we need to have
    # 6 failure status (status=failure)
    assert p.out.count("status=failure") == 7, p.out
    assert "GITURL" in p.out, p.out

    # Try with an unsupported VCS
    e3.anod.helper.text_replace(
        os.path.join(local_spec_dir, "conf.yaml"),
        [(b"vcs: git", b"vcs: unsupported-vcs")],
    )
    p = e3.os.process.Run(
        [
            "e3-sandbox",
            "-v",
            "exec",
            "--specs-dir",
            local_spec_dir,
            "--plan",
            os.path.join(root_dir, "test.plan"),
            sandbox_dir,
        ]
    )
    assert "unsupported-vcs vcs type not supported" in p.out, p.out
    assert p.out.count("status=failure") == 7, p.out

    # Also check with a missing repo
    e3.anod.helper.text_replace(
        os.path.join(local_spec_dir, "conf.yaml"), [(b"dummy-github", b"another_repo")]
    )
    p = e3.os.process.Run(
        [
            "e3-sandbox",
            "-v",
            "exec",
            "--specs-dir",
            local_spec_dir,
            "--plan",
            os.path.join(root_dir, "test.plan"),
            sandbox_dir,
        ]
    )
    assert "add_spec: unknown repository dummy-github" in p.out, p.out
    assert p.status == 1


def test_sandbox_user_yaml(git_specs_dir):
    """Verify that user.yaml specs_dir is taken into account."""
    root_dir = os.getcwd()
    sandbox_dir = os.path.join(root_dir, "sbx")

    e3.os.process.Run(["e3-sandbox", "create", sandbox_dir], output=None)
    with open(os.path.join(sandbox_dir, "test.plan"), "w") as fd:
        fd.write("anod_build('dummyspec')\n")

    specs_source_dir = os.path.join(os.path.dirname(__file__), "specs")
    local_spec_dir = os.path.join(root_dir, "myspecs")

    with open(os.path.join(sandbox_dir, "user.yaml"), "w") as fd:
        yaml.dump({"specs_dir": local_spec_dir}, fd)

    e3.fs.sync_tree(specs_source_dir, local_spec_dir)
    create_prolog(local_spec_dir)
    # Test with local specs
    p = e3.os.process.Run(
        [
            "e3-sandbox",
            "-v",
            "exec",
            "--plan",
            os.path.join(sandbox_dir, "test.plan"),
            sandbox_dir,
        ]
    )
    assert "build dummyspec" in p.out
    assert f"using alternate specs dir {local_spec_dir}" in p.out

    sbx = e3.anod.sandbox.SandBox(root_dir=sandbox_dir)

    assert sbx.is_alternate_specs_dir

    if sys.platform == "win32":
        assert sbx.specs_dir.lower() == local_spec_dir.lower()
    else:
        assert sbx.specs_dir == local_spec_dir
