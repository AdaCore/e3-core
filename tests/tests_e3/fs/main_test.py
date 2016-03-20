import e3.hash
import e3.fs
import os
import tempfile


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
        e3.fs.mkdir(a)
        e3.fs.echo_to_file(os.path.join(a, 'a1'), 'a1')
        e3.fs.mkdir(os.path.join(a, 'b'))
        e3.fs.echo_to_file(os.path.join(a, 'b', 'b1'), 'b1')
        dest = os.path.join(tempd, 'dest')
        e3.fs.mkdir(dest)
        e3.fs.cp(a, dest, recursive=True)
        assert os.path.exists(os.path.join(dest, 'a', 'b', 'b1'))
        assert os.path.exists(os.path.join(dest, 'a', 'a1'))
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
    finally:
        e3.fs.rm(tf.name)


def test_find():
    assert os.path.abspath(__file__) in {
        os.path.abspath(f) for f in e3.fs.find(os.path.dirname(__file__))}


def test_tree_state():
    # Just check that get_filetree_state returns a string
    assert isinstance(
        e3.fs.get_filetree_state(os.path.dirname(__file__)),
        str)
