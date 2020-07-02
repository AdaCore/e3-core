"""Add set of conditional booleans that can be used to explore many combinations.

ToggleableBoolean are meant to be grouped and their value can be toggled to
explore all possible combinations. This can be useful when there is an expression
depending on external values that you want to evaluate without knowing in advance
the external environment.
"""
from __future__ import annotations

from itertools import product
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Iterator, List


class ToggleableBooleanGroup:
    """Contain group of toggleable boolean.

    Add a new boolean by calling .add(<name>, <bool value>). Then generate
    all possible combinations by running .shuffle()::

        group = ToggleableBooleanGroup()
        group.add('first', True)
        group.add('second', False)

        for series in group.shuffle():
            print([str(b) for b in series])

    Will display::

        ['first: True', 'second: True']
        ['first: False', 'second: True']
        ['first: False', 'second: False']
    """

    def __init__(self) -> None:
        self.series: List[ToggleableBoolean] = []

    def __getitem__(self, key: int) -> ToggleableBoolean:
        return self.series[key]

    def __len__(self) -> int:
        return len(self.series)

    def shuffle(self) -> Iterator[List[ToggleableBoolean]]:
        """Generate all other possible set of values for all conditional booleans.

        :return: yield a new list of ToggleableBoolean with a different set of value.
            Calling this function until StopIteration is raised will generate all
            possible values except the initial set of value.
        """
        initial_values = tuple(bool(c) for c in self.series)
        for shuffeld_values in product([True, False], repeat=len(initial_values)):
            if shuffeld_values != initial_values:
                # Replace conditional values by these new shuffled values
                for idx, value in enumerate(shuffeld_values):
                    self.series[idx].value = value
                yield self.series

    def add(self, name: str, value: bool) -> ToggleableBoolean:
        """Create a new boolean value and add it to this group.

        :param name: boolean name for debug info
        :param value: boolean value
        """
        result = ToggleableBoolean(name=name, value=value)
        self.series.append(result)
        return result


class ToggleableBoolean:
    """Contain a boolean value that can be toggle in group.

    See ToggleableBooleanGroup.
    """

    def __init__(self, name: str, value: bool) -> None:
        """Set boolean value.

        :param name: boolean name for debug info
        :param value: boolean value
        """
        self.value = value
        self.name = name

    def __bool__(self) -> bool:
        return self.value

    def __str__(self) -> str:
        return f"{self.name}: {self.value}"
