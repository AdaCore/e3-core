from e3.collection.dag import DAG, DAGError, DAGIterator

import pytest


def test_simple_dag():
    d = DAG()
    d.add_vertex("a")
    d.add_vertex("b")
    d.add_vertex("c")
    result = []
    for vertex_id, _ in d:
        result.append(vertex_id)
    result.sort()
    assert result == ["a", "b", "c"]
    assert d.check() is None


def test_add_vertex():
    d = DAG()

    # add_vertex should fail in case a dep does not exist
    with pytest.raises(DAGError):
        d.add_vertex("a", predecessors=["b"])

    # check order of a iteration with simple dependency
    d.add_vertex("b")
    d.add_vertex("a", predecessors=["b"])

    result = []
    for vertex_id, _ in d:
        result.append(vertex_id)
    assert result == ["b", "a"]

    # check that add_vertex fails on attempt to add already existing nodde
    with pytest.raises(DAGError):
        d.add_vertex("a")

    # check update with new dependency
    d.add_vertex("c")
    d.update_vertex("b", predecessors=["c"])

    assert d.get_predecessors("b") == frozenset(["c"])
    assert d.vertex_predecessors == {
        "a": frozenset(["b"]),
        "b": frozenset(["c"]),
        "c": frozenset([]),
    }

    result = []
    for vertex_id, _ in d:
        result.append(vertex_id)
    assert result == ["c", "b", "a"]

    d.update_vertex("a", data="datafora_")
    d.update_vertex("c", data="dataforc_")
    result = []
    compound_data = ""
    for vertex_id, data in d:
        if data is not None:
            compound_data += data
        result.append(vertex_id)
    assert result == ["c", "b", "a"]
    assert compound_data == "dataforc_datafora_"


def test_cycle_detection():
    d = DAG()
    d.add_vertex("a")
    d.add_vertex("b")
    d.update_vertex("a", predecessors=["b"])
    with pytest.raises(DAGError):
        d.update_vertex("b", data="newb", predecessors=["a"])

    # Ensure that DAG is still valid and that previous
    # update_vertex has no effect
    result = []
    for vertex_id, data in d:
        result.append(vertex_id)
        assert data is None
    assert result == ["b", "a"]

    # Force the creation of a cycle
    d.update_vertex("b", data="newb", predecessors=["a"], enable_checks=False)

    # Verify that the cycle is detected
    with pytest.raises(DAGError):
        d.check()

    # Verify that some functions do not hang when a cycle is present
    assert len(d.get_closure("b")) == 2
    assert str(d)
    assert d.as_dot()

    with pytest.raises(DAGError):
        d.reverse_graph()


def test_shortest_path():
    d = DAG()
    d.add_vertex("a")
    d.add_vertex("b")
    d.update_vertex("a", predecessors=["b"])
    d.update_vertex("b", predecessors=["a"], enable_checks=False)
    assert d.shortest_path("a", "a") == ["a", "b", "a"]

    d = DAG()
    d.add_vertex("a")
    d.update_vertex("a", predecessors=["a"], enable_checks=False)
    assert d.shortest_path("a", "a") == ["a", "a"]

    d = DAG()
    d.add_vertex("a")
    d.add_vertex("b", predecessors=["a"])
    d.add_vertex("c", predecessors=["b"])
    d.add_vertex("d", predecessors=["c", "a"])
    assert d.shortest_path("a", "d") == ["a", "d"]
    assert d.shortest_path("d", "a") is None


def test_dag_merge():
    d = DAG()
    d.add_vertex("b")
    d.add_vertex("a", predecessors=["b"])

    d2 = DAG()
    d2.add_vertex("c")
    d2.add_vertex("b", predecessors=["c"])
    d2.add_vertex("a", predecessors=["c"])

    d3 = d | d2
    result = []
    for vertex_id, data in d3:
        result.append(vertex_id)
        assert data is None
    assert result == ["c", "b", "a"]


def test_dag_len():
    d = DAG()
    d.add_vertex("a")
    d.add_vertex("b")
    d.update_vertex("a", predecessors=["b"])
    assert len(d) == 2


def test_dag_str():
    d = DAG()
    d.add_vertex("a")
    d.add_vertex("b")
    d.update_vertex("a", predecessors=["b"])
    assert str(d)


def test_iter_with_busy_state():
    d = DAG()
    d.add_vertex("a")
    d.add_vertex("b", predecessors=["a"])

    it = DAGIterator(d, enable_busy_state=True)
    for nid, _ in it:
        if nid is None:
            it.leave("a")


def test_inexisting():
    d = DAG()
    d.add_vertex("a")
    assert "a" in d
    d.update_vertex("a", data="NOT B", predecessors=["b"], enable_checks=False)
    assert "b" not in d
    assert d["a"] == "NOT B"
    with pytest.raises(DAGError):
        d.check()


