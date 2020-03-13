import os

import e3.diff
import e3.fs

import pytest


def test_non_existing():
    """Check that a non existing file will be considered as null string."""
    assert e3.diff.diff("foo1", "foo2") == ""


def test_patch():
    test_dir = os.path.dirname(__file__)
    file_to_patch = os.path.join(test_dir, "file_to_patch.orig.txt")
    file_after_patch = os.path.join(test_dir, "file_to_patch.new.txt")
    file_after_patch2 = os.path.join(test_dir, "file_to_patch.new2.txt")
    file_patch = os.path.join(test_dir, "patch.txt")
    file_patch2 = os.path.join(test_dir, "patch2.txt")

    current_dir = os.getcwd()

    e3.fs.cp(file_to_patch, current_dir)
    e3.diff.patch(file_patch, current_dir)

    with open("file_to_patch.orig.txt") as fd:
        output = fd.readlines()

    with open(file_after_patch) as fd:
        expected = fd.readlines()

    # By default empty line, leading and trailing whitespaces are ignored
    assert e3.diff.diff(expected + [""], output) == ""
    assert e3.diff.diff([" " + l + " " for l in expected], output) == ""
    assert e3.diff.diff(expected, output, ignore_white_chars=False) == ""

    # we can also ignore specific pattern
    assert "-to ignore" in e3.diff.diff(expected + ["to ignore"], output)
    assert e3.diff.diff(expected + ["to ignore"], output, ignore="ig.*re") == ""

    e3.fs.cp(file_patch2, current_dir)
    e3.diff.patch("patch2.txt", current_dir, discarded_files=["dummy_to_patch.new.txt"])
    assert e3.diff.diff("file_to_patch.orig.txt", file_after_patch2) == ""

    e3.fs.cp(file_patch2, current_dir)
    e3.diff.patch(
        "patch2.txt", current_dir, discarded_files=lambda x: x.endswith("new.txt")
    )


def test_patch_ignore_all(caplog):
    test_dir = os.path.dirname(__file__)
    file_to_patch = os.path.join(test_dir, "file_to_patch.orig.txt")
    file_patch2 = os.path.join(test_dir, "patch2.txt")

    current_dir = os.getcwd()

    e3.fs.cp(file_to_patch, current_dir)
    e3.fs.cp(file_patch2, current_dir)
    e3.diff.patch("patch2.txt", current_dir, discarded_files=lambda x: True)

    assert "All patch2.txt content has been discarded" in caplog.text


def test_discarded():
    test_dir = os.path.dirname(__file__)
    orig = os.path.join(test_dir, "data.txt")
    new = os.path.join(test_dir, "data_new.txt")
    current_dir = os.getcwd()

    e3.fs.cp(orig, current_dir)
    e3.fs.cp(os.path.join(test_dir, "data_patch_universal.txt"), current_dir)
    e3.diff.patch(
        "data_patch_universal.txt", current_dir, discarded_files=["*file_to_patch*"]
    )

    with open(new, "r") as fd:
        expected = fd.read()
    with open("data.txt", "r") as fd:
        result = fd.read()
    assert result == expected

    e3.fs.cp(orig, current_dir)
    e3.fs.cp(os.path.join(test_dir, "data_patch_contextual.txt"), current_dir)
    e3.diff.patch(
        "data_patch_universal.txt", current_dir, discarded_files=["*file_to_patch*"]
    )

    with open(new, "r") as fd:
        expected = fd.read()
    with open("data.txt", "r") as fd:
        result = fd.read()
    assert result == expected

    e3.fs.cp(orig, current_dir)


def test_patch_invalid():
    test_dir = os.path.dirname(__file__)
    file_to_patch = os.path.join(test_dir, "file_to_patch.orig.txt")
    file_patch2 = os.path.join(test_dir, "patch2.txt")

    current_dir = os.getcwd()

    e3.fs.cp(file_to_patch, current_dir)
    e3.fs.cp(file_patch2, current_dir)

    with open("patch2.txt", "a") as f:
        f.write("invalid")

    with pytest.raises(e3.diff.DiffError):
        e3.diff.patch("patch2.txt", current_dir)
