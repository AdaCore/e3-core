import e3.hash
import e3.fs
import e3.diff
import os
import tempfile
import pytest
import sys


def test_cp():
    tf = tempfile.NamedTemporaryFile(delete=False)
    tf.close()
    try:
        e3.fs.cp(__file__, tf.name)
        assert e3.hash.sha1(__file__) == e3.hash.sha1(tf.name)
    finally:
        e3.fs.rm(tf.name)

    tempd = tempfile.mkdtemp()
    try:
        a = os.path.join(tempd, 'a')
        a1 = os.path.join(a, 'a1')
        b1 = os.path.join(a, 'b', 'b1')

        e3.fs.mkdir(a)
        e3.fs.echo_to_file(a1, 'a1')
        e3.fs.mkdir(os.path.join(a, 'b'))
        e3.fs.echo_to_file(b1, 'b1')

        dest = os.path.join(tempd, 'dest')
        e3.fs.mkdir(dest)
        e3.fs.cp(a, dest, recursive=True)
        assert os.path.exists(os.path.join(dest, 'a', 'a1'))
        assert os.path.exists(os.path.join(dest, 'a', 'b', 'b1'))

        dest2 = os.path.join(tempd, 'dest2')

        with pytest.raises(e3.fs.FSError) as err:
            e3.fs.cp('*.non_existing', dest2)
            assert "can't find files matching" in err

        with pytest.raises(e3.fs.FSError) as err:
            e3.fs.cp([a1, b1], dest2)
            assert 'target should be a directory' in err

        e3.fs.mkdir(dest2)
        e3.fs.cp([a1, b1], dest2)
        assert os.path.exists(os.path.join(dest2, 'a1'))
        assert os.path.exists(os.path.join(dest2, 'b1'))

        dest3 = os.path.join(tempd, 'dest3')
        e3.fs.mkdir(dest3)
        e3.fs.cp(a, dest3, copy_attrs=False, recursive=True)
        e3.fs.cp(a1, dest3, copy_attrs=False)

        assert os.path.exists(os.path.join(dest3, 'a', 'a1'))
        assert os.path.exists(os.path.join(dest3, 'a', 'b', 'b1'))
        assert os.path.exists(os.path.join(dest3, 'a1'))

    finally:
        e3.fs.rm(tempd, True)


def test_echo():
    tf = tempfile.NamedTemporaryFile(delete=False)
    tf.close()
    try:
        e3.fs.echo_to_file(tf.name, 'foo')
        e3.fs.echo_to_file(tf.name, 'foo')
        e3.fs.echo_to_file(tf.name, 'bar', append=True)
        with open(tf.name) as foobar_f:
            assert foobar_f.read() == 'foobar'

        e3.fs.echo_to_file(tf.name, ['line1', 'line2'])
        with open(tf.name) as fd:
            assert fd.read().strip() == 'line1\nline2'
    finally:
        e3.fs.rm(tf.name)


def test_find():
    d = os.path.dirname(__file__)
    parent_d = os.path.dirname(d)

    result = {os.path.abspath(f) for f in e3.fs.find(parent_d)}
    assert os.path.abspath(__file__) in result
    assert os.path.abspath(d) not in result

    result = e3.fs.find(parent_d, include_dirs=True, include_files=False)
    result = {os.path.abspath(f) for f in result}
    assert os.path.abspath(d) in result
    assert os.path.abspath(__file__) not in result

    result = e3.fs.find(parent_d, include_dirs=True, include_files=True)
    result = {os.path.abspath(f) for f in result}
    assert os.path.abspath(d) in result
    assert os.path.abspath(__file__) in result


def test_tree_state():
    import time
    tempd = tempfile.mkdtemp()
    try:
        d = os.path.dirname(os.path.dirname(__file__))
        state = e3.fs.get_filetree_state(d)
        assert isinstance(state, str)

        e3.fs.sync_tree(d, os.path.join(tempd))
        state2 = e3.fs.get_filetree_state(tempd)
        assert state != state2

        state3 = e3.fs.get_filetree_state(tempd)
        assert state2 == state3

        # To ensure that file system resolution is not hidding
        # changes
        time.sleep(2)

        e3.os.fs.touch(os.path.join(tempd, 'toto'))
        state4 = e3.fs.get_filetree_state(tempd)
        assert state4 != state3
    finally:
        e3.fs.rm(tempd, True)


@pytest.mark.skipif(sys.platform != 'win32', reason='test using symlink')
def test_sync_tree_with_symlinks():
    tempd = tempfile.mkdtemp()
    try:
        a = os.path.join(tempd, 'a')
        b = os.path.join(tempd, 'b')
        m1 = os.path.join(tempd, 'm1')
        m2 = os.path.join(tempd, 'm2')
        m3 = os.path.join(tempd, 'm3')

        e3.fs.mkdir(m1)
        e3.fs.mkdir(m2)
        e3.fs.mkdir(m3)

        with open(a, 'w') as f:
            f.write('a')

        with open(b, 'w') as f:
            f.write('b')

        e3.fs.cp(a, os.path.join(m1, 'c'))
        os.symlink(b, os.path.join(m2, 'c'))
        os.symlink(m2, os.path.join(m3, 'c'))

        # we start with m2/c -> b
        # so m2/c and b points to the same content
        assert e3.diff.diff(
            b,
            os.path.join(m2, 'c')) == ''
        assert e3.diff.diff(
            b,
            os.path.join(m1, 'c'))
        e3.fs.sync_tree(m1, m2)

        # after the sync tree m1/c = m2/c
        assert e3.diff.diff(
            os.path.join(m1, 'c'),
            os.path.join(m2, 'c')) == ''

        # and m2/c is not a symlink anymore so does not
        # have the same content as b
        assert e3.diff.diff(
            b,
            os.path.join(m2, 'c'))

        # we start with m3/c -> m2
        assert os.path.exists(os.path.join(m3, 'c', 'c'))
        e3.fs.sync_tree(m1, m3)
        # after the sync tree m1/c = m3/c
        assert e3.diff.diff(
            os.path.join(m1, 'c'),
            os.path.join(m3, 'c')) == ''

        # and m3/c is not a link to m2
        assert not os.path.exists(os.path.join(m3, 'c', 'c'))
        assert os.path.exists(os.path.join(m2, 'c'))

    finally:
        e3.fs.rm(tempd, True)
