from __future__ import annotations

import json
import os
import pytest
from datetime import datetime
from time import sleep

from e3.archive import create_archive
from e3.anod.store import StoreError
from e3.anod.store.interface import resource_id
from e3.anod.store.file import File, FileKind
from e3.anod.store.component import Component
from e3.anod.store.buildinfo import BuildInfo
from e3.dsse import DSSE
from e3.slsa.provenance import Statement

from e3.fs import mkdir
from e3.os.fs import touch

DEFAULT_SETUP = "test"


def test_file_metadata(store) -> None:  # type: ignore[no-untyped-def]
    """Check component metadata APIs."""
    metadata: dict[str, object] = {
        "one": 1,
        "two": "two",
        "three": {1: 1, 2: 2},
        "none": None,
        "list": '["one", "two"]',
    }
    bid = BuildInfo.create(store=store, setup=DEFAULT_SETUP, version="1.0")
    with open("toto.txt", "w") as fio:
        fio.write("XXXX")
    binary = File(
        build_id=bid.id,
        kind=FileKind.binary,
        name="toto.txt",
        filename="toto.txt",
        build_info=bid,
        resource_path=os.path.abspath("toto.txt"),
        metadata=metadata,
        store=store,
    )

    # Add a metadata statement
    statement: Statement = Statement(
        statement_type=Statement.SCHEMA_TYPE_VALUE, subject=[]
    )
    binary.set_metadata_statement(
        "provenance",
        DSSE(body=statement.as_json(), payload_type="application/provenance-data+json"),
    )
    comp = Component(
        build_id=bid.id,
        build_info=bid,
        name="comp1",
        specname="comp1",
        platform="x86_64-linux",
        version="1.0",
        files=[binary],
        store=store,
    )
    comp.push()

    # Retrieve the component from cathod, and check metadata
    comp_list = Component.latest(store=store, setup=DEFAULT_SETUP)
    assert len(comp_list) == 1, "Too many registered components"
    latest_comp: Component = comp_list[0]
    assert len(latest_comp.files) == 1
    latest_file = latest_comp.files[0]
    assert "provenance" in latest_file.metadata, "Missing provenance metadata"
    latest_statement: DSSE = latest_file.get_metadata_statement("provenance")
    assert isinstance(
        latest_statement, DSSE
    ), f"Invalid provenance metadata type ({latest_statement.__class__.__name__}!r)"
    # Now compare the retrieved statement
    assert (
        Statement.load_json(latest_statement.body) == statement
    ), "Statement metadata has been modified"
    # Check initial metadata values
    for key, value in metadata.items():
        print(latest_file.metadata, type(latest_file.metadata))
        if isinstance(value, dict):
            # Compare through JSON
            assert json.dumps(latest_file.metadata[key], sort_keys=True) == json.dumps(
                value, sort_keys=True
            )
        else:
            assert (
                latest_file.metadata[key] == value
            ), "Missing key/value pair in metadata"

    # More code coverage for the get_metadata_statement() method
    assert latest_file.get_metadata_statement("none") is None
    with pytest.raises(TypeError) as te:
        latest_file.get_metadata_statement("one")
    assert "the JSON object must be" in te.value.args[0]
    with pytest.raises(json.decoder.JSONDecodeError) as jde:
        latest_file.get_metadata_statement("two")
    assert "Expecting value" in jde.value.args[0]

    with pytest.raises(TypeError) as lte:
        latest_file.get_metadata_statement("list")
    assert "Corrupted metadata:" in lte.value.args[0]

    # More code coverage for the set_metadata_statement() method

    with pytest.raises(StoreError) as ce:
        binary.set_metadata_statement("Not-a-DSSE", None)
    assert "Metadata statement should be a DSSE envelope." in ce.value.args[0]


