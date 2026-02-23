from pathlib import Path
import os

import e3.diff
import e3.fs
import e3.archive
import pytest


def test_non_existing() -> None:
    """Check that a non existing file will be considered as null string."""
    assert e3.diff.diff("foo1", "foo2") == ""


def test_patch() -> None:
    test_dir = Path(os.path.dirname(__file__))
    file_to_patch = test_dir / "file_to_patch.orig.txt"
    file_after_patch = test_dir / "file_to_patch.new.txt"
    file_after_patch2 = test_dir / "file_to_patch.new2.txt"
    file_patch = test_dir / "patch.txt"
    file_patch2 = test_dir / "patch2.txt"

    current_dir = Path.cwd()

    e3.fs.cp(file_to_patch, current_dir)
    e3.diff.patch(str(file_patch), str(current_dir))

    with Path("file_to_patch.orig.txt").open() as fd:
        output = fd.readlines()

    with file_after_patch.open() as fd:
        expected = fd.readlines()

    # By default empty line, leading and trailing whitespaces are ignored
    assert e3.diff.diff([*expected, ""], output) == ""
    assert e3.diff.diff([" " + line + " " for line in expected], output) == ""
    assert e3.diff.diff(expected, output, ignore_white_chars=False) == ""

    # we can also ignore specific pattern
    assert "-to ignore" in e3.diff.diff([*expected, "to ignore"], output)
    assert e3.diff.diff([*expected, "to ignore"], output, ignore="ig.*re") == ""

    e3.fs.cp(file_patch2, current_dir)
    e3.diff.patch(
        "patch2.txt", str(current_dir), discarded_files=["dummy_to_patch.new.txt"]
    )
    assert e3.diff.diff("file_to_patch.orig.txt", str(file_after_patch2)) == ""

    e3.fs.cp(file_patch2, current_dir)
    e3.diff.patch(
        "patch2.txt", str(current_dir), discarded_files=lambda x: x.endswith("new.txt")
    )


def test_patch_ignore_all(caplog) -> None:
    test_dir = Path(os.path.dirname(__file__))
    file_to_patch = test_dir / "file_to_patch.orig.txt"
    file_patch2 = test_dir / "patch2.txt"

    current_dir = Path.cwd()

    e3.fs.cp(file_to_patch, current_dir)
    e3.fs.cp(file_patch2, current_dir)
    with pytest.raises(e3.diff.EmptyDiffError):
        e3.diff.patch("patch2.txt", str(current_dir), discarded_files=lambda _x: True)


def test_discarded() -> None:
    test_dir = Path(os.path.dirname(__file__))
    orig = test_dir / "data.txt"
    new = test_dir / "data_new.txt"
    current_dir = Path.cwd()

    e3.fs.cp(orig, current_dir)
    e3.fs.cp(test_dir / "data_patch_universal.txt", current_dir)
    e3.diff.patch(
        "data_patch_universal.txt",
        str(current_dir),
        discarded_files=["*file_to_patch*"],
    )

    with new.open() as fd:
        expected = fd.read()
    with Path("data.txt").open() as fd:
        result = fd.read()
    assert result == expected

    e3.fs.cp(orig, current_dir)
    e3.fs.cp(test_dir / "data_patch_contextual.txt", current_dir)
    e3.diff.patch(
        "data_patch_universal.txt",
        str(current_dir),
        discarded_files=["*file_to_patch*"],
    )

    with new.open() as fd:
        expected = fd.read()
    with Path("data.txt").open() as fd:
        result = fd.read()
    assert result == expected

    e3.fs.cp(orig, current_dir)


def test_patch_invalid() -> None:
    test_dir = Path(os.path.dirname(__file__))
    file_to_patch = test_dir / "file_to_patch.orig.txt"
    file_patch2 = test_dir / "patch2.txt"

    current_dir = Path.cwd()

    e3.fs.cp(file_to_patch, current_dir)
    e3.fs.cp(file_patch2, current_dir)

    with Path("patch2.txt").open("a") as f:
        f.write("invalid")

    with pytest.raises(e3.diff.DiffError):
        e3.diff.patch("patch2.txt", str(current_dir))