def test_cycle():
    d = DAG()
    d.add_vertex("a")
    d.add_vertex("b")
    d.update_vertex("a", predecessors=["b"])
    d.add_vertex("c", predecessors=["b"])
    d.update_vertex("b", predecessors=["c"], enable_checks=False)
    with pytest.raises(DAGError):
        d.check()

    with pytest.raises(DAGError):
        d.get_context("b")


def test_reverse_dag():
    d = DAG()
    d.add_vertex("a")
    d.add_vertex("b", predecessors=["a"])
    d.add_vertex("c", predecessors=["b"])
    d.add_vertex("d", predecessors=["c"])

    it = DAGIterator(d)
    assert [k for k, _ in it] == ["a", "b", "c", "d"]

    reverse_d = d.reverse_graph()
    reverse_it = DAGIterator(reverse_d)
    assert [k for k, _ in reverse_it] == ["d", "c", "b", "a"]


def test_dot():
    d = DAG()
    d.add_vertex("a")
    d.add_vertex("b", predecessors=["a"])
    assert '"b" -> "a"' in d.as_dot()


def test_pruned_dag():
    d = DAG()
    d.add_vertex("a")
    d.add_vertex("a1")
    d.add_vertex("a2")
    d.add_vertex("b", predecessors=["a", "a1"])
    d.add_vertex("c", predecessors=["b", "a2"])
    d.add_vertex("d", predecessors=["c"])
    d.add_tag("d", "tag")

    def f(dg, node):
        if node in ("b", "c"):
            return True
        return False

    d2 = d.prune(f)

    for node, _ in d2:
        preds = d2.get_predecessors(node)
        if node == "d":
            assert len(preds) == 3
            assert "a" in preds
            assert "a1" in preds
            assert "a2" in preds
            assert d2.get_tag("d") == "tag"
        elif node.startswith("a"):
            assert len(preds) == 0
        else:
            raise AssertionError("invalid node")

    # By default prune ensure we keep context unchanged.
    # If we add a tag to 'b' (that would be suppressed) then we expect a
    # DAGError
    d.add_tag("b", "b_tag")
    with pytest.raises(DAGError):
        d.prune(f)

    # In that last test, check that no error is raised but that tag are
    # preserved
    d4 = d.prune(f, preserve_context=False)
    assert d4.get_tag("d") == "tag"


def test_tagged_dag():
    r"""Test add_tag/get_tag/get_context.

    With the following DAG::

               A
              / \
             B   C*
           /  \ /
          D*   E
         / \  / \
        F   G    H*
    """
    d = DAG()
    d.add_vertex("a")
    d.add_vertex("b", predecessors=["a"])
    d.add_vertex("c", predecessors=["a"])
    d.add_vertex("d", predecessors=["b"])
    d.add_vertex("e", predecessors=["b", "c"])
    d.add_vertex("f", predecessors=["d"])
    d.add_vertex("g", predecessors=["d", "e"])
    d.add_vertex("h", predecessors=["e"])

    d.add_tag("c", data="tagc")
    d.add_tag("d", data="tagd")
    d.add_tag("h", data="tagh")

    assert d.get_tag("a") is None
    assert d.get_tag("b") is None
    assert d.get_tag("c") == "tagc"
    assert d.get_tag("e") is None
    assert d.get_tag("h") == "tagh"

    assert d.get_context("d") == [(0, "d", "tagd")]
    assert d.get_context("g") == [(1, "d", "tagd"), (2, "c", "tagc")]
    assert d.get_context("f") == [(1, "d", "tagd")]
    assert d.get_context("b") == []
    assert d.get_context("a") == []
    assert d.get_context("c") == [(0, "c", "tagc")]
    assert d.get_context("e") == [(1, "c", "tagc")]
    assert d.get_context("h") == [(0, "h", "tagh")]

    assert d.get_context("e", reverse_order=True) == [(1, "h", "tagh")]
    assert d.get_context("h", reverse_order=True) == [(0, "h", "tagh")]
    assert d.get_context("a", reverse_order=True) == [
        (1, "c", "tagc"),
        (2, "d", "tagd"),
        (3, "h", "tagh"),
    ]

    assert d.get_context("a", reverse_order=True) == [
        (1, "c", "tagc"),
        (2, "d", "tagd"),
        (3, "h", "tagh"),
    ]

    assert d.get_context(vertex_id="a", max_distance=2, reverse_order=True) == [
        (1, "c", "tagc"),
        (2, "d", "tagd"),
    ]

    assert d.get_context(vertex_id="a", max_element=2, reverse_order=True) == [
        (1, "c", "tagc"),
        (2, "d", "tagd"),
    ]
