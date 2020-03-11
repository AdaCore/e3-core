from enum import Enum


class ReturnValue(Enum):
    """Return values for anod commands."""

    success = 0
    failure = 1
    missing = 2
    notready = 75
    force_skip = 122
    force_fail = 123
    unknown = 124
    skip = 125
    unchanged = 126
