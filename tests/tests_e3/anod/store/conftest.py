from __future__ import annotations

import pytest

from e3.anod.store import StoreRW


@pytest.fixture(scope="function")
def store():
    with StoreRW() as store:
        yield store
