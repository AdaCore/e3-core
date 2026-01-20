from __future__ import annotations

import pytest

from e3.os.fs import touch
from e3.anod.store.interface import StoreError
from e3.anod.store.buildinfo import BuildInfo
from e3.error import E3Error

DEFAULT_SETUP = "test"


def test_build_info_create(store) -> None:
    """Test creating a BuildInfo object from a build ID."""
    today = BuildInfo.today_build_date()

    bid1 = BuildInfo.create(store, DEFAULT_SETUP, "1.0")
    assert bid1.build_date == today
    assert bid1.build_version == "1.0"
    assert bid1.setup == DEFAULT_SETUP
    assert not bid1.isready

    bid2 = BuildInfo.create(store, DEFAULT_SETUP, "1.0", "20120101")
    assert bid2.build_date == "20120101"
    assert bid2.build_version == "1.0"
    assert bid2.setup == DEFAULT_SETUP
    assert not bid2.isready

    with pytest.raises(StoreError, match="No buildinfo found"):
        BuildInfo.latest(store, DEFAULT_SETUP)

    assert BuildInfo.latest(store, DEFAULT_SETUP, ready_only=False) == bid1

    assert bid1.mark_ready()
    assert bid1.isready

    latest = BuildInfo.latest(store, DEFAULT_SETUP)
    assert latest == bid1 and latest.isready

    assert (
        BuildInfo.latest(store, DEFAULT_SETUP, build_date="20120101", ready_only=False)
        == bid2
    )
    assert bid2.mark_ready()
    assert bid2.isready

    latest = BuildInfo.latest(store, DEFAULT_SETUP, build_date="20120101")
    assert latest == bid2 and latest.isready


def test_load_build_info_ready() -> None:
    """Test basic BuildInfo.load with ready build ID."""
    build_info_data = {
        "build_date": "20170915",
        "isready": True,
        "setup": "gcc-49",
        "creation_date": "2017-09-16 01:05:03.132488",
        "build_version": "18.0w",
        "_id": "59bc78bfc7a447cf3bbe0ece",
    }
    bi = BuildInfo.load(build_info_data)
    assert str(bi)
    assert bi is not None


def test_load_build_info_not_ready() -> None:
    """Test basic BuildInfo.load and BuildInfo.as_dict."""
    build_info_data = {
        "build_date": "20170915",
        "isready": False,
        "setup": "gcc-49",
        "creation_date": "2017-09-16 01:05:03.132488",
        "build_version": "18.0w",
        "_id": "59bc78bfc7a447cf3bbe0ece",
    }
    bi = BuildInfo.load(build_info_data)
    assert str(bi)
    assert bi.as_dict() == build_info_data


def test_load_build_info_implict_not_ready() -> None:
    """Test basic BuildInfo.load and BuildInfo.as_dict."""
    build_info_data = {
        "build_date": "20170915",
        "setup": "gcc-49",
        "creation_date": "2017-09-16 01:05:03.132488",
        "build_version": "18.0w",
        "_id": "59bc78bfc7a447cf3bbe0ece",
    }
    bi = BuildInfo.load(build_info_data)

    as_dict_result = dict(build_info_data)
    as_dict_result["isready"] = False
    assert str(bi)
    assert bi.as_dict() == as_dict_result


def test_create_build_info_from_id(store) -> None:
    """Test creating a BuildInfo object from a build ID."""
    ref_bi = store.create_build_id(DEFAULT_SETUP, "20241030", "1.0")
    ref_bi["isready"] = store.mark_build_ready(ref_bi["_id"])

    bi = BuildInfo.from_id(store, ref_bi["_id"])
    assert str(bi)
    assert bi.as_dict() == ref_bi


def test_create_build_info_from_invalid_id(store) -> None:
    """Test creating a BuildInfo object from a nonexistant build ID."""
    with pytest.raises(StoreError):
        BuildInfo.from_id(store, "non-existant")


