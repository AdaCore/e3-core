"""Implementation of Direct Acyclic Graphs."""

from __future__ import absolute_import

NOT_VISITED = 0
LOCKED = 1
VISITED = 2


class DAG(object):
    def __init__(self, nodes=None):
        """Initialize a DAG."""
        self.nodes = {0: None}
        self.prereqs = {0: set()}
        self.states = {0: NOT_VISITED}
        self.node_index = 0

        # State
        self.non_visited = {0}

        if nodes is not None:
            for node in nodes:
                self.add_node(node)

    def add_node(self, data, prereqs=None):
        """Add a node into the DAG.

        :param data: data for the node. If data is None the node will be
            considered as a dummy node
        :param prereqs: list of prerequisites or None
        :type prereqs: list[int] | None
        :return: the new node id
        :rtype: int
        """
        if prereqs is None:
            prereqs = {0}
        else:
            prereqs = set(prereqs)

        self.node_index += 1
        nid = self.node_index
        self.nodes[nid] = data
        self.prereqs[nid] = prereqs
        self.states[nid] = NOT_VISITED
        self.non_visited.add(nid)
        return nid

    def add_nodes(self, *args, **kwargs):
        """Add various nodes in the dag with the same prerequisites.

        Each element of args is used as data parameter for add_node and
        if prereqs keyword argument is passed all the added nodes will
        have prereqs as prerequisites.

        :return: the list of node ids
        :rtype: list[int]
        """
        result = set()
        for d in args:
            result.add(self.add_node(d, kwargs.get('prereqs', None)))
        return result

    def __iter__(self):
        return self

    def __len__(self):
        # Don't count node 0 (root of the dag)
        return len(self.nodes) - 1

    def next(self):
        """Retrieve next element ready for execution.

        Elements returned by next are marked as LOCKED and should be released
        with release method to be marked as VISITED

        :return: a tuple id, data. (None, None) is returned if no element is
            available
        :rtype: (int, object)
        """
        result = self.non_visited
        if not result:
            raise StopIteration

        # Retrieve the first node for which all the parents have been
        # visited
        result = next(
            (k for k in result if not self.prereqs[k] or
             not [p for p in self.prereqs[k] if self.states[p] != VISITED]),
            None)

        if result is None:
            # No node is ready to be visited
            return None, None

        # Lock the node and remove it from the visited list
        self.states[result] = LOCKED
        self.non_visited.discard(result)

        # If the node has no data this is a dummy node so release it
        # immediately and return the next element
        if self.nodes[result] is None:
            self.__release_locked_node(result)
            return self.next()

        return result, self.nodes[result]

    def __release_locked_node(self, node):
        """Release a locked node.

        :param node: a node id
        :type node: int
        """
        assert self.states[node] == LOCKED, 'cannot release a non locked node'
        self.states[node] = VISITED

    def release(self, node):
        """Release a node.

        :param node: a node id
        :type node: int | None

        Do nothing when the node is not locked
        """
        if node is not None and self.states[node] == LOCKED:
            self.__release_locked_node(node)