def test_patch_git_format() -> None:
    test_dir = Path(os.path.dirname(__file__))
    file_to_patch = test_dir / "git_file.txt"
    patch_file = test_dir / "git_diff.patch"

    cwd = Path.cwd()

    e3.fs.cp(file_to_patch, cwd)
    e3.fs.cp(patch_file, cwd)

    e3.diff.patch("git_diff.patch", str(cwd))
    with (cwd / "git_file.txt").open() as fd:
        content = fd.read()
    assert "That's nice it's working !" in content


def test_patch_git_format_ignore() -> None:
    test_dir = Path(os.path.dirname(__file__))
    file_to_patch = test_dir / "git_file.txt"
    patch_file = test_dir / "*.patch"

    cwd = Path.cwd()

    e3.fs.cp(file_to_patch, cwd)
    e3.fs.cp(patch_file, cwd)

    e3.diff.patch("git_diff.patch", str(cwd), discarded_files=["a/*"])
    with (cwd / "git_file.txt").open() as fd:
        content = fd.read()
    assert "That's nice it's working !" in content

    e3.fs.cp(file_to_patch, cwd)
    with pytest.raises(e3.diff.EmptyDiffError):
        e3.diff.patch("git_diff.patch", str(cwd), discarded_files=["git_file.txt"])

    with (cwd / "git_file.txt").open() as fd:
        content = fd.read()
    assert "That's nice it's working !" not in content

    e3.fs.cp(file_to_patch, cwd)
    e3.diff.patch("git_diff_show.patch", str(cwd))
    with (cwd / "git_file.txt").open() as fd:
        content = fd.read()
    assert "That's nice it's working !" in content

    e3.fs.cp(file_to_patch, cwd)
    e3.diff.patch("git_diff_no_prefix.patch", str(cwd))
    with (cwd / "git_file.txt").open() as fd:
        content = fd.read()
    assert "That's nice it's working !" in content


def test_patch_git_with_headers() -> None:
    test_dir = os.path.dirname(__file__)
    test_dir = Path(os.path.dirname(__file__))
    patch_file = test_dir / "git_patch_with_header"

    cwd = Path.cwd()

    e3.fs.cp(patch_file, cwd)

    e3.diff.patch("git_patch_with_header", str(cwd))
    assert os.path.isfile("file1")
    assert os.path.isfile("file2")

    e3.fs.rm("file1")
    e3.fs.rm("file2")
    e3.diff.patch("git_patch_with_header", str(cwd), discarded_files=["file1"])
    assert not os.path.isfile("file1")
    assert os.path.isfile("file2")

    e3.fs.rm("file1")
    e3.fs.rm("file2")
    e3.diff.patch("git_patch_with_header", str(cwd), discarded_files=["file2"])
    assert os.path.isfile("file1")
    assert not os.path.isfile("file2")

    e3.fs.rm("file1")
    e3.fs.rm("file2")
    with pytest.raises(e3.diff.EmptyDiffError):
        e3.diff.patch("git_patch_with_header", str(cwd), discarded_files=["file*"])

    assert not os.path.isfile("file1")
    assert not os.path.isfile("file2")


def test_patch_git_binary() -> None:
    test_dir = Path(os.path.dirname(__file__))
    patch_file = test_dir / "unicorn.patch"
    cwd = Path.cwd()
    e3.fs.cp(patch_file, cwd)
    e3.diff.patch("unicorn.patch", str(cwd))
    assert os.path.isfile("unicorn.zip")
    e3.archive.unpack_archive("unicorn.zip", dest=".")
    assert os.path.isfile("unicorn.txt")