def test_get_build_info_list(store) -> None:  # type: ignore [no-untyped-def]
    BuildInfo.create(
        store=store,
        setup=DEFAULT_SETUP,
        version="1.0",
        date="20250518",
        mark_ready=True,
    )

    BuildInfo.create(
        store=store,
        setup=DEFAULT_SETUP,
        version="1.0",
        date="20250515",
        mark_ready=True,
    )

    BuildInfo.create(
        store=store, setup="other", version="1.0", date="20250514", mark_ready=True
    )

    BuildInfo.create(
        store=store,
        setup=DEFAULT_SETUP,
        version="1.0",
        date="20250513",
        mark_ready=True,
    )

    BuildInfo.create(
        store=store,
        setup=DEFAULT_SETUP,
        version="1.0",
        date="20250512",
        mark_ready=True,
    )

    BuildInfo.create(
        store=store,
        setup=DEFAULT_SETUP,
        version="1.0",
        date="20250511",
        mark_ready=True,
    )

    BuildInfo.create(
        store=store,
        setup=DEFAULT_SETUP,
        version="2.0",
        date="20250510",
        mark_ready=True,
    )

    # There should be only 2 matching build info in the last 3 days
    bis: list[BuildInfo] = BuildInfo.list(
        store, setup=DEFAULT_SETUP, build_date="20250518", nb_days=3
    )
    assert len(bis) == 2

    # There should be only 3 matching build info in the last 5 days
    bis = BuildInfo.list(store, setup=DEFAULT_SETUP, build_date="20250518", nb_days=5)
    assert len(bis) == 3

    # Check with other setup
    bis = BuildInfo.list(store, setup="other", build_date="20250518", nb_days=10)
    assert len(bis) == 1
    bis = BuildInfo.list(store, setup="other")
    assert len(bis) == 1

    # Check with all setup (both using "all" or None)
    bis = BuildInfo.list(store, setup="all", build_date="20250518", nb_days=10)
    assert len(bis) == 7
    bis = BuildInfo.list(store, build_date="20250518", nb_days=10)
    assert len(bis) == 7

    bis = BuildInfo.list(store, setup=DEFAULT_SETUP, build_version="2.0")
    assert len(bis) == 1


def test_get_latest_build_not_found(store) -> None:
    """Test BuildInfo.latest class method."""
    with pytest.raises(StoreError):
        BuildInfo.from_id(store, "nonexistant")


def test_get_latest_build_ready(store) -> None:
    bid = store.create_build_id(DEFAULT_SETUP, "20241001", "1.0")["_id"]
    store.mark_build_ready(bid)
    bid = store.create_build_id(DEFAULT_SETUP, "20241002", "1.0")["_id"]
    store.mark_build_ready(bid)
    bid = store.create_build_id(DEFAULT_SETUP, "20241003", "1.0")["_id"]
    # store.mark_build_ready(bid)
    bid = store.create_build_id("other", "20241004", "1.0")["_id"]
    store.mark_build_ready(bid)

    bi = BuildInfo.latest(store, setup=DEFAULT_SETUP)
    assert bi.build_date == "20241002"


def test_get_latest_build_ready_or_not(store) -> None:
    bid = store.create_build_id(DEFAULT_SETUP, "20241001", "1.0")["_id"]
    store.mark_build_ready(bid)
    bid = store.create_build_id(DEFAULT_SETUP, "20241002", "1.0")["_id"]
    store.mark_build_ready(bid)
    bid = store.create_build_id(DEFAULT_SETUP, "20241003", "1.0")["_id"]
    # store.mark_build_ready(bid)
    bid = store.create_build_id("other", "20241004", "1.0")["_id"]
    store.mark_build_ready(bid)

    bi = BuildInfo.latest(store, setup=DEFAULT_SETUP, ready_only=False)
    assert bi.build_date == "20241003"


