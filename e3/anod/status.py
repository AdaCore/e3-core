from __future__ import absolute_import

from enum import Enum


class ReturnValue(Enum):
    """Return values for anod commands."""
    success = 0
    failure = 1
    missing = 2
    notready = 75
