"""Tests for e3.anod package."""

from pathlib import Path

import e3.anod.error
import e3.anod.package
from e3.fs import mkdir, rm
from e3.os.fs import touch

import pytest


def test_source_builder_default_prepare_src() -> None:
    """Test SourceBuilder with the default prepare_src function."""
    sb = e3.anod.package.SourceBuilder(
        name="a-src", fullname=lambda: "a-src.tgz", checkout=["a-git"]
    )

    assert sb.fullname() == "a-src.tgz"

    current_dir = Path.cwd()
    a_wd = current_dir / "a_wd"

    # create a fake working dir of a-git
    mkdir(a_wd)
    touch(a_wd / "a_file")

    a_dest = current_dir / "a_dest"
    mkdir(a_dest)

    sb.prepare_src(repos={"a-git": {"working_dir": a_wd}}, dest=a_dest)

    assert (a_dest / "a_file").exists()

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


def test_source_builder_custom_prepare_src() -> None:
    """Test SourceBuilder with a custom prepare_src function."""

    def prepare_src(repos, dest) -> None:
        touch(Path(dest, "my_generated_source_file"))

    sb = e3.anod.package.SourceBuilder(
        name="b-src",
        fullname=lambda: "b-src.tgz",
        checkout=["b-git"],
        prepare_src=prepare_src,
    )

    sb.prepare_src(None, str(Path.cwd()))
    assert Path("my_generated_source_file").exists()


def test_apply_patch() -> None:
    """Test SourceBuilder.apply_patch handling."""
    sb = e3.anod.package.SourceBuilder(
        name="d-src", fullname=lambda: "d-src.tgz", checkout=["d-git"]
    )

    with Path("my_patch").open("w") as f:
        f.write(
            "--- a_file\t2017-04-11 16:34:44.000000000 +0200\n"
            "+++ a_file\t2017-04-11 16:34:40.000000000 +0200\n"
            "@@ -0,0 +1 @@\n"
            "+new line\n"
        )

    current_dir = str(Path.cwd())
    touch("a_file")
    sb.apply_patch(None, "my_patch", current_dir)

    with Path("a_file").open() as f:
        assert f.read().strip() == "new line"

    sb = e3.anod.package.SourceBuilder(
        name="d-src",
        fullname=lambda: "d-src.tgz",
        prepare_src=lambda _x, _y: None,
        checkout=["d-git", "e-git"],
    )

    with pytest.raises(e3.anod.error.AnodError) as err:
        sb.apply_patch(None, "my_patch", current_dir)
    assert "no apply_patch" in str(err)

    sb = e3.anod.package.SourceBuilder(
        name="d-src",
        fullname=lambda: "d-src.tgz",
        prepare_src=lambda _x, _y: None,
        checkout=["d-git", "e-git"],
        apply_patch=lambda _x, _y, _z: 42,
    )

    assert sb.apply_patch(None, None, None) == 42

    # Thirdparty source builders set the default patch command by default

    rm("a_file")
    touch("a_file")
    tsb = e3.anod.package.ThirdPartySourceBuilder(name="third-src.tgz")
    tsb.apply_patch(None, "my_patch", current_dir)

    with Path("a_file").open() as f:
        assert f.read().strip() == "new line"