def test_update_metadata(store) -> None:
    build_id = store.create_build_id(DEFAULT_SETUP, "20241001", "1.0")["_id"]
    store.mark_build_ready(build_id)
    with open("my-src", "w") as fd:
        fd.write("Random content")

    rid = resource_id("my-src")
    store.submit_file(
        {
            "name": "my-src",
            "kind": "source",
            "alias": "my-src",
            "filename": "my-src",
            "revision": "",
            "metadata": None,
            "build_id": build_id,
            "resource_id": rid,
            "downloaded_as": "my-src",
        }
    )
    bid = BuildInfo.latest(store=store, setup=DEFAULT_SETUP)
    source = bid.get_source_list()[0]
    assert source.name == "my-src"
    metadata = source.get_metadata_statement("my-metadata")
    assert metadata is None
    with pytest.raises(StoreError):
        source.set_metadata_statement("my-metadata", "random data")
    source.set_metadata_statement("my-metadata", DSSE("random data", ""))
    metadata = source.get_metadata_statement("my-metadata")
    assert metadata is not None
    assert metadata.body == b"random data"

    source.update_metadata()

    tmp = store.get_source_info("my-src", build_id)
    assert tmp["_id"] == source.file_id
    assert tmp["metadata"] is not None
    assert tmp["metadata"] == source.metadata


def test_push(store):
    bid = BuildInfo.create(store, DEFAULT_SETUP, "1.0")

    with open("myfile.txt", "x") as f:
        f.write("xxxxx")

    f = File(
        build_id=bid.id,
        kind=FileKind.source,
        name="myfile",
        filename="myfile.txt",
        resource_id=store.resource_id("myfile.txt"),
        internal=True,
        resource_path="myfile.txt",
        store=store,
    )
    assert str(f) == "myfile:FileKind.source:None"
    tmp = f.push()
    assert isinstance(tmp, File)
    assert tmp is not f
    assert tmp == f
    assert f.file_id is not None
    assert tmp.file_id is not None
    assert str(f) == f"myfile:FileKind.source:{tmp.file_id}"

    store_data = store.get_source_info("myfile", bid.id, kind="source")
    other = File.load(data=store_data, store=store)
    assert other == tmp and other == f


def test_download(store):
    build_id = store.create_build_id(DEFAULT_SETUP, "20241001", "1.0")["_id"]
    store.mark_build_ready(build_id)
    with open("my-src", "w") as fd:
        fd.write("Random content")

    resource_id1 = resource_id("my-src")
    store.submit_file(
        {
            "name": "my-src",
            "kind": "source",
            "alias": "my-src",
            "filename": "my-src",
            "revision": "",
            "metadata": None,
            "build_id": build_id,
            "resource_id": resource_id1,
            "downloaded_as": "my-src",
        }
    )

    bid = BuildInfo.latest(store=store, setup=DEFAULT_SETUP)
    source = bid.get_source_list()[0]
    assert source.name == "my-src"

    mkdir("sandbox")
    source.download(dest_dir="sandbox")
    mtime1 = os.path.getmtime(source.downloaded_as)
    meta_file = os.path.join("sandbox", source.name + "_meta.json")
    assert os.path.isfile(meta_file)

    sleep(1.0)
    source.download(dest_dir="sandbox")
    mtime2 = os.path.getmtime(source.downloaded_as)
    assert mtime1 == mtime2

    with open(source.downloaded_as, "r") as fd:
        content = fd.read()
        assert content == "Random content"

    source2 = File.load_from_meta_file(
        dest_dir="sandbox", name=source.name, store=store
    )
    assert source2.file_id == source.file_id

    with pytest.raises(StoreError):
        source.download(dest_dir="non-existent")

    with open("my-src", "w") as fd:
        fd.write("New content")

    resource_id2 = resource_id("my-src")
    store.submit_file(
        {
            "name": "my-src",
            "kind": "source",
            "alias": "my-src",
            "filename": "my-src",
            "revision": "",
            "metadata": None,
            "build_id": build_id,
            "resource_id": resource_id2,
            "downloaded_as": "my-src",
        }
    )
    source = bid.get_source_list()[0]
    assert source.name == "my-src"
    assert source.resource_id == resource_id2

    source.download(dest_dir="sandbox")
    mtime2 = os.path.getmtime(source.downloaded_as)
    assert mtime1 != mtime2

    with open(source.downloaded_as, "r") as fd:
        content = fd.read()
        assert content == "New content"

    mkdir("atest0")
    mkdir("atest1")
    assert source.download(dest_dir="atest0")
    assert source.download(dest_dir="atest1")


