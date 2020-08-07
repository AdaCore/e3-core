import os

import e3.diff
import e3.fs

import pytest


def test_non_existing():
    """Check that a non existing file will be considered as null string."""
    assert e3.diff.diff("foo1", "foo2") == ""


def test_patch():
    test_dir = os.path.dirname(__file__)
    files_to_patch = [
        os.path.join(test_dir, "file_to_patch.orig.txt"),
        os.path.join(test_dir, "data.txt"),
    ]
    files_after_patch = [
        os.path.join(test_dir, "file_to_patch.new.txt"),
        os.path.join(test_dir, "data_new.txt"),
    ]
    patch_file = os.path.join(test_dir, "data_patch_universal.txt")

    current_dir = os.getcwd()

    for file_tp in files_to_patch:
        e3.fs.cp(file_tp, current_dir)

    e3.diff.patch(patch_file, current_dir)

    for file_tp, file_after in zip(files_to_patch, files_after_patch):
        local_file = os.path.basename(file_tp)
        with open(local_file) as fd:
            output = fd.readlines()

        with open(file_after) as fd:
            expected = fd.readlines()

        # By default empty line, leading and trailing whitespaces are ignored
        assert e3.diff.diff(expected + [""], output) == ""
        assert e3.diff.diff([" " + line + " " for line in expected], output) == ""
        assert e3.diff.diff(expected, output, ignore_white_chars=False) == ""

        # we can also ignore specific pattern
        assert "-to ignore" in e3.diff.diff(expected + ["to ignore"], output)
        assert e3.diff.diff(expected + ["to ignore"], output, ignore="ig.*re") == ""


def test_empty_patch():
    """test patch containing a new empty file."""
    test_dir = os.path.dirname(__file__)
    patch_file = os.path.join(test_dir, "git_patch_with_newfile.patch")
    file_to_patch = os.path.join(test_dir, "file_to_patch.orig.txt")
    file_after_first_patch = os.path.join(test_dir, "file_to_patch.new.txt")
    current_dir = os.getcwd()

    e3.fs.cp(file_to_patch, current_dir)
    e3.diff.patch(patch_file, current_dir)
    assert e3.diff.diff("file_to_patch.orig.txt", file_after_first_patch) == ""

    # we verify that an empty file has been created
    assert os.path.exists(os.path.join(current_dir, "new_file"))


def test_patch_ignore_all(caplog):
    test_dir = os.path.dirname(__file__)
    file_to_patch = os.path.join(test_dir, "file_to_patch.orig.txt")
    file_patch2 = os.path.join(test_dir, "data_patch_with_dummy.txt")

    current_dir = os.getcwd()

    e3.fs.cp(file_to_patch, current_dir)
    e3.fs.cp(file_patch2, current_dir)
    e3.diff.patch(
        "data_patch_with_dummy.txt", current_dir, discarded_files=lambda x: True
    )

    assert "All data_patch_with_dummy.txt content has been discarded" in caplog.text


def test_patch_discarded():
    """Test discard functionality."""
    test_dir = os.path.dirname(__file__)
    patch_file_dummy = os.path.join(test_dir, "data_patch_with_dummy.txt")
    file_after_first_patch = os.path.join(test_dir, "file_to_patch.new.txt")
    file_after_second_patch = os.path.join(test_dir, "file_to_patch.new2.txt")

    current_dir = os.getcwd()

    # we replace the file with a copy after being patched
    e3.fs.cp(
        file_after_first_patch, os.path.join(current_dir, "file_to_patch.orig.txt")
    )

    e3.diff.patch(
        patch_file_dummy, current_dir, discarded_files=["dummy_to_patch.new.txt"]
    )
    assert e3.diff.diff("file_to_patch.orig.txt", file_after_second_patch) == ""

    # we replace the file with a copy after being patched
    e3.fs.cp(
        file_after_first_patch, os.path.join(current_dir, "file_to_patch.orig.txt")
    )

    e3.diff.patch(
        patch_file_dummy, current_dir, discarded_files=lambda x: x.endswith("new.txt")
    )
    assert e3.diff.diff("file_to_patch.orig.txt", file_after_second_patch) == ""


def test_patch_discarded_glob():
    """Test discard functionality with glob patterns."""
    test_dir = os.path.dirname(__file__)
    orig = os.path.join(test_dir, "data.txt")
    new = os.path.join(test_dir, "data_new.txt")
    current_dir = os.getcwd()

    e3.fs.cp(orig, current_dir)
    e3.fs.cp(os.path.join(test_dir, "data_patch_universal.txt"), current_dir)
    e3.diff.patch(
        "data_patch_universal.txt", current_dir, discarded_files=["*file_to_patch*"]
    )

    with open(new) as fd:
        expected = fd.read()
    with open("data.txt") as fd:
        result = fd.read()
    assert result == expected


def test_patch_invalid():
    test_dir = os.path.dirname(__file__)
    file_to_patch = os.path.join(test_dir, "file_to_patch.orig.txt")
    file_patch2 = os.path.join(test_dir, "data_patch_with_dummy.txt")

    current_dir = os.getcwd()

    e3.fs.cp(file_to_patch, current_dir)
    e3.fs.cp(file_patch2, current_dir)

    with open("data_patch_with_dummy.txt", "a") as f:
        f.write("invalid")

    with pytest.raises(e3.diff.DiffError):
        e3.diff.patch("data_patch_with_dummy.txt", current_dir)
