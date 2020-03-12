"""Implementation of Direct Acyclic Graphs."""


from itertools import chain
from e3.error import E3Error


class DAGError(E3Error):
    pass


class DAGIterator(object):

    NOT_VISITED = 0
    BUSY = 1
    VISITED = 2

    def __init__(self, dag, enable_busy_state=False):
        """Initialize DAG iterator.

        :param dag: the dag on which iteration is done
        :type dag: DAG
        :param enable_busy_state: used to implement topological parallel
            iteration. When False, a vertex has only 2 possible states: VISITED
            or NOT_VISITED. When true, calling the next() function on the
            iteratior puts the element in 'BUSY' state. It will only be moved
            to 'Visited' once calling the 'leave()' method.
        :type enable_busy_state: bool
        """
        self.dag = dag
        self.non_visited = set(self.dag.vertex_data.keys())
        self.states = {k: self.NOT_VISITED for k in list(self.dag.vertex_data.keys())}
        self.enable_busy_state = enable_busy_state

        # Compute number of non visited predecessors for each node.
        # Doing this computation in advance enable faster
        # iteration overall (simplify conditions in next_element)
        self.pred_number = {k: len(v) for k, v in self.dag.vertex_predecessors_items()}

    def __iter__(self):
        return self

    def __next__(self):
        """Retrieve next_element with with_predecessors=False.

        The intermediate function is needed in Python 3.x

        :rtype: (None, None) | (str, T)
        """
        return self.next_element()[0:2]

    def next_element(self):
        """Retrieve next element in topological order.

        :return: a tuple id, data, predecessors. (None, None, None) is
            returned if no element is available).
        :rtype: (str, T, list[str]) | (None, None, None)
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
                            "cycle detected: %s" % " -> ".join(minimal_cycle)
                        )
                raise DAGError("cycle detected (unknown error)")

            # No vertex is ready to be visited
            return None, None, None

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

    def leave(self, vertex_id):
        """Switch element from BUSY to VISITED state.

        :param vertex_id: the vertex to leave
        :type vertex_id: str
        """
        assert self.states[vertex_id] == self.BUSY
        self.states[vertex_id] = self.VISITED
        # Update the number of non visited predecessors
        for k in self.dag.get_successors(vertex_id):
            self.pred_number[k] -= 1


class DAG(object):
    """Represent a Directed Acyclic Graph.

    :ivar vertex_data: a dictionary containing all vertex data
        indexed by vertex id
    :vartype vertex_data: dict
    :ivar tags: a dictionary containing "tags" associated with
        a vertex data, indexed by vertex id
    """

    def __init__(self):
        """Initialize a DAG."""
        self.vertex_data = {}
        self.tags = {}

        self.__vertex_predecessors = {}
        self.__vertex_successors = {}
        self.__has_cycle = None

    @property
    def vertex_predecessors(self):
        """Return predecessors.

        Meant only for backward compatibility. Use vertex_predecessors_items.

        :return: a dictionary containing the list of predecessors for each
            vertex, indexed by vertex id
        :rtype: dict
        """
        # We're doing a copy of the __vertex_predecessors dictionary
        # to avoid external modifications
        return dict(self.__vertex_predecessors)

    def vertex_predecessors_items(self):
        """Return predecessors.

        :return: a list of (vertex id, predecessors)
        :rtype: dict
        """
        return iter(self.__vertex_predecessors.items())

    def get_predecessors(self, vertex_id):
        """Get set of predecessors for a given vertex."""
        return self.__vertex_predecessors.get(vertex_id, frozenset())

    def set_predecessors(self, vertex_id, predecessors):
        """Set predecessors for a given vertex.

        Invalidate the global dictionary of vertex successors.
        """
        self.__vertex_predecessors[vertex_id] = predecessors
        # Reset successors and cycle check results which are now invalid
        self.__vertex_successors = {}
        self.__has_cycle = None

    def get_successors(self, vertex_id):
        """Get set of successors for a given vertex.

        If the global dictionary of vertex successors has not been
        computed or if it has been invalidated then recompute it.
        """
        if self.__vertex_successors == {}:
            self.__vertex_successors = {k: set() for k in self.__vertex_predecessors}
            for k, v in self.__vertex_predecessors.items():
                for el in v:
                    self.__vertex_successors[el].add(k)
            # Use frozenset to prevent the modification of successors
            for k, v in self.__vertex_successors.items():
                self.__vertex_successors[k] = frozenset(v)

        return self.__vertex_successors.get(vertex_id, frozenset())

    def add_tag(self, vertex_id, data):
        """Tag a vertex.

        :param vertex_id: ID of the vertex to tag
        :param data: tag content
        """
        self.tags[vertex_id] = data

    def get_tag(self, vertex_id):
        """Retrieve a tag associated with a vertex.

        :param vertex_id: ID of the vertex
        :return: tag content
        """
        return self.tags.get(vertex_id)

    def get_context(
        self, vertex_id, max_distance=None, max_element=None, reverse_order=False
    ):
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
        :type max_distance: int | None
        :param max_element: return only up-to ``max_element`` elements
        :type max_element: int | None
        :param reverse_order: when True follow successors instead of
            predecessors
        :type reverse_order: bool
        :return: a list of tuple (distance:int, tagged vertex id, tag content)
        :rtype: list[tuple]
        """
        self.check()

        def get_next(vid):
            """Get successors or predecessors.

            :param vid: vertex id
            """
            if reverse_order:
                result = self.get_successors(vid)
            else:
                result = self.get_predecessors(vid)
            return result

        visited = set()
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

    def add_vertex(self, vertex_id, data=None, predecessors=None):
        """Add a new vertex into the DAG.

        :param vertex_id: the name of the vertex
        :type vertex_id: collections.Hashable
        :param data: data for the vertex.
        :type data: object
        :param predecessors: list of predecessors (vertex ids) or None
        :type predecessors: list[str] | None
        :raise: DAGError if cycle is detected or else vertex already exist
        """
        if vertex_id in self.vertex_data:
            raise DAGError(
                message="vertex %s already exist" % vertex_id, origin="DAG.add_vertex"
            )
        self.update_vertex(vertex_id, data, predecessors)

    def update_vertex(
        self, vertex_id, data=None, predecessors=None, enable_checks=True
    ):
        """Update a vertex into the DAG.

        :param vertex_id: the name of the vertex
        :type vertex_id: collections.Hashable
        :param data: data for the vertex. If None and vertex already exist
            then data value is preserved
        :type data: object
        :param predecessors: list of predecessors (vertex ids) or None. If
            vertex already exists predecessors are added to the original
            predecessors
        :type predecessors: list[str] | None
        :param enable_checks: if False check that all predecessors exists and
            that no cycle is introduce is not perform (for performance)
        :type enable_checks: bool
        :raise: DAGError if cycle is detected
        """
        if predecessors is None:
            predecessors = frozenset()
        else:
            predecessors = frozenset(predecessors)

        if enable_checks:
            # Before doing changes ensure that the DAG is already valid
            self.check()

            non_existing_predecessors = [
                k for k in predecessors if k not in self.vertex_data
            ]
            if non_existing_predecessors:
                raise DAGError(
                    message="predecessor on non existing vertices %s"
                    % ", ".join(non_existing_predecessors),
                    origin="DAG.update_vertex",
                )

        if vertex_id not in self.vertex_data:
            self.set_predecessors(vertex_id, predecessors)
            self.vertex_data[vertex_id] = data
        else:
            previous_predecessors = self.get_predecessors(vertex_id)
            self.set_predecessors(vertex_id, previous_predecessors | predecessors)

            if enable_checks:
                # Will raise DAGError if a cycle is created
                if vertex_id in self.get_closure(vertex_id):
                    minimal_cycle = self.shortest_path(vertex_id, vertex_id)
                    self.set_predecessors(vertex_id, previous_predecessors)
                    raise DAGError(
                        message="cannot update vertex (%s create a cycle: %s)"
                        % (vertex_id, " -> ".join(minimal_cycle)),
                        origin="DAG.update_vertex",
                    )

            if data is not None:
                self.vertex_data[vertex_id] = data

        if not enable_checks:
            # DAG modified without cycle checks, discard cached result
            self.__has_cycle = None

    def shortest_path(self, source, target):
        """Compute the shortest path between two vertices of the DAG.

        :param source: vertex id of the source
        :param target: vertex id of the target. If target is equal to source
            then the algorithm try to find the shortest cycle
        :return: a list of vertex. If there is no path between two nodes then
            return None
        :rtype: list[str] | None
        """
        # We use the Dikjstra algorithm to compute the shortest path.
        # Note that this is a slight variation so that the algorithm
        # can be used to compute shortest cycle on a given node.

        # The maximum distance between two vertices is len(DAG) - 1. Thus
        # len(DAG) can be our infinite distance. As when target and source
        # are equals we might add an additional fake node, increase it by one.
        infinite = len(self.vertex_data) + 1

        # Keep track of minimal distance between vertices and the sources
        dist = {k: infinite for k in self.vertex_data}

        # Keep track of the minimum distance
        prev = {k: None for k in self.vertex_data}

        # Set of non visited vertices
        unvisited = {k for k in self.vertex_data}

        # The only known distance at startup
        dist[target] = 0

        if source == target:
            # If source is equal to target, default dikjstra algorithm does
            # not work. Add a fake node and use it as target. When iterating
            # on predecessors replace all occurences of sources to that node.
            # If we find a path between that node and the source, it means
            # we have our shortest cycle.
            dist[None] = infinite
            prev[None] = None
            unvisited.add(None)
            source = None

        while unvisited:
            u = min(unvisited, key=lambda x: dist[x])
            unvisited.remove(u)

            # We have found our shortest path, so break
            if u == source:
                break

            for v in self.get_predecessors(u):
                # Handle cycle detection case.
                if source is None and v == target:
                    v = None

                alt = dist[u] + 1
                if alt < dist[v]:
                    dist[v] = alt
                    prev[v] = u

        if dist[source] == infinite:
            # No path exist between source and target (or no cycle).
            return None
        else:
            result = [source]
            while prev[result[-1]] is not None:
                result.append(prev[result[-1]])

            # In case of cycle detection the first node is None which
            # is in reality our source node.
            if source is None:
                result[0] = target
            return result

    def check(self):
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
                    message="invalid nodes in predecessors of %s" % node,
                    origin="DAG.check",
                )
        # raise DAGError if cycle
        try:
            for _ in DAGIterator(self):
                pass
        except DAGError:
            self.__has_cycle = True
            raise
        else:
            self.__has_cycle = False

    def get_closure(self, vertex_id):
        """Retrieve closure of predecessors for a vertex.

        :param vertex_id: the vertex to inspect
        :type vertex_id: collections.Hashable
        :return: a set of vertex_id
        :rtype: set(collections.Hashable)
        """
        visited = set()
        closure = self.get_predecessors(vertex_id)
        closure_len = len(closure)

        while True:
            for n in closure - visited:
                visited.add(n)

                closure |= self.get_predecessors(n)

            if len(closure) == closure_len:
                break
            closure_len = len(closure)
        return closure

    def reverse_graph(self):
        """Compute the reverse DAG.

        :return: the reverse DAG (edge inverted)
        :rtype: DAG
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
        try:
            result.check()
        except DAGError:
            # Check detected
            self.__has_cycle = True
            raise
        else:
            # No cycle in the DAG
            self.__has_cycle = False
        return result

    def __iter__(self):
        return DAGIterator(self)

    def __contains__(self, vertex_id):
        """Check if a vertex is present in the DAG."""
        return vertex_id in self.vertex_data

    def __getitem__(self, vertex_id):
        """Get data associated with a vertex."""
        return self.vertex_data[vertex_id]

    def __or__(self, other):
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

    def as_dot(self):
        """Return a Graphviz graph representation of the graph.

        :return: the dot source file
        :rtype: str
        """
        result = ["digraph G {", 'rankdir="LR";']
        for vertex in self.vertex_data:
            result.append('"%s"' % vertex)
        for vertex, predecessors in self.__vertex_predecessors.items():
            for predecessor in predecessors:
                result.append('"%s" -> "%s"' % (vertex, predecessor))
        result.append("}")
        return "\n".join(result)

    def prune(self, fun, preserve_context=True):
        """Create a pruned graph.

        :param fun: function that return True whenever a node should be
            pruned. The function receive as parameter the dag and the node id
        :type fun: (DAG, str) -> bool
        :param preserve_context: if True ensure that context is preserved
            (i.e: that calls to get_context will return the same value for
             both current graph and pruned graph). This means that any attempt
            to remove a node containing a tag will result in a DAGError.
        :type preserve_context: bool
        :return: a new DAG
        :rtype: DAG
        """
        result = DAG()

        # Used to maintain the new list of predecessors
        pruned_node_predecessors = {}

        for node, data in self:
            # The new list of predecessors is the union of predecessors of
            # pruned predecessors and the other predecessors.
            predecessors = set(
                chain(
                    *[pruned_node_predecessors[k] for k in self.get_predecessors(node)]
                )
            )

            if fun(self, node):
                # Check if node can pruned
                if node in self.tags and preserve_context:
                    raise DAGError("suppressing %s impact context" % node)

                # Node is pruned keep track of its predecessors
                pruned_node_predecessors[node] = predecessors
            else:
                # Node is kept. Note that no check is needed as pruning
                # operation cannot introduce a cycle.
                result.update_vertex(node, data, predecessors, enable_checks=False)
                pruned_node_predecessors[node] = set([node])
                if node in self.tags:
                    result.add_tag(node, self.tags[node])
        return result

    def __len__(self):
        return len(self.vertex_data)

    def __str__(self):
        result = []
        for vertex, predecessors in self.__vertex_predecessors.items():
            if predecessors:
                result.append("%s -> %s" % (vertex, ", ".join(predecessors)))
            else:
                result.append("%s -> (none)" % vertex)
        return "\n".join(result)