def test_download_as_name(store):
    build_id = store.create_build_id(DEFAULT_SETUP, "20241001", "1.0")["_id"]
    store.mark_build_ready(build_id)
    touch("my-src")
    store.submit_file(
        {
            "name": "my-src",
            "kind": "source",
            "alias": "my-src",
            "filename": "my-src.tar.gz",
            "revision": "",
            "metadata": None,
            "build_id": build_id,
            "resource_id": "zeufizebfizub",
            "downloaded_as": "my-src",
        }
    )
    del build_id

    bid = BuildInfo.latest(store=store, setup=DEFAULT_SETUP)
    source = bid.get_source_list()[0]

    assert source.name == "my-src"

    mkdir("sandbox")
    source.download(dest_dir="sandbox", as_name="new_name")
    assert os.path.basename(source.downloaded_as) == "new_name.tar.gz"
    assert os.path.isfile(os.path.join("sandbox", "new_name_meta.json"))


def test_corrupted_meta_file(store):
    build_id = store.create_build_id(DEFAULT_SETUP, "20241001", "1.0")["_id"]
    store.mark_build_ready(build_id)
    touch("my-src")
    store.submit_file(
        {
            "name": "my-src",
            "kind": "source",
            "alias": "my-src",
            "filename": "my-src",
            "revision": "",
            "metadata": None,
            "build_id": build_id,
            "resource_id": "zeufizebfizub",
            "downloaded_as": "my-src",
        }
    )
    del build_id

    bid = BuildInfo.latest(store=store, setup=DEFAULT_SETUP)
    source = bid.get_source_list()[0]

    assert source.name == "my-src"

    mkdir("sandbox")
    source.download(dest_dir="sandbox", as_name="new_name")
    meta_file = os.path.join("sandbox", "new_name_meta.json")
    with open(meta_file, "w") as fd:
        fd.write("{{")
    source.download(dest_dir="sandbox", as_name="new_name")
    source2 = File.load_from_meta_file(dest_dir="sandbox", name="new_name", store=store)
    assert source2.file_id == source.file_id

    with pytest.raises(StoreError, match="non existing metafile"):
        File.load_from_meta_file(dest_dir="notexist", name="notexist_name", store=store)

    meta_file = File.metadata_path(dest_dir="sandbox", name="new_name")
    with open(meta_file, "r+") as f:
        data = json.load(f)
        del data["_id"]
        f.write(json.dumps(data, indent=2))

    with pytest.raises(StoreError, match="error while loading metadata file"):
        File.load_from_meta_file(dest_dir="sandbox", name="new_name", store=store)


def test_upload_thirdparty(store):
    bid = store.create_build_id("thirdparties", "20271031", "1.0")["_id"]
    store.mark_build_ready(bid)
    del bid

    with open("test.txt", "w") as fd:
        fd.write("This is a test")

    result = File.upload_thirdparty(store=store, path="test.txt")
    assert result.file_id is not None

    mkdir("downloads")
    downloaded = result.download(dest_dir="downloads")
    assert downloaded

    with pytest.raises(StoreError):
        File.upload_thirdparty(store=store, path="test.txt")

    with open("test.txt", "w") as fd:
        fd.write("This is a new content")
    result = File.upload_thirdparty(store=store, path="test.txt", force=True)

    downloaded = result.download(dest_dir="downloads")
    assert downloaded
    with open(result.downloaded_as, "r") as fd:
        content = fd.read()
        assert content == "This is a new content"


def test_upload_thirdparty_from_dir(store):
    bid = store.create_build_id("thirdparties", "20271031", "1.0")["_id"]
    store.mark_build_ready(bid)
    del bid

    mkdir("test")
    today = datetime.now().strftime("%Y%m%d")
    with open("test/test.txt", "w") as fd:
        fd.write("This is a test")

    result = File.upload_thirdparty_from_dir(store=store, path="test", prefix="foo")
    assert result == f"foo-{today}.tgz"

    result = File.upload_thirdparty_from_dir(
        store=store, path="test", prefix="foo", build_dir="test"
    )
    assert result == f"foo-{today}-1.tgz"

    for idx in range(2, 10):
        result = File.upload_thirdparty_from_dir(store=store, path="test", prefix="foo")
        assert result == f"foo-{today}-{idx}.tgz"

    # Reject too many tries
    with pytest.raises(StoreError):
        File.upload_thirdparty_from_dir(store=store, path="test", prefix="foo")


