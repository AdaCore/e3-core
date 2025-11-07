from __future__ import annotations

import os
import pytest
from datetime import datetime, timezone

from e3.os.fs import touch

from e3.anod.store.file import File, FileKind
from e3.anod.store.buildinfo import BuildInfo
from e3.anod.store.component import Component
from e3.anod.store.interface import StoreError


def test_create_and_get_build_info(store):
    # Ensure the "build_info" is created between 'start' and 'end'.
    #
    # With the current implementation the buildinfo is created automatically when
    # a new entry is added to the database.
    #
    # Doing this ensures that the retrieved build_info is not an old relic kept on
    # the database (which should normally be recreated for each tests). This also,
    # ensures that the retrieved dict contains a parsable "creation_date" key.
    start = datetime.now(timezone.utc).replace(microsecond=0)
    created = store.create_build_id("test", "20241028", "1.0")
    date = datetime.fromisoformat(created["creation_date"]).replace(microsecond=0)
    end = datetime.now(timezone.utc).replace(microsecond=0)
    assert start <= date <= end

    assert created["_id"] is not None
    assert created["setup"] == "test"
    assert created["isready"] is False
    assert created["build_date"] == "20241028"
    assert created["build_version"] == "1.0"

    get = store.get_build_info(created["_id"])
    assert get == created

    previous = store.create_build_id("test", "20241027", "1.0")
    tmp = store.get_latest_build_info("test", ready_only=False)
    assert tmp == created

    created2 = store.create_build_id("test", "20241028", "1.0")
    assert created2 != created
    tmp = store.get_latest_build_info("test", ready_only=False)
    assert tmp != created
    assert tmp == created2

    tmp = store.get_latest_build_info(
        "test", date="20241027", version="1.0", ready_only=False
    )
    assert tmp == previous


def test_build_info_ready(store):
    created = store.create_build_id("test", "20241028", "1.0")
    assert created["isready"] is False

    with pytest.raises(StoreError) as err:
        store.get_latest_build_info("test")
    assert "No buildinfo found" in str(err)

    assert store.mark_build_ready(created["_id"]) is True
    tmp = store.get_latest_build_info("test")

    created["isready"] = True
    assert tmp == created


def test_file(store):
    buildinfo = store.create_build_id("test", "20241028", "1.0")
    touch("test.txt")
    assert os.path.isfile("test.txt")
    with open("test.txt", "w") as fd:
        fd.write("m")
    path_abs = os.path.abspath("test.txt")

    tmp = File(
        build_id=buildinfo["_id"],
        kind=FileKind.thirdparty,
        name="test.txt",
        filename="test.txt",
        resource_path="test.txt",
    )

    f = store.submit_file(tmp.as_dict())
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    assert "_id" in f
    assert f["kind"] == "thirdparty"
    assert f["name"] == "test.txt"
    assert f["alias"] == "test.txt"
    assert f["filename"] == "test.txt"
    assert f["revision"] == ""
    assert f["metadata"] == {}
    assert f["build_id"] == buildinfo["_id"]
    assert "resource_id" in f
    assert "id" in f["resource"]
    assert f["resource"]["id"] == f["resource_id"]
    assert f["resource"]["path"] == path_abs
    assert f["resource"]["size"] == 1
    date = datetime.fromisoformat(f["resource"]["creation_date"]).replace(
        second=0, microsecond=0
    )
    assert now == date
    assert f.get("unpack_dir") is None
    assert "build" in f and f["build"]["_id"] == f["build_id"]

    touch("test-tp.txt")
    with open("test-tp.txt", "w") as fd:
        fd.write("n")

    tmp = File(
        build_id=buildinfo["_id"],
        kind=FileKind.thirdparty,
        name="test-tp.txt",
        filename="test-tp.txt",
        resource_path="test-tp.txt",
    )

    f2 = store.create_thirdparty(tmp.as_dict())
    assert f["_id"] != f2["_id"]

    latest = store.latest_thirdparty("test-tp.txt")
    assert latest["_id"] == f2["_id"]
    latest = store.latest_thirdparty("test-tp.txt", tp_id=f2["_id"])
    assert latest["_id"] == f2["_id"]

    src = store.get_source_info("test.txt", bid=buildinfo["_id"], kind="thirdparty")
    assert src["_id"] == f["_id"]

    with pytest.raises(ValueError, match="Cannot find file without name or file id"):
        store._get_file()

    tmp = store._get_file(fid=f2["_id"])
    assert tmp is not None
    assert tmp["name"] == "test-tp.txt"


