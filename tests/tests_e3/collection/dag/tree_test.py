import pytest

from e3.collection.dag import DAG


def test_empty_tree():
    t = DAG()
    assert t.as_tree() == ""


def test_single_node_tree():
    t = DAG()
    t.add_vertex("foo")
    assert t.as_tree() == "foo"


def test_multi_node_tree():
    t = DAG()
    t.add_vertex("foo")
    t.add_vertex("bar", predecessors=["foo"])
    t.add_vertex("baz", predecessors=["foo", "bar"])
    t.add_vertex("baf", predecessors=["baz", "bar"])

    expected_tree = """\
foo
├── bar
│   ├── baf
│   └── baz
│       └── baf
└── baz
    └── baf"""

    assert t.as_tree() == expected_tree


def test_name_key_tree():
    t = DAG()
    t.add_vertex("foo1", data={"name": "foo-one"})
    t.add_vertex("foo2", data={"name": "foo-two"}, predecessors=["foo1"])
    t.add_vertex("foo3", data={"name": "foo-three"}, predecessors=["foo2"])

    expected_tree = """\
foo-one
└── foo-two
    └── foo-three"""

    assert t.as_tree(name_key="name") == expected_tree

    # If we give a non-existing name key, it should error out
    with pytest.raises(AssertionError):
        t.as_tree(name_key="non-existing")