def test_get_source_list(store) -> None:
    bid = store.create_build_id(DEFAULT_SETUP, "20241001", "1.0")["_id"]
    store.mark_build_ready(bid)

    touch("test1")
    store.submit_file(
        {
            "name": "ex1-src",
            "kind": "source",
            "alias": "ex1-src",
            "filename": "ex1-src",
            "revision": "",
            "metadata": None,
            "build_id": bid,
            "resource_id": "izefbnpzaodboa",
            "downloaded_as": "test1",
        }
    )
    touch("test2")
    store.submit_file(
        {
            "name": "ex2-src",
            "kind": "source",
            "alias": "ex2-src",
            "filename": "ex2-src",
            "revision": "",
            "metadata": None,
            "build_id": bid,
            "resource_id": "aofzipzefnaibzoa",
            "downloaded_as": "test2",
        }
    )
    touch("test3")
    store.submit_file(
        {
            "name": "ex3-src",
            "kind": "source",
            "alias": "ex3-src",
            "filename": "ex3-src",
            "revision": "",
            "metadata": None,
            "build_id": bid,
            "resource_id": "ibduiazubdozeijzeofubzuyvytcxquv",
            "downloaded_as": "test3",
        }
    )
    touch("test4")
    store.submit_file(
        {
            "name": "third.tgz",
            "kind": "thirdparty",
            "alias": "third.tgz",
            "filename": "third.tgz",
            "revision": "",
            "metadata": None,
            "build_id": bid,
            "resource_id": "aouzfbizebfzpxnoizef",
            "downloaded_as": "test4",
        }
    )
    touch("test5")
    store.submit_file(
        {
            "name": "ex-bin.tar.gz",
            "kind": "binary",
            "alias": "ex-bin.tar.gz",
            "filename": "ex-bin.tar.gz",
            "revision": "",
            "metadata": None,
            "build_id": bid,
            "resource_id": "jdbaiubozeindsyivziuadoainz",
            "downloaded_as": "test5",
        }
    )

    bi = BuildInfo.latest(store, setup=DEFAULT_SETUP)
    src_list = bi.get_source_list()

    names = ("ex1-src", "ex2-src", "ex3-src", "third.tgz")
    for src in src_list:
        assert src.name in names
        assert src.kind != "binary"
    assert len(src_list) == 4


def test_get_build_data(store) -> None:
    bid = store.create_build_id(DEFAULT_SETUP, "20241001", "1.0")["_id"]
    store.mark_build_ready(bid)

    touch("test1")
    store.submit_file(
        {
            "name": "ex1-src",
            "kind": "source",
            "alias": "ex1-src",
            "filename": "ex1-src",
            "revision": "",
            "metadata": None,
            "build_id": bid,
            "resource_id": "izefbnpzaodboa",
            "downloaded_as": "test1",
        }
    )
    touch("test2")
    store.submit_file(
        {
            "name": "ex2-src",
            "kind": "source",
            "alias": "ex2-src",
            "filename": "ex2-src",
            "revision": "",
            "metadata": None,
            "build_id": bid,
            "resource_id": "aofzipzefnaibzoa",
            "downloaded_as": "test2",
        }
    )
    touch("test3")
    store.submit_file(
        {
            "name": "ex3-src",
            "kind": "source",
            "alias": "ex3-src",
            "filename": "ex3-src",
            "revision": "",
            "metadata": None,
            "build_id": bid,
            "resource_id": "ibduiazubdozeijzeofubzuyvytcxquv",
            "downloaded_as": "test3",
        }
    )
    touch("test4")
    store.submit_file(
        {
            "name": "third.tgz",
            "kind": "thirdparty",
            "alias": "third.tgz",
            "filename": "third.tgz",
            "revision": "",
            "metadata": None,
            "build_id": bid,
            "resource_id": "aouzfbizebfzpxnoizef",
            "downloaded_as": "test4",
        }
    )
    touch("test5")
    store.submit_file(
        {
            "name": "ex-bin.tar.gz",
            "kind": "binary",
            "alias": "ex-bin.tar.gz",
            "filename": "ex-bin.tar.gz",
            "revision": "",
            "metadata": None,
            "build_id": bid,
            "resource_id": "jdbaiubozeindsyivziuadoainz",
            "downloaded_as": "test5",
        }
    )

    other_bid = store.create_build_id("othersetup", "20241001", "1.0")["_id"]
    store.mark_build_ready(other_bid)

    touch("test6")
    store.submit_file(
        {
            "name": "ex4-src",
            "kind": "source",
            "alias": "ex4-src",
            "filename": "ex4-src",
            "revision": "",
            "metadata": None,
            "build_id": other_bid,
            "resource_id": "ibduiazubdozeijzeofubzuyvytcxquv",
            "downloaded_as": "test6",
        }
    )

    store.submit_component(
        {
            "name": "hello",
            "specname": "hello",
            "build_id": bid,
            "version": "1.0",
            "is_valid": True,
            "is_published": False,
            "platform": "x86_64-linux",
            "files": [],
            "sources": [],
            "releases": None,
            "readme": None,
            "attachments": None,
        }
    )

    bi = BuildInfo.latest(store, setup=DEFAULT_SETUP)
    data = bi.get_build_data()

    assert len(data["sources"]) == 4
    assert len(data["components"]) == 1