def test_component(store):
    """Check that we can add a component to the offline db."""
    buildinfo = store.create_build_id("test", "20241029", "1.0")
    store.mark_build_ready(buildinfo["_id"])

    # First create a component
    bid = BuildInfo.latest(store=store, setup="test")
    with open("test1.txt", "w") as fd:
        fd.write("1")

    binary1 = File(
        build_id=bid.id,
        kind=FileKind.binary,
        name="test1.txt",
        filename="test1.txt",
        build_info=bid,
        resource_path=os.path.abspath("test1.txt"),
    )

    with open("source.txt", "w") as fd:
        fd.write("s")

    source = File(
        build_id=buildinfo["_id"],
        kind=FileKind.thirdparty,
        name="source.txt",
        filename="source.txt",
        resource_path="source.txt",
    )

    with open("att.txt", "w") as fd:
        fd.write("a")

    with open("readme.txt", "w") as fd:
        fd.write("x")

    att = File(
        build_id=buildinfo["_id"],
        kind=FileKind.thirdparty,
        name="att.txt",
        filename="att.txt",
        resource_path="att.txt",
    )
    readme = File(
        build_id=buildinfo["_id"],
        kind=FileKind.readme,
        name="readme.name",
        filename="readme.txt",
        resource_path="readme.txt",
    )

    c1 = Component(
        build_id=bid.id,
        build_info=bid,
        name="comp1",
        specname="comp1",
        platform="x86_64-linux",
        version="1.0",
        files=[binary1],
        readme=readme,
        attachments=[{"name": "myatt", "att_file": att.as_dict()}],
        store=store,
    )
    # Attachments as a list are automatically transformed into a dict by the
    # Component.__init__ function. We just force the attachments to be a list of
    # ComponentAttachment for testing purpose.
    c1_dict = c1.as_dict()
    c1_dict["attachments"] = [
        {"name": "myatt", "att_file": c1_dict["attachments"]["myatt"]}
    ]
    store.submit_component(c1_dict)
    tmp = Component.load(c1_dict)
    assert tmp == c1

    tmp = store.list_components(bid.id)
    assert len(tmp) == 1
    assert tmp[0]["name"] == "comp1"
    assert tmp[0]["specname"] == "comp1"
    assert tmp[0]["platform"] == "x86_64-linux"
    assert tmp[0]["version"] == "1.0"
    assert tmp[0]["build_id"] == bid.id
    assert tmp[0]["build"] == bid.as_dict()
    assert tmp[0]["readme"]["name"] == "readme.name"
    assert tmp[0]["readme"]["kind"] == "readme"
    assert tmp[0]["readme"]["filename"] == "readme.txt"
    assert isinstance(tmp[0]["attachments"], dict)
    assert len(tmp[0]["attachments"].keys()) == 1
    assert list(tmp[0]["attachments"].keys())[0] == "myatt"
    assert list(tmp[0]["attachments"].values())[0]["name"] == "att.txt"
    assert tmp[0]["readme"]["filename"] == "readme.txt"

    tmp = store.list_components(bid.id, platform="CannotBeFound")
    assert not tmp
    tmp = store.list_components(bid.id, component="CannotBeFound")
    assert not tmp

    # Sources should be submited BEFORE pushing the component
    src = store.submit_file(source.as_dict())

    with open("test2.txt", "w") as fd:
        fd.write("2")

    binary2 = File(
        build_id=bid.id,
        kind=FileKind.binary,
        name="test2.txt",
        filename="test2.txt",
        build_info=bid,
        resource_path=os.path.abspath("test2.txt"),
    )

    c2 = Component(
        build_id=bid.id,
        build_info=bid,
        name="comp2",
        specname="comp2",
        platform="x86_64-windows64",
        version="2.0",
        files=[binary2],
        sources=[File.load(src, store=store)],
        attachments={"myatt": att},
        store=store,
    )
    c2.push()

    tmp = store.list_components(bid.id)
    assert len(tmp) == 2

    tmp = store.latest_components("test")
    assert len(tmp) == 2
    assert tmp[0]["name"] == "comp2"
    assert tmp[0]["specname"] == "comp2"
    assert tmp[0]["platform"] == "x86_64-windows64"
    assert tmp[0]["version"] == "2.0"
    assert tmp[0]["build_id"] == bid.id
    assert tmp[0]["build"] == bid.as_dict()

    tmp = store.latest_components("test", platform="x86_64-linux")
    assert tmp[0]["name"] == "comp1"
    assert tmp[0]["specname"] == "comp1"
    assert tmp[0]["platform"] == "x86_64-linux"
    assert tmp[0]["version"] == "1.0"
    assert tmp[0]["build_id"] == bid.id
    assert tmp[0]["build"] == bid.as_dict()

    with open("att2.txt", "w") as fd:
        fd.write("a")

    # Test pushing component with the other attachment format (list)
    att2 = File(
        build_id=buildinfo["_id"],
        kind=FileKind.thirdparty,
        name="att2.txt",
        filename="att2.txt",
        resource_path="att2.txt",
    )

    with open("test2.txt", "w") as fd:
        fd.write("3")

    binary3 = File(
        build_id=bid.id,
        kind=FileKind.binary,
        name="test2.txt",
        filename="test2.txt",
        build_info=bid,
        resource_path=os.path.abspath("test2.txt"),
    )

    c3 = Component(
        build_id=bid.id,
        build_info=bid,
        name="comp3",
        specname="comp3",
        platform="x86_64-linux",
        version="3.0",
        files=[binary3],
        sources=[File.load(src, store=store)],
        attachments=[{"name": "myatt2", "att_file": att2.as_dict()}],
        store=store,
    )
    c3.push()
    tmp = store.latest_components("test", platform="x86_64-linux")
    assert tmp[0]["name"] == "comp3"
    assert tmp[0]["specname"] == "comp3"
    assert tmp[0]["platform"] == "x86_64-linux"
    assert tmp[0]["version"] == "3.0"
    assert tmp[0]["build_id"] == bid.id
    assert tmp[0]["build"] == bid.as_dict()
    assert isinstance(tmp[0]["attachments"], dict) and "myatt2" in tmp[0]["attachments"]


