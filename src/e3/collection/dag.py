"""Implementation of Direct Acyclic Graphs."""


from __future__ import annotations

from itertools import chain
from typing import TYPE_CHECKING

from e3.error import E3Error

if TYPE_CHECKING:
    from typing import (
        Any,
        Callable,
        Dict,
        FrozenSet,
        Hashable,
        List,
        Iterator,
        Optional,
        Sequence,
        Set,
        Tuple,
    )

    VertexID = Hashable


class DAGError(E3Error):
    pass


class DAGIterator:

    NOT_VISITED = 0
    BUSY = 1
    VISITED = 2

    def __init__(self, dag: DAG, enable_busy_state: bool = False):
        """Initialize DAG iterator.

        :param dag: the dag on which iteration is done
        :param enable_busy_state: used to implement topological parallel
            iteration. When False, a vertex has only 2 possible states: VISITED
            or NOT_VISITED. When true, calling the next() function on the
            iteratior puts the element in 'BUSY' state. It will only be moved
            to 'Visited' once calling the 'leave()' method.
        """
        self.dag = dag
        self.non_visited = set(self.dag.vertex_data.keys())
        self.states = {k: self.NOT_VISITED for k in list(self.dag.vertex_data.keys())}
        self.enable_busy_state = enable_busy_state

        # Compute number of non visited predecessors for each node.
        # Doing this computation in advance enable faster
        # iteration overall (simplify conditions in next_element)
        self.pred_number = {k: len(v) for k, v in self.dag.vertex_predecessors_items()}

    def __iter__(self) -> DAGIterator:
        return self

    def __next__(self) -> Tuple[None, None] | Tuple[VertexID, Any]:
        """Retrieve next_element with with_predecessors=False.

        The intermediate function is needed in Python 3.x
        """
        vertex_id, data, _ = self.next_element()
        if vertex_id is None:
            return (None, None)
        return (vertex_id, data)

    def next_element(self,) -> Tuple[Optional[VertexID], Any, FrozenSet[VertexID]]:
        """Retrieve next element in topological order.

        :return: a vertex id, data, predecessors. (None, None, frozenset()) is
            returned if no element is available).
        """
        if not self.non_visited:
            raise StopIteration

        # Retrieve the first vertex for which all the predecessors have been
        # visited
        result = next((k for k in self.non_visited if self.pred_number[k] == 0), None)

        if result is None:
            if not self.enable_busy_state:
                for node in self.non_visited:
                    minimal_cycle = self.dag.shortest_path(node, node)
                    if minimal_cycle is not None:
                        raise DAGError(
                            "cycle detected: %s"
                            % " -> ".join(
                                [str(vertex_id) for vertex_id in minimal_cycle]
                            )
                        )
                raise DAGError("cycle detected (unknown error)")

            # No vertex is ready to be visited
            return None, None, frozenset()

        # Remove the vertex from the "non_visited_list" and when
        # enable_busy_state, mark the vertex as BUSY, mark it VISITED
        # otherwise.
        if self.enable_busy_state:
            self.states[result] = self.BUSY
        else:
            self.states[result] = self.VISITED
            # Update the number of non visited predecessors
            for k in self.dag.get_successors(result):
                self.pred_number[k] -= 1

        self.non_visited.discard(result)

        return (result, self.dag.vertex_data[result], self.dag.get_predecessors(result))

    def leave(self, vertex_id: VertexID) -> None:
        """Switch element from BUSY to VISITED state.

        :param vertex_id: the vertex to leave
        """
        assert self.states[vertex_id] == self.BUSY
        self.states[vertex_id] = self.VISITED
        # Update the number of non visited predecessors
        for k in self.dag.get_successors(vertex_id):
            self.pred_number[k] -= 1