def test_download_and_unpack(store):
    build_id = store.create_build_id(DEFAULT_SETUP, "20241001", "1.0")["_id"]
    store.mark_build_ready(build_id)

    mkdir("archive_root")
    touch("archive_root/file1.txt")
    touch("archive_root/file2.txt")
    create_archive(filename="archive-src.tar.gz", from_dir="archive_root", dest=".")
    store.submit_file(
        {
            "name": "archive-src",
            "kind": "source",
            "alias": "archive-src",
            "filename": "archive-src.tar.gz",
            "revision": "",
            "metadata": None,
            "build_id": build_id,
            "resource_id": "zeufizebfizub",
            "downloaded_as": "archive-src.tar.gz",
        }
    )
    touch("invalid-src.tar.gz")
    store.submit_file(
        {
            "name": "invalid-src",
            "kind": "source",
            "alias": "invalid-src",
            "filename": "invalid-src.tar.gz",
            "revision": "",
            "metadata": None,
            "build_id": build_id,
            "resource_id": "aiuzdbzedoezfiribgier",
            "downloaded_as": "invalid-src.tar.gz",
        }
    )

    bid = BuildInfo.latest(store=store, setup=DEFAULT_SETUP)
    source = bid.get_source_info(name="archive-src")
    mkdir("sandbox/pkg")
    downloaded = source.download(dest_dir="sandbox", unpack_dir="sandbox/pkg")
    assert downloaded
    assert os.path.isfile("sandbox/pkg/file1.txt")

    downloaded = source.download(dest_dir="sandbox", unpack_dir="sandbox/pkg")
    assert not downloaded

    mkdir("sandbox/pkg2")
    downloaded = source.download(dest_dir="sandbox", unpack_dir="sandbox/pkg2")
    assert downloaded

    # Test with dest_dir set to None
    mkdir("sandbox/pkg3")
    downloaded = source.download(dest_dir=None, unpack_dir="sandbox/pkg3")
    assert downloaded
    assert source.downloaded_as is None

    # Test with non existent unpack dir
    with pytest.raises(StoreError):
        source.download(dest_dir="sandbox", unpack_dir="sandbox/non-existent")

    # Test with invalid archive
    source = bid.get_source_info(name="invalid-src")
    with pytest.raises(StoreError):
        source.download(dest_dir="sandbox", unpack_dir="sandbox/non-existent")


def test_file_eq_neq():
    ref_f = File(
        build_id="a" * 24,
        kind=FileKind.source,
        name="gdb-8.3-src",
        filename="gdb-8.3-src.tar.gz",
        resource_id="b" * 24,
        internal=True,
    )

    # First things first, verify that comparison with an unrelated
    # object works and returns the expected answer...

    assert (ref_f == {}) is False
    assert (ref_f != {}) is True

    # Create another File object using the same parameters as when
    # we created ref_f. Comparing those two should say they are equal.

    f = File(
        build_id=ref_f.build_id,
        kind=ref_f.kind,
        name=ref_f.name,
        filename=ref_f.filename,
        resource_id=ref_f.resource_id,
        internal=ref_f.internal,
    )

    assert (ref_f == f) is True
    assert (ref_f != f) is False

    # Now, iterate over each attribute, and created a File that's
    # almost identical to ref_f, except for the one attribute
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
    #   - A boolean indicating the modified file is still expected
    #     to be equal to the unmodified one.
    TESTING_PLAN = {
        # Attributes which affect comparison...
        "file_id": ("c" * 24, False),
        "build_id": ("d" * 24, False),
        "kind": (FileKind.thirdparty, False),
        "name": ("new-src", False),
        "filename": ("new-src.tar.gz", False),
        "resource_id": ("e" * 24, False),
        "internal": (False, False),
        "alias": ("new-alias", False),
        "revision": ("rev20", False),
        "metadata": ("unimportant", False),
        "build_info": ("unimportant", False),
        # Attributes that do not affect comparison...
        "downloaded_as": ("/path/to/download/src.tar.gz", True),
        "unpack_dir": ("/path/to/unpack/src", True),
        "store": ("unimportant", True),
    }

    # Verify that the TESTING_PLAN above covers all attributes
    # of class File.
    assert sorted(TESTING_PLAN.keys()) == sorted(f.__dict__.keys())

    for attr_name in list(TESTING_PLAN.keys()):
        new_val, still_equal = TESTING_PLAN[attr_name]

        f = File(
            build_id=ref_f.build_id,
            kind=ref_f.kind,
            name=ref_f.name,
            filename=ref_f.filename,
            resource_id=ref_f.resource_id,
            internal=ref_f.internal,
        )
        setattr(f, attr_name, new_val)

        assert (ref_f == f) is still_equal
        assert (ref_f != f) is not still_equal