def test_bulk_query(store) -> None:
    with open("file1.txt", "w") as f:
        f.write("Carpette is a cat")

    with open("file2.txt", "w") as f:
        f.write("Carpette is a nice cat")

    bid = BuildInfo.create(store, "test", "1.0")
    f1 = File(
        build_id=bid.id,
        kind=FileKind.source,
        name="file1",
        filename="file1.txt",
        resource_path=os.path.abspath("file1.txt"),
        store=store,
    )
    f1.push()
    f2 = File(
        build_id=bid.id,
        kind=FileKind.thirdparty,
        name="file2",
        filename="file2.txt",
        resource_path=os.path.abspath("file2.txt"),
        store=store,
    )
    component = Component(
        build_id=bid.id,
        name="comp",
        platform="x86_64-linux",
        version="1.0",
        specname="comp",
        files=[f2],
        build_info=bid,
        store=store,
    )
    component.push()

    query_f2 = {"query": "source", "kind": "thirdparty"}
    tmp = store.bulk_query([query_f2])
    assert len(tmp) == 1
    assert tmp[0]["query"] == query_f2
    assert tmp[0]["msg"] == "Invalid source query: missing name"
    assert not tmp[0]["response"]

    query_f2["name"] = "file2"
    tmp = store.bulk_query([query_f2])
    assert len(tmp) == 1
    assert tmp[0]["query"] == query_f2
    assert not tmp[0]["msg"]
    assert tmp[0]["response"]["name"] == "file2"
    assert tmp[0]["response"]["kind"] == "thirdparty"

    query_f1 = {"query": "source", "name": "file1", "bid": bid.id}
    tmp = store.bulk_query([query_f1])
    assert len(tmp) == 1
    assert tmp[0]["query"] == query_f1
    assert not tmp[0]["msg"]
    assert tmp[0]["response"]["name"] == "file1"
    assert tmp[0]["response"]["kind"] == "source"

    del query_f1["bid"]
    tmp = store.bulk_query([query_f1])
    assert len(tmp) == 1
    assert tmp[0]["msg"] == "Invalid source query: missing build ID"
    assert not tmp[0]["response"]

    query_comp = {
        "query": "component",
        "setup": "test",
        "platform": "x86_64-linux",
        "name": "comp",
    }
    tmp = store.bulk_query([query_comp])
    assert len(tmp) == 1
    assert tmp[0]["query"] == query_comp
    assert not tmp[0]["msg"]
    assert tmp[0]["response"]["name"] == "comp"
    assert tmp[0]["response"]["build"]["setup"] == "test"
    assert tmp[0]["response"]["platform"] == "x86_64-linux"

    del query_comp["setup"]
    tmp = store.bulk_query([query_comp])
    assert len(tmp) == 1
    assert tmp[0]["msg"].startswith(
        "Invalid component query: one or more mandatory keys"
    )

    query_comp["setup"] = "test"
    del query_comp["query"]
    tmp = store.bulk_query([query_comp])
    assert len(tmp) == 1
    assert tmp[0]["msg"] == "Invalid query: missing 'query' key"

    query_comp["query"] = "notknow"
    tmp = store.bulk_query([query_comp])
    assert len(tmp) == 1
    assert tmp[0]["msg"] == "Invalid query type 'notknow'"

    query_comp = {
        "query": "component",
        "setup": "test",
        "platform": "x86-linux",
        "name": "comp",
    }
    tmp = store.bulk_query([query_comp])
    assert len(tmp) == 1
    assert tmp[0]["msg"] == "No component matching criteria"