def test_get_component_list(store) -> None:
    bid = store.create_build_id(DEFAULT_SETUP, "20241001", "1.0")["_id"]
    store.mark_build_ready(bid)

    store.submit_component(
        {
            "name": "comp1",
            "specname": "comp1",
            "build_id": bid,
            "version": "1.0",
            "is_valid": True,
            "is_published": False,
            "platform": "x86-linux",
            "files": [],
            "sources": [],
            "releases": None,
            "readme": None,
            "attachments": None,
        }
    )
    store.submit_component(
        {
            "name": "comp1",
            "specname": "comp1",
            "build_id": bid,
            "version": "1.0",
            "is_valid": True,
            "is_published": False,
            "platform": "x86-windows",
            "files": [],
            "sources": [],
            "releases": None,
            "readme": None,
            "attachments": None,
        }
    )

    bi = BuildInfo.latest(store, setup=DEFAULT_SETUP)
    data = bi.get_component_list(name="comp1")
    assert len(data) == 2
    data = bi.get_component_list(name="comp1", platform="x86-linux")
    assert len(data) == 1
    data = bi.get_component_list(name="comp1", platform="x86_64-linux")
    assert len(data) == 0
    data = bi.get_component(name="comp1", platform="x86-linux")
    assert data.build_id == bid
    assert data.name == "comp1" and data.platform == "x86-linux"


def test_get_source_info(store) -> None:
    bid = store.create_build_id(DEFAULT_SETUP, "20241001", "1.0")["_id"]
    store.mark_build_ready(bid)
    touch("test")
    store.submit_file(
        {
            "name": "dummy-src",
            "kind": "source",
            "alias": "dummy-src",
            "filename": "dummy-src",
            "revision": "",
            "metadata": None,
            "build_id": bid,
            "resource_id": "ibduiazubdozeijzeofubzuyvytcxquv",
            "downloaded_as": "test",
        }
    )
    bi = BuildInfo.latest(store, setup=DEFAULT_SETUP)
    f = bi.get_source_info("dummy-src")
    assert f.name == "dummy-src"

    with pytest.raises(StoreError):
        bi.get_source_info("nonexist-src")


def test_wait(store) -> None:
    with pytest.raises(E3Error):
        bid = BuildInfo.wait(
            store=store, timeout=0.1, setup=DEFAULT_SETUP, retry_delay=0.1
        )
    bid = store.create_build_id(DEFAULT_SETUP, BuildInfo.today_build_date(), "1.0")

    with pytest.raises(E3Error):
        bid = BuildInfo.wait(
            store=store, timeout=0.1, setup=DEFAULT_SETUP, retry_delay=0.1
        )

    store.mark_build_ready(bid["_id"])
    bid = BuildInfo.wait(store=store, timeout=0.1, setup=DEFAULT_SETUP, retry_delay=0.1)
    assert bid.isready
    assert bid.setup == DEFAULT_SETUP


