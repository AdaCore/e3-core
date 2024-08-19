from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Iterable


class Qualifier(dict):

    def __sub__(self, other: Iterable[str]) -> Qualifier:
        """Create a new dict qualifier with some keys filtered-out.

        Examples:
            {"k1": "v1", "k2": "v2"} - {"k2"} == {"k1": "v1"}
            {"k1": "v1", "k2": "v2"} - {"k2": "v3"} == {"k1": "v1"}
        """
        return Qualifier({k: v for k, v in self.items() if k not in other})

    def __add__(self, other: dict | None) -> Qualifier:
        """Create a new dict qualifier that merges two dicts.

        The operation is equivalent to pipe operator with the difference that
        its priority is higher as defined by Python standard. This allows more
        natural expression that mix + and - operators (both operators have the
        same priority).
        """
        if other is None:
            return Qualifier(self)
        else:
            return Qualifier(self | other)

    def __and__(self, other: Iterable[str]) -> Qualifier:
        """Create a new dict qualifier with the subset other of the keys.

        Examples:
            {"k1": "v1", "k2": "v2"} & {"k2"} == {"k2": "v2"}
            {"k1": "v1", "k2": "v2"} & {"k2": "v3"} == {"k2": "v2"}
        """
        return Qualifier({k: v for k, v in self.items() if k in other})