class DAG:
    """Represent a Directed Acyclic Graph.

    :ivar vertex_data: a dictionary containing all vertex data
        indexed by vertex id
    :vartype vertex_data: dict
    :ivar tags: a dictionary containing "tags" associated with
        a vertex data, indexed by vertex id
    """

    def __init__(self) -> None:
        """Initialize a DAG."""
        self.vertex_data: Dict[VertexID, Any] = {}
        self.tags: Dict[VertexID, Any] = {}

        self.__vertex_predecessors: Dict[VertexID, FrozenSet[VertexID]] = {}
        self.__vertex_successors: Dict[VertexID, FrozenSet[VertexID]] = {}
        self.__has_cycle: Optional[bool] = None
        self.__cached_topological_order: Optional[List[Tuple[VertexID, Any]]] = None

    def reset_caches(self) -> None:
        """Reset caches for DAG properties (cycle and cached topological order).

        This is a mandatory step when changing DAG edges.
        """
        self.__has_cycle = None
        self.__cached_topological_order = None

    @property
    def vertex_predecessors(self) -> Dict[VertexID, FrozenSet[VertexID]]:
        """Return predecessors.

        Meant only for backward compatibility. Use vertex_predecessors_items.

        :return: a dictionary containing the list of predecessors for each
            vertex, indexed by vertex id
        """
        # We're doing a copy of the __vertex_predecessors dictionary
        # to avoid external modifications
        return dict(self.__vertex_predecessors)

    def vertex_predecessors_items(
        self,
    ) -> Iterator[Tuple[VertexID, FrozenSet[VertexID]]]:
        """Return predecessors.

        :return: a list of (vertex id, predecessors)
        """
        return iter(self.__vertex_predecessors.items())

    def get_predecessors(self, vertex_id: VertexID) -> FrozenSet[VertexID]:
        """Get set of predecessors for a given vertex."""
        return self.__vertex_predecessors.get(vertex_id, frozenset())

    def set_predecessors(
        self, vertex_id: VertexID, predecessors: FrozenSet[VertexID]
    ) -> None:
        """Set predecessors for a given vertex.

        Invalidate the global dictionary of vertex successors.
        """
        self.__vertex_predecessors[vertex_id] = predecessors
        # Reset successors and cycle check results which are now invalid
        self.__vertex_successors = {}
        self.reset_caches()

    def get_successors(self, vertex_id: VertexID) -> FrozenSet[VertexID]:
        """Get set of successors for a given vertex.

        If the global dictionary of vertex successors has not been
        computed or if it has been invalidated then recompute it.
        """
        if self.__vertex_successors == {}:
            successors: Dict[VertexID, Set[VertexID]] = {
                k: set() for k in self.__vertex_predecessors
            }
            for pred_k, pred_v in self.__vertex_predecessors.items():
                for el in pred_v:
                    successors[el].add(pred_k)
            # Use frozenset to prevent the modification of successors
            for succ_k, succ_v in successors.items():
                self.__vertex_successors[succ_k] = frozenset(succ_v)

        return self.__vertex_successors.get(vertex_id, frozenset())

    def add_tag(self, vertex_id: VertexID, data: Any) -> None:
        """Tag a vertex.

        :param vertex_id: ID of the vertex to tag
        :param data: tag content
        """
        self.tags[vertex_id] = data

    def get_tag(self, vertex_id: VertexID) -> Any:
        """Retrieve a tag associated with a vertex.

        :param vertex_id: ID of the vertex
        :return: tag content
        """
        return self.tags.get(vertex_id)

    def get_context(
        self,
        vertex_id: VertexID,
        max_distance: Optional[int] = None,
        max_element: Optional[int] = None,
        reverse_order: bool = False,
    ) -> List[Tuple[int, VertexID, Any]]:
        r"""Get tag context.

        Returns the list of predecessors tags along with their vertex id and
        the distance between the given vertex and the tag. On each predecessors
        branch the first tag in returned. So for the following graph::


                A*
               / \
              B   C*
             / \   \
            D   E*  F

        where each node with a * are tagged

        get_context(D) will return (2, A, <tag A>)
        get_context(E) will return (0, E, <tag E>)
        get_context(F) will return (1, C, <tag C>)

        When using reverse_order=True, get_context will follow successors
        instead of predecessors.

        get_context(B, reverse_order=True) will return (1, E, <tag E>)

        :param vertex_id: ID of the vertex
        :param max_distance: do not return resultsh having a distance higher
            than ``max_distance``
        :param max_element: return only up-to ``max_element`` elements
        :param reverse_order: when True follow successors instead of
            predecessors
        :return: a list of tuple (distance:int, tagged vertex id, tag content)
        """
        self.check()

        def get_next(vid: VertexID) -> FrozenSet[VertexID]:
            """Get successors or predecessors.

            :param vid: vertex id
            """
            if reverse_order:
                result = self.get_successors(vid)
            else:
                result = self.get_predecessors(vid)
            return result

        visited: Set[VertexID] = set()
        tags = []
        distance = 0
        node_tag = self.get_tag(vertex_id)
        if node_tag is not None:
            tags.append((distance, vertex_id, node_tag))
            return tags

        closure = get_next(vertex_id)
        closure_len = len(closure)

        while True:
            distance += 1
            if max_distance is not None and distance > max_distance:
                return tags
            for n in closure - visited:
                visited.add(n)

                n_tag = self.get_tag(n)
                if n_tag is not None:
                    tags.append((distance, n, n_tag))

                    if max_element is not None and len(tags) == max_element:
                        return tags
                else:
                    # Search tag in vertex predecessors
                    closure |= get_next(n)

            if len(closure) == closure_len:
                break
            closure_len = len(closure)
        return tags

    def add_vertex(
        self,
        vertex_id: VertexID,
        data: Any = None,
        predecessors: Optional[Sequence[VertexID]] = None,
    ) -> None:
        """Add a new vertex into the DAG.

        Note that this function always checks that there is no cycle in the
        current DAG. If you prefer to insert all your node first and then
        do the check at the end use update_vertex calls followed by a call
        to check.

        :param vertex_id: the name of the vertex
        :param data: data for the vertex.
        :param predecessors: list of predecessors (vertex ids) or None
        :raise: DAGError if cycle is detected or else vertex already exist
        """
        if vertex_id in self.vertex_data:
            raise DAGError(
                message=f"vertex {vertex_id} already exist", origin="DAG.add_vertex"
            )
        self.update_vertex(vertex_id, data, predecessors)

    def update_vertex(
        self,
        vertex_id: VertexID,
        data: Any = None,
        predecessors: Optional[
            Sequence[VertexID] | Set[VertexID] | FrozenSet[VertexID]
        ] = None,
        enable_checks: bool = True,
    ) -> None:
        """Update a vertex into the DAG.

        :param vertex_id: the name of the vertex
        :param data: data for the vertex. If None and vertex already exist
            then data value is preserved
        :param predecessors: list of predecessors (vertex ids) or None. If
            vertex already exists predecessors are added to the original
            predecessors
        :param enable_checks: if False check that all predecessors exists and
            that no cycle is introduce is not perform (for performance)
        :raise: DAGError if cycle is detected
        """
        if predecessors is None:
            vertex_predecessors: FrozenSet[VertexID] = frozenset()
        else:
            vertex_predecessors = frozenset(predecessors)

        if enable_checks:
            # Before doing changes ensure that the DAG is already valid
            self.check()

            non_existing_predecessors = [
                k for k in vertex_predecessors if k not in self.vertex_data
            ]
            if non_existing_predecessors:
                raise DAGError(
                    message="predecessor on non existing vertices {}".format(
                        ", ".join([str(nid) for nid in non_existing_predecessors])
                    ),
                    origin="DAG.update_vertex",
                )

        if vertex_id not in self.vertex_data:
            self.set_predecessors(vertex_id, vertex_predecessors)
            self.vertex_data[vertex_id] = data
        else:
            previous_predecessors = self.get_predecessors(vertex_id)
            self.set_predecessors(
                vertex_id, previous_predecessors | vertex_predecessors
            )

            if enable_checks:
                # Will raise DAGError if a cycle is created
                if vertex_id in self.get_closure(vertex_id):
                    minimal_cycle = self.shortest_path(vertex_id, vertex_id)
                    if TYPE_CHECKING:
                        assert minimal_cycle is not None
                    self.set_predecessors(vertex_id, previous_predecessors)
                    raise DAGError(
                        message="cannot update vertex ({} create a cycle: {})".format(
                            vertex_id, " -> ".join([str(vid) for vid in minimal_cycle])
                        ),
                        origin="DAG.update_vertex",
                    )

            if data is not None:
                self.vertex_data[vertex_id] = data

        if enable_checks:
            self.__cached_topological_order = None
        else:
            # DAG modified without cycle checks, discard cached result
            self.reset_caches()

    def shortest_path(
        self, source: VertexID, target: VertexID
    ) -> Optional[List[VertexID]]:
        """Compute the shortest path between two vertices of the DAG.

        :param source: vertex id of the source
        :param target: vertex id of the target. If target is equal to source
            then the algorithm try to find the shortest cycle
        :return: a list of vertex. If there is no path between two nodes then
            return None
        """
        # We use the Dikjstra algorithm to compute the shortest path.
        # Note that this is a slight variation so that the algorithm
        # can be used to compute shortest cycle on a given node.

        # The maximum distance between two vertices is len(DAG) - 1. Thus
        # len(DAG) can be our infinite distance. As when target and source
        # are equals we might add an additional fake node, increase it by one.
        infinite = len(self.vertex_data) + 1

        # Keep track of minimal distance between vertices and the sources
        dist: Dict[Optional[VertexID], int] = {k: infinite for k in self.vertex_data}

        # Keep track of the minimum distance
        prev: Dict[Optional[VertexID], Optional[VertexID]] = {
            k: None for k in self.vertex_data
        }

        # Set of non visited vertices
        unvisited: Set[Optional[VertexID]] = set(self.vertex_data)

        # The only known distance at startup
        dist[target] = 0

        path_source: Optional[VertexID] = source

        if path_source == target:
            # If source is equal to target, default dikjstra algorithm does
            # not work. Add a fake node and use it as target. When iterating
            # on predecessors replace all occurences of sources to that node.
            # If we find a path between that node and the source, it means
            # we have our shortest cycle.
            dist[None] = infinite
            prev[None] = None
            unvisited.add(None)
            path_source = None

        while unvisited:
            u = min(unvisited, key=lambda x: dist[x])
            unvisited.remove(u)

            # We have found our shortest path, so break
            if u == path_source:
                break
            elif u is None:
                continue

            for u_pred in self.get_predecessors(u):
                # Handle cycle detection case.
                if path_source is None and u_pred == target:
                    v = None
                else:
                    v = u_pred

                alt = dist[u] + 1
                if alt < dist[v]:
                    dist[v] = alt
                    prev[v] = u

        if dist[path_source] == infinite:
            # No path exist between source and target (or no cycle).
            return None
        else:
            result: List[Optional[VertexID]] = [path_source]
            while prev[result[-1]] is not None:
                result.append(prev[result[-1]])

            # In case of cycle detection the first node is None which
            # is in reality our source node.
            if path_source is None:
                result[0] = target
            return result

    def check(self) -> None:
        """Check for cycles and inexisting nodes.

        :raise: DAGError if the DAG is not valid
        """
        # Noop if check already done
        if self.__has_cycle is False:
            return
        elif self.__has_cycle:
            raise DAGError(
                message="this DAG contains at least one cycle", origin="DAG.check"
            )
        # First check predecessors validity
        for node, preds in self.__vertex_predecessors.items():
            if len([k for k in preds if k not in self.vertex_data]) > 0:
                self.__has_cycle = True
                raise DAGError(
                    message=f"invalid nodes in predecessors of {node}",
                    origin="DAG.check",
                )
        # raise DAGError if cycle
        topological_order = []
        try:
            for vertex_id, data in DAGIterator(self):
                if vertex_id is not None:
                    topological_order.append((vertex_id, data))
        except DAGError:
            self.__has_cycle = True
            raise
        else:
            self.__has_cycle = False
            self.__cached_topological_order = topological_order

    def get_closure(self, vertex_id: VertexID) -> Set[VertexID]:
        """Retrieve closure of predecessors for a vertex.

        :param vertex_id: the vertex to inspect
        :return: a set of vertex_id
        """
        closure: Set[VertexID] = set()
        to_visit = set(self.get_predecessors(vertex_id))

        while len(to_visit) > 0:
            next_visit: Set[VertexID] = set()
            for n in to_visit:
                closure.add(n)
                next_visit |= self.get_predecessors(n)

            to_visit = next_visit - closure

        return closure

    def reverse_graph(self, enable_checks: bool = True) -> DAG:
        """Compute the reverse DAG.

        :param enable_checks: whether to check that "self" is valid (no cycle)
        :return: the reverse DAG (edge inverted)
        """
        result = DAG()

        # Copy the tags to the reverse DAG
        result.tags = self.tags

        # Note that we don't need to enable checks during this operation
        # as the reverse graph of a DAG is still a DAG (no cycles).
        for node, predecessors in self.__vertex_predecessors.items():
            result.update_vertex(node, data=self.vertex_data[node], enable_checks=False)
            for p in predecessors:
                result.update_vertex(p, predecessors=[node], enable_checks=False)

        # The reversed topological order for "self" is a valid topological
        # order for "result".
        result.__has_cycle = self.__has_cycle
        result.__cached_topological_order = (
            None
            if self.__cached_topological_order is None
            else list(reversed(self.__cached_topological_order))
        )

        if enable_checks:
            try:
                result.check()
            except DAGError:
                # Check detected
                self.__has_cycle = True
                raise
            else:
                self.__has_cycle = False

        return result

    def __iter__(self) -> Iterator[Tuple[VertexID, Any]]:
        return (
            iter(DAGIterator(self))
            if self.__cached_topological_order is None
            else iter(self.__cached_topological_order)
        )

    def __contains__(self, vertex_id: VertexID) -> bool:
        """Check if a vertex is present in the DAG."""
        return vertex_id in self.vertex_data

    def __getitem__(self, vertex_id: VertexID) -> Any:
        """Get data associated with a vertex."""
        return self.vertex_data[vertex_id]

    def __or__(self, other: DAG) -> DAG:
        """Merge two dags."""
        assert isinstance(other, DAG)

        result = DAG()

        # First add vertices and then update predecessors. The two step
        # procedure is needed because predecessors should exist.
        for nid in self.vertex_data:
            result.add_vertex(nid)

        for nid in other.vertex_data:
            result.update_vertex(nid)

        # Update predecessors
        for nid in self.vertex_data:
            result.update_vertex(nid, self.vertex_data[nid], self.get_predecessors(nid))

        for nid in other.vertex_data:
            result.update_vertex(
                nid, other.vertex_data[nid], other.get_predecessors(nid)
            )

        # Make sure that no cycle are created the merged DAG.
        result.check()
        return result

    def as_dot(self) -> str:
        """Return a Graphviz graph representation of the graph.

        :return: the dot source file
        """
        result = ["digraph G {", 'rankdir="LR";']
        for vertex in self.vertex_data:
            result.append(f'"{vertex}"')
        for vertex, predecessors in self.__vertex_predecessors.items():
            for predecessor in predecessors:
                result.append(f'"{vertex}" -> "{predecessor}"')
        result.append("}")
        return "\n".join(result)

    def prune(
        self, fun: Callable[[DAG, VertexID], bool], preserve_context: bool = True
    ) -> DAG:
        """Create a pruned graph.

        :param fun: function that return True whenever a node should be
            pruned. The function receive as parameter the dag and the node id
        :param preserve_context: if True ensure that context is preserved
            (i.e: that calls to get_context will return the same value for
            both current graph and pruned graph). This means that any attempt
            to remove a node containing a tag will result in a DAGError.
        :return: a new DAG
        """
        result = DAG()

        # Used to maintain the new list of predecessors
        pruned_node_predecessors: Dict[VertexID, Set[VertexID]] = {}

        for node, data in self:
            # The new list of predecessors is the union of predecessors of
            # pruned predecessors and the other predecessors.
            if TYPE_CHECKING:
                assert node is not None
            predecessors = set(
                chain(
                    *[pruned_node_predecessors[k] for k in self.get_predecessors(node)]
                )
            )

            if fun(self, node):
                # Check if node can pruned
                if node in self.tags and preserve_context:
                    raise DAGError(f"suppressing {node} impact context")

                # Node is pruned keep track of its predecessors
                pruned_node_predecessors[node] = predecessors
            else:
                # Node is kept. Note that no check is needed as pruning
                # operation cannot introduce a cycle.
                result.update_vertex(node, data, predecessors, enable_checks=False)
                pruned_node_predecessors[node] = {node}
                if node in self.tags:
                    result.add_tag(node, self.tags[node])
        return result

    def __len__(self) -> int:
        return len(self.vertex_data)

    def __str__(self) -> str:
        result = []
        for vertex, predecessors in self.__vertex_predecessors.items():
            if predecessors:
                result.append(
                    "{} -> {}".format(vertex, ", ".join(str(p) for p in predecessors))
                )
            else:
                result.append(f"{vertex} -> (none)")
        return "\n".join(result)