def test_build_info_eq_ne() -> None:
    ref_bi = BuildInfo(
        build_date="20170915",
        setup=DEFAULT_SETUP,
        creation_date="2017-09-16 01:05:03.132488",
        id="59bc78bfc7a447cf3bbe0ece",
        build_version="18.0w",
        isready=True,
    )

    # Create another BuildInfo objet, using the same parameters
    # as when we created ref_bi. Comparing those two should say
    # they are equal.

    bi = BuildInfo(
        build_date=ref_bi.build_date,
        setup=ref_bi.setup,
        creation_date=ref_bi.creation_date,
        id=ref_bi.id,
        build_version=ref_bi.build_version,
        isready=ref_bi.isready,
    )

    assert (bi == ref_bi) is True
    assert (bi != ref_bi) is False

    assert (bi == 1) is False

    # Now, iterate over each attribute, and create a BuildInfo
    # that's almost identical to ref_bi, except for the one attribute
    # that's different, and then evaluate equality.
    #
    # We perform this check in a systematic way so as to force us
    # to revisit the implementation of equality/non-equality each time
    # we add/remove an attribute, so as to avoid introducing subtle bugs
    # related to this feature.

    # A dictionary where, for each attribute of File, we have one
    # element where the key is that attribute name, and the value
    # is a tuple with the following elements:
    #   - A new value to use when modifying this attribute;
    #   - A boolean indicating the modified component is still expected
    #     to be equal to the unmodified one.
    TESTING_PLAN = {
        # Attributes which affect comparison...
        "build_date": ("unimportant", False),
        "setup": (ref_bi.setup + "-src", False),
        "creation_date": ("2018-09-16 01:05:03.132488", False),
        "id": ("a" * 24, False),
        "build_version": ("10.7w", False),
        "isready": (not ref_bi.isready, False),
        # Attributes that do not affect comparison...
        "store": ("unimportant", True),
    }

    # Verify that the TESTING_PLAN above covers all attributes
    # of class File.
    assert sorted(TESTING_PLAN.keys()) == sorted(bi.__dict__.keys())

    for attr_name in list(TESTING_PLAN.keys()):
        new_val, still_equal = TESTING_PLAN[attr_name]

        bi = BuildInfo(
            build_date=ref_bi.build_date,
            setup=ref_bi.setup,
            creation_date=ref_bi.creation_date,
            id=ref_bi.id,
            build_version=ref_bi.build_version,
            isready=ref_bi.isready,
        )
        setattr(bi, attr_name, new_val)

        assert (bi == ref_bi) is still_equal, attr_name
        assert (bi != ref_bi) is not still_equal, attr_name
        assert (bi == 1) is False


def test_build_info_copy(store) -> None:
    OTHER_SETUP = f"{DEFAULT_SETUP}-other"
    bid = BuildInfo.create(store, DEFAULT_SETUP, "1.0")
    copy = bid.copy(OTHER_SETUP, mark_as_ready=False)

    assert copy.setup == OTHER_SETUP
    assert copy.build_date == BuildInfo.today_build_date()
    assert copy.build_version == "1.0"
    assert not copy.isready

    with pytest.raises(StoreError, match="No buildinfo found"):
        BuildInfo.latest(store, OTHER_SETUP, ready_only=True)

    assert BuildInfo.latest(store, OTHER_SETUP, ready_only=False) == copy

    bid = BuildInfo.create(store, DEFAULT_SETUP, "1.0", date="20120101")
    copy = bid.copy(OTHER_SETUP, mark_as_ready=True)

    assert copy.setup == OTHER_SETUP
    assert copy.build_date == "20120101"
    assert copy.build_version == "1.0"
    assert copy.isready

    # Ensure no errors
    _ = BuildInfo.latest(store, OTHER_SETUP, ready_only=False)

    assert BuildInfo.latest(store, OTHER_SETUP, ready_only=True) == copy

    with pytest.raises(
        StoreError, match=f"Cannot copy into the same setup: {DEFAULT_SETUP}"
    ):
        _ = bid.copy(DEFAULT_SETUP)
