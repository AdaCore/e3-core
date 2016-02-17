"""Implementation of Direct Acyclic Graphs."""

from __future__ import absolute_import
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
            or NOT_VISITED. When true, calling the next() funtion on the
            iteratior puts the element in 'BUSY' state. It will only be moved
            to 'Visited' once calling the 'leave()' method.
        :type enable_busy_state: bool
        """
        self.dag = dag
        self.non_visited = set(self.dag.vertex_data.keys())
        self.states = {k: self.NOT_VISITED
                       for k in self.dag.vertex_data.keys()}
        self.enable_busy_state = enable_busy_state

    def __iter__(self):
        return self

    def next(self):
        """Retrieve next element in topological order.

        :return: a tuple id, data. (None, None) is returned if no element is
            available
        :rtype: (str, object)
        """
        if not self.non_visited:
            raise StopIteration

        # Retrieve the first vertex for which all the predecessors have been
        # visited
        result = next(
            (k for k in self.non_visited
             if not self.dag.vertex_predecessors[k] or
             not [p for p in self.dag.vertex_predecessors[k]
                  if self.states[p] != self.VISITED]),
            None)

        if result is None:
            # No vertex is ready to be visited
            return None, None

        # Remove the vertex from the "non_visited_list" and when
        # enable_busy_state, mark the vertex as BUSY, mark it VISITED
        # otherwise.
        self.states[result] = self.BUSY if self.enable_busy_state \
            else self.VISITED
        self.non_visited.discard(result)

        return result, self.dag.vertex_data[result]

    def leave(self, vertex_id):
        """Switch element from BUSY to VISITED state.

        :param vertex_id: the vertex to leave
        :type vertex_id: str
        """
        assert self.states[vertex_id] == self.BUSY
        self.states[vertex_id] = self.VISITED


class DAG(object):
    def __init__(self):
        """Initialize a DAG."""
        self.vertex_data = {}
        self.vertex_predecessors = {}

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
            raise DAGError(message="vertex %s already exist" % vertex_id,
                           origin="DAG.add_vertex")
        self.update_vertex(vertex_id, data, predecessors)

    def update_vertex(self, vertex_id, data=None, predecessors=None):
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
        :raise: DAGError if cycle is detected
        """
        if predecessors is None:
            predecessors = frozenset()
        else:
            predecessors = frozenset(predecessors)

        non_existing_predecessors = [k for k in predecessors
                                     if k not in self.vertex_data]
        if non_existing_predecessors:
            raise DAGError(message='predecessor on non existing vertices %s'
                           % ", ".join(non_existing_predecessors),
                           origin="DAG.update_vertex")

        if vertex_id not in self.vertex_data:
            self.vertex_predecessors[vertex_id] = predecessors
            self.vertex_data[vertex_id] = data
        else:
            previous_predecessors = self.vertex_predecessors[vertex_id]
            self.vertex_predecessors[vertex_id] |= predecessors

            # Will raise DAGError if a cycle is created
            try:
                self.get_closure(vertex_id)
            except DAGError:
                self.vertex_predecessors[vertex_id] = previous_predecessors
                raise DAGError(
                    message='cannot update vertex (%s create a cycle)'
                    % vertex_id,
                    origin='DAG.update_vertex')

            if data is not None:
                self.vertex_data[vertex_id] = data

    def get_closure(self, vertex_id):
        """Retrieve closure of predecessors for a vertex.

        :param vertex_id: the vertex to inspect
        :type vertex_id: collections.Hashable
        :return: a set of vertex_id
        :rtype: set(collections.Hashable)
        """
        visited = set()
        closure = self.vertex_predecessors[vertex_id]
        closure_len = len(closure)

        while True:
            for n in closure - visited:
                visited.add(n)

                if n in self.vertex_predecessors:
                    closure |= self.vertex_predecessors[n]

            if vertex_id in closure:
                raise DAGError(message='cycle detected (involving: %s)'
                               % vertex_id,
                               origin='DAG.get_closure')

            if len(closure) == closure_len:
                break
            closure_len = len(closure)
        return closure

    def __iter__(self):
        return DAGIterator(self)

    def __or__(self, other):
        """Merge two dags."""
        assert isinstance(other, DAG)

        result = DAG()

        # First add vertices and then update predecessors. The two step
        # procedure is needed because predecessors should exist. Also
        # using add_vertex and update_vertex ensure cycle detection is done
        # during the creation of the merged DAG.
        for nid in self.vertex_data:
            result.add_vertex(nid)

        for nid in other.vertex_data:
            result.update_vertex(nid)

        # Update predecessors
        for nid in self.vertex_data:
            result.update_vertex(
                nid,
                self.vertex_data[nid],
                self.vertex_predecessors[nid])

        for nid in other.vertex_data:
            result.update_vertex(
                nid,
                other.vertex_data[nid],
                other.vertex_predecessors[nid])
        return result

    def __len__(self):
        return len(self.vertex_data)

    def __str__(self):
        result = []
        for nid in self.vertex_predecessors:
            if self.vertex_predecessors[nid]:
                result.append('%s -> %s' %
                              (nid,
                               ', '.join(self.vertex_predecessors[nid])))
            else:
                result.append('%s -> (none)' % nid)
        return '\n'.join(result)
