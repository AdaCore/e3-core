import e3.diff
import e3.fs
import os
import tempfile


def test_non_existing():
    """Check that a non existing file will be considered as null string"""
    assert e3.diff.diff('foo1', 'foo2') == ''


def test_patch():
    test_dir = os.path.dirname(__file__)
    file_to_patch = os.path.join(test_dir, 'file_to_patch.orig.txt')
    file_after_patch = os.path.join(test_dir, 'file_to_patch.new.txt')
    file_after_patch2 = os.path.join(test_dir, 'file_to_patch.new2.txt')
    file_patch = os.path.join(test_dir, 'patch.txt')
    file_patch2 = os.path.join(test_dir, 'patch2.txt')

    tempd = tempfile.mkdtemp()
    try:
        e3.fs.cp(file_to_patch, tempd)
        e3.diff.patch(file_patch, tempd)

        with open(os.path.join(tempd, 'file_to_patch.orig.txt')) as fd:
            output = fd.readlines()

        with open(file_after_patch) as fd:
            expected = fd.readlines()

        assert e3.diff.diff(expected, output) == ''

        e3.diff.patch(file_patch2, tempd,
                      discarded_files=['dummy_to_patch.new.txt'])
        assert e3.diff.diff(os.path.join(tempd, 'file_to_patch.orig.txt'),
                            file_after_patch2) == ''
    finally:
        e3.fs.rm(tempd, True)
