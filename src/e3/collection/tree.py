from typing import List, Optional


class Node:
    """Implement a Node structure to be used by the Tree class."""

    def __init__(self, tag: str, identifier: str, parent: Optional[str] = None) -> None:
        """Construct a Node object."""
        self.tag = tag
        self.identifier = identifier
        self.parent = parent
        self.children: List[Node] = []

    @property
    def is_leaf(self) -> bool:
        """Check if the node is a leaf of the tree or not."""
        return not self.children

    def __str__(self) -> str:
        """Print the tag of the node by default."""
        return str(self.tag)


class Tree:
    """Implement a tree structure to imitate the bash `tree` command."""

    def __init__(self) -> None:
        """Construct a Tree object."""
        self.root_node: Optional[Node] = None
        self.id_list: List[str] = []

    def create_node(
        self, tag: str, identifier: str, parent: Optional[str] = None
    ) -> None:
        """Create a node in the tree.

        :param tag: the tag of the node (what is going to be shown to the user).
        :param identifier: the ID used to find the node in the tree (must be unique).
        :param parent: the ID of the parent of the node. This is irrelevant for the
            root node.
        """
        # Check for duplicate ID
        if identifier in self.id_list:
            raise TreeException(f"Identifier {identifier} already exists in tree")

        # The first node becomes the root node automatically
        if self.root_node is None:
            if parent is not None:
                raise TreeException("Parent should be None for root node")
            self.root_node = Node(tag, identifier)
        else:
            # Check that parent is not None
            if not parent:
                raise TreeException("Parent cannot be None for non-root node")

            # Check that parent exists
            if parent not in self.id_list:
                raise TreeException(f"Parent {parent} is not in tree")

            # Create new node
            new_node = Node(tag, identifier, parent)
            parent_node = self.get_node(parent)
            assert parent_node is not None
            # Append node to its parent's children list
            parent_node.children.append(new_node)

        # Append new ID to ID list
        self.id_list.append(identifier)

    def remove_node(self, identifier: str) -> None:
        """Remove a node from the tree.

        :param identifier: the ID of the node to be removed
        """
        if identifier not in self.id_list:
            raise TreeException(
                f"Identifier {identifier} cannot be removed (does not exist in tree)"
            )

        # Get node to be deleted
        node = self.get_node(identifier)
        assert node is not None
        for child in node.children:
            self.remove_node(child.identifier)

        if node.parent is None:
            # Node is root, delete everything
            self.root_node = None
            self.id_list = []
        else:
            # Get the node's parent
            parent_node = self.get_node(node.parent)
            assert parent_node is not None
            # Remove the child of the parent node
            parent_node.children.remove(node)
            # Remove the child's ID from the ID list
            self.id_list.remove(identifier)

    def get_node(
        self, identifier: str, start_node: Optional[Node] = None
    ) -> Optional[Node]:
        """Get a specific node from the tree (using its ID).

        :param identifier: the ID of the node we're looking for
        :param start_node: the node from which to begin the search. If None, start
            from the root node.
        :return: the node if it is found, None otherwise.
        """
        # If the user doesn't specify a start node, start from the top
        if start_node is None:
            # If the tree is empty, there's no need to look
            if self.root_node is None:
                return None
            start_node = self.root_node

        assert start_node is not None
        # If the node is found, return it
        if start_node.identifier == identifier:
            return start_node
        # If it's not found, look among its children
        else:
            for child in start_node.children:
                # Launch get_node() recursively
                node = self.get_node(identifier, start_node=child)
                # If found, return it
                if node:
                    return node

            # If nothing is found at the end of the search, the node does not exist
            return None

    def show(
        self, start_node: Optional[Node] = None, depth: int = 0, prefix: str = ""
    ) -> None:
        """Print the tree, like the bash `tree` command.

        The start node parameter is used in the similar fashion as in the `get_node()`
        function. The depth and prefix parameters are also used in the same fashion,
        and serve to determine the format of the pipe symbols used to print the
        "skeleton" of the tree. It is not recommended to change the initial value of
        these parameters.

        :param start_node: the root node from which to begin the search. If None, start
            from the root node.
        :param depth: the initial depth, used for formatting the printed tree.
        :param prefix: the initial prefix, used for formatting the printed tree.
        """
        # If the user doesn't specify a start node, start from the top
        if start_node is None:
            # If the tree is empty, there's nothing to print
            if self.root_node is None:
                return
            start_node = self.root_node
            assert start_node is not None
            # Just print the tag of the node, no need for a prefix or suffix
            print(start_node)
            # Move to the next level of depth
            depth += 1

        # Iterate over children (in order)
        for i, child in enumerate(sorted(start_node.children, key=lambda c: c.tag)):
            # If it's the last child, don't continue pipe downwards
            if i == len(start_node.children) - 1:
                suffix = "\u2514\u2500\u2500 "
            # Else, do continue pipe downwards
            else:
                suffix = "\u251c\u2500\u2500 "

            # If it's the last child, don't show any vertical pipes as a prefix related
            # to this level of depth
            if i == len(start_node.children) - 1:
                new_prefix = "    "
            # Else, do show a vertical pipe for this level of depth
            else:
                new_prefix = "\u2502   "

            # Print the node's tag with the appropriate prefix and suffix
            print(f"{prefix}{suffix}{child}")

            # Recurse on the child to print all levels of depths
            self.show(start_node=child, depth=depth + 1, prefix=prefix + new_prefix)


class TreeException(Exception):
    """Implement an exception specific to the Tree class."""

    pass
