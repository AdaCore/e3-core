import pytest
from typing import Any

from e3.collection.tree import Tree, TreeException


def test_single_node_tree() -> None:
    t = Tree()
    t.create_node(tag="foo", identifier="foo")
    foo_node = t.get_node("foo")
    assert foo_node is not None
    assert foo_node.is_leaf


def test_duplicate_identifier() -> None:
    t = Tree()
    t.create_node(tag="foo", identifier="foo")
    # A duplicate identifier should trigger an exception
    with pytest.raises(TreeException, match=r"Identifier .+ already exists in tree"):
        t.create_node(tag="bar", identifier="foo")


def test_get_node() -> None:
    t = Tree()
    # Tree is empty, get_node() should always return None
    assert t.get_node("blah") is None
    t.create_node(tag="foo", identifier="foo")
    t.create_node(tag="bar", identifier="bar", parent="foo")
    t.create_node(tag="baz", identifier="baz", parent="bar")
    t.create_node(tag="bax", identifier="bax", parent="bar")
    bar_node = t.get_node("bar")
    assert bar_node is not None
    assert bar_node.children == [t.get_node("baz"), t.get_node("bax")]


def test_node_removal() -> None:
    t = Tree()
    t.create_node(tag="foo", identifier="foo")
    t.create_node(tag="bar", identifier="bar", parent="foo")
    t.create_node(tag="baz", identifier="baz", parent="bar")
    t.create_node(tag="bax", identifier="bax", parent="bar")
    t.remove_node("bar")
    # All nodes except foo should be gone
    assert t.get_node("bar") is None
    assert t.get_node("baz") is None
    assert t.get_node("bax") is None
    assert t.get_node("foo") is not None
    # Attempting to remove a non-existing node should trigger an exception
    with pytest.raises(
        TreeException,
        match=r"Identifier .+ cannot be removed \(does not exist in tree\)",
    ):
        t.remove_node("bar")
    # Removing the root node should work
    t.remove_node("foo")
    assert t.get_node("foo") is None


def test_missing_parent() -> None:
    t = Tree()
    # Setting a parent for the root node should trigger an exception
    with pytest.raises(TreeException, match=r"Parent should be None for root node"):
        t.create_node(tag="foo", identifier="foo", parent="bar")

    t.create_node(tag="foo", identifier="foo")
    # Using a non-existing parent should trigger an exception
    with pytest.raises(
        TreeException,
        match=r"Parent .+ is not in tree",
    ):
        t.create_node(tag="bar", identifier="bar", parent="baz")


def test_show_empty_tree(capsys: Any) -> None:
    t = Tree()
    t.show()

    captured_output = capsys.readouterr()
    assert captured_output.out == ""


def test_show_full_tree(capsys: Any) -> None:
    t = Tree()
    t.create_node(tag="foo", identifier="foo")
    t.create_node(tag="bar", identifier="bar", parent="foo")
    t.create_node(tag="baz", identifier="baz", parent="bar")
    t.create_node(tag="bax", identifier="bax", parent="bar")
    t.create_node(tag="bay", identifier="bay", parent="bax")
    t.show()

    captured_output = capsys.readouterr()
    expected_output = """\
foo
└── bar
    ├── bax
    │   └── bay
    └── baz
"""

    assert captured_output.out == expected_output
