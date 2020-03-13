import os

import e3.anod.error
import e3.anod.package
from e3.fs import mkdir, rm
from e3.os.fs import touch

import pytest


def test_source_builder_default_prepare_src():
    """Test SourceBuilder with the default prepare_src function."""
    sb = e3.anod.package.SourceBuilder(
        name="a-src", fullname=lambda: "a-src.tgz", checkout=["a-git"]
    )

    assert sb.fullname() == "a-src.tgz"

    current_dir = os.getcwd()
    a_wd = os.path.join(current_dir, "a_wd")

    # create a fake working dir of a-git
    mkdir(a_wd)
    touch(os.path.join(a_wd, "a_file"))

    a_dest = os.path.join(current_dir, "a_dest")
    mkdir(a_dest)

    sb.prepare_src(repos={"a-git": {"working_dir": a_wd}}, dest=a_dest)

    assert os.path.exists(os.path.join(a_dest, "a_file"))

    # Check that this is working only when we have one repo
    for checkout in ([], ["a-git", "b-git"]):
        sb_err = e3.anod.package.SourceBuilder(
            name="a-src", fullname=lambda: "a-src.tgz", checkout=checkout
        )

        with pytest.raises(e3.anod.error.SpecError):
            assert sb_err.prepare_src

    # Check ThirdParty prepare_src is None
    tp = e3.anod.package.ThirdPartySourceBuilder(name="unmanaged-src")
    assert tp.prepare_src is None


def test_source_builder_custom_prepare_src():
    """Test SourceBuilder with a custom prepare_src function."""

    def prepare_src(repos, dest):
        touch(os.path.join(dest, "my_generated_source_file"))

    sb = e3.anod.package.SourceBuilder(
        name="b-src",
        fullname=lambda: "b-src.tgz",
        checkout=["b-git"],
        prepare_src=prepare_src,
    )

    sb.prepare_src(None, os.getcwd())
    assert os.path.exists("my_generated_source_file")


def test_apply_patch():
    """Test SourceBuilder.apply_patch handling."""
    sb = e3.anod.package.SourceBuilder(
        name="d-src", fullname=lambda: "d-src.tgz", checkout=["d-git"]
    )

    with open("my_patch", "w") as f:
        f.write(
            "--- a_file\t2017-04-11 16:34:44.000000000 +0200\n"
            "+++ a_file\t2017-04-11 16:34:40.000000000 +0200\n"
            "@@ -0,0 +1 @@\n"
            "+new line\n"
        )

    current_dir = os.getcwd()
    touch("a_file")
    sb.apply_patch(None, "my_patch", current_dir)

    with open("a_file") as f:
        assert f.read().strip() == "new line"

    sb = e3.anod.package.SourceBuilder(
        name="d-src",
        fullname=lambda: "d-src.tgz",
        prepare_src=lambda x, y: None,
        checkout=["d-git", "e-git"],
    )

    with pytest.raises(e3.anod.error.AnodError) as err:
        sb.apply_patch(None, "my_patch", current_dir)
    assert "no apply_patch" in str(err)

    sb = e3.anod.package.SourceBuilder(
        name="d-src",
        fullname=lambda: "d-src.tgz",
        prepare_src=lambda x, y: None,
        checkout=["d-git", "e-git"],
        apply_patch=lambda x, y, z: 42,
    )

    assert sb.apply_patch(None, None, None) == 42

    # Thirdparty source builders set the default patch command by default

    rm("a_file")
    touch("a_file")
    tsb = e3.anod.package.ThirdPartySourceBuilder(name="third-src.tgz")
    tsb.apply_patch(None, "my_patch", current_dir)

    with open("a_file") as f:
        assert f.read().strip() == "new line"
