from __future__ import annotations

import pytest

from e3.anod.store import StoreRW


@pytest.fixture(scope="function")
def store() -> StoreRW:
    # Adding a default DB filename is mandatory to avoid collision between the tests and
    # the fixture.
    #
    # Otherwise, the default DB name used by everyone, including tests that doesn't
    # specify a DB filename, will ".store.db".
    with StoreRW("_fixture-database.db") as store:
        yield store
