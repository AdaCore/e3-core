from __future__ import annotations

import os
import pytest
from typing import TYPE_CHECKING

from e3.fs import mkdir, mv

from e3.anod.store import LocalStore, StoreError
from e3.anod.store.buildinfo import BuildInfo
from e3.anod.store.component import Component
from e3.anod.store.file import File, FileKind

if TYPE_CHECKING:
    from e3.anod.store import StoreRW

DEFAULT_SETUP = "test"


def test_basic(store: StoreRW) -> None:
    """Check that we can create a component and retrieve it."""
    # First we have to create a build ID to be able to create the component
    build_id = store.create_build_id(DEFAULT_SETUP, "20241001", "1.0")["_id"]
    store.mark_build_ready(build_id)

    bid = BuildInfo.latest(store=store, setup=DEFAULT_SETUP)

    # A Component must contains some files
    with open("foo.txt", "w") as f:
        f.write("foo")

    binary = File(
        build_id=bid.id,
        kind=FileKind.binary,
        name="foo.txt",
        filename="foo.txt",
        build_info=bid,
        resource_path=os.path.abspath("foo.txt"),
    )

    with open("foo_attachment.txt", "w") as f:
        f.write("foo_attachment")

    att = File(
        build_id=bid.id,
        kind=FileKind.attachment,
        name="foo_attachment.txt",
        filename="foo_att.txt",
        build_info=bid,
        resource_path=os.path.abspath("foo_attachment.txt"),
    )

    with open("foo_readme.txt", "w") as f:
        f.write("foo_readme")

    readme = File(
        build_id=bid.id,
        kind=FileKind.attachment,
        name="foo_readme.txt",
        filename="foo_readme.txt",
        build_info=bid,
        resource_path=os.path.abspath("foo_readme.txt"),
    )

    with open("foo_source.txt", "w") as f:
        f.write("foo_source")

    source = File(
        build_id=bid.id,
        kind=FileKind.source,
        name="foo_source.txt",
        filename="foo_source.txt",
        build_info=bid,
        resource_path=os.path.abspath("foo_source.txt"),
        store=store,
    )
    # Sources must be pushed before the component. Sources will not be pushed
    # automatically since there are intended to already be in the database when creating
    # a component.
    source = source.push()

    # Now we can create the component and push it.
    c = Component(
        build_id=bid.id,
        build_info=bid,
        name="comp1",
        specname="comp1",
        platform="x86_64-linux",
        version="1.0",
        files=[binary],
        sources=[source],
        readme=readme,
        attachments={"foo_att": att},
        store=store,
    )
    c = c.push()

    # Now, we have a pushed component to a Database. Now we can check if we can add it
    # to the LocalStore
    with LocalStore(db="local-store.db", online_store=store) as local:
        local.add_component_from_store(from_store=store, setup=DEFAULT_SETUP)

        assert local._raw_add_build_info(bid.as_dict()) is False, (
            "The buildinfo has already been added to the local store. "
            "The function must return False."
        )
        # Should not raise any errors
        local.raw_add_build_info(bid.as_dict())
        local.add_build_info_from_store(from_store=store, bid=bid.id)

        assert local._raw_add_component(c.as_dict()) is False, (
            "The component has already been added to the local store. "
            "The function must return False."
        )
        # Should not raise any errors
        local.raw_add_component(c.as_dict())
        local.add_component_from_store(from_store=store, setup=DEFAULT_SETUP)

        assert local._raw_add_file(source.as_dict()) is False, (
            "The source has already been added to the local store. "
            "The function must return False."
        )
        # Should not raise any errors
        local.raw_add_file(source.as_dict())
        local.add_source_from_store(
            from_store=store, name="foo_source.txt", setup=DEFAULT_SETUP
        )
        local.add_source_from_store(from_store=store, name="foo_source.txt", bid=bid.id)

        comp_list = Component.latest(store=local, setup=DEFAULT_SETUP)

    assert len(comp_list) == 1, "Only one component pushed"
    comp = comp_list[0]
    assert comp == c, f"components are different: {comp.as_dict()} != {c.as_dict()}"


def test_add_build_info_from_store(store: StoreRW) -> None:
    build_id = store.create_build_id(DEFAULT_SETUP, "20241001", "1.0")["_id"]
    store.mark_build_ready(build_id)

    with LocalStore(db="bi.db", online_store=store) as local:
        # The build ID doesn't exist on the LocalStore. The code will first try to
        # read if this build ID already exist on the database. If not, an exception will
        # be raise and caught by the code: This mean we have to insert the new build
        # info.
        local.add_build_info_from_store(store, build_id)

        biinfo = local.get_latest_build_info(DEFAULT_SETUP)
        assert biinfo["setup"] == DEFAULT_SETUP
        assert biinfo["_id"] == build_id

    # Create a new buildinfo, we will tests its insertion using `add_source_from_store`.
    src_build_id = store.create_build_id(DEFAULT_SETUP, "20241002", "1.0")["_id"]
    store.mark_build_ready(src_build_id)

    with open("foo.txt", "w") as f:
        f.write("foo")

    File(
        build_id=src_build_id,
        kind=FileKind.source,
        name="foo.txt",
        filename="foo.txt",
        resource_path=os.path.abspath("foo.txt"),
        store=store,
    ).push()

    with LocalStore(db="source.db", online_store=store) as local:
        # This methods does basicaly the same thing that `add_build_info_from_store`.
        #
        # See the above comment for explanation.
        local.add_source_from_store(store, "foo.txt", src_build_id)

        biinfo = local.get_latest_build_info(DEFAULT_SETUP)
        assert biinfo["setup"] == DEFAULT_SETUP
        assert biinfo["_id"] == src_build_id


def test_insert_files_with_same_resource_id(store: StoreRW) -> None:
    build_id = store.create_build_id(DEFAULT_SETUP, "20241002", "1.0")["_id"]
    store.mark_build_ready(build_id)

    # Same file content ==> Same resource ID
    with open("f.txt", "w") as f:
        f.write("foo")

    f0 = File(
        build_id=build_id,
        kind=FileKind.source,
        name="f0.txt",
        filename="f0.txt",
        resource_path=os.path.abspath("f.txt"),
        store=store,
    ).push()

    f1 = File(
        build_id=build_id,
        kind=FileKind.source,
        name="f1.txt",
        filename="f1.txt",
        resource_path=os.path.abspath("f.txt"),
        store=store,
    ).push()

    assert f0.resource_id == f1.resource_id

    with LocalStore(db="same-rid.db", online_store=store) as local:
        # First insert f0.txt ==> Will create the corresponding resource
        local.add_source_from_store(store, "f0.txt", build_id)
        # Now the tests: Should not raise an error.
        #   insert f1.txt ==> Will create the corresponding file, but the resource will
        #                     not be created (already present)
        local.add_source_from_store(store, "f1.txt", build_id)

        # Now, we will move f.txt somewhere else and then we will create and add file2.
        # This will force the database to update the stored path to the resource.

        # Create a new directory and move f.txt into it.
        mkdir("fff")
        new_path = os.path.join("fff", "f.txt")
        mv("f.txt", new_path)

        # Create f2.txt and push it to the "online" store.
        f2 = File(
            build_id=build_id,
            kind=FileKind.source,
            name="f2.txt",
            filename="f2.txt",
            resource_path=os.path.abspath(new_path),
            store=store,
        ).push()

        assert f0.resource_id == f2.resource_id

        local.add_source_from_store(store, "f2.txt", build_id)


def test_component_with_attachments_list(store: StoreRW) -> None:
    build_id = store.create_build_id(DEFAULT_SETUP, "20241001", "1.0")["_id"]
    store.mark_build_ready(build_id)

    bid = BuildInfo.latest(store=store, setup=DEFAULT_SETUP)

    # A Component must contains some files
    with open("foo.txt", "w") as f:
        f.write("foo")
    with open("foo_attachment.txt", "w") as f:
        f.write("foo_attachment")
    with open("foo_source.txt", "w") as f:
        f.write("foo_source")

    binary = File(
        build_id=bid.id,
        kind=FileKind.binary,
        name="foo.txt",
        filename="foo.txt",
        build_info=bid,
        resource_path=os.path.abspath("foo.txt"),
    )

    att = File(
        build_id=bid.id,
        kind=FileKind.attachment,
        name="foo_attachment.txt",
        filename="foo_att.txt",
        build_info=bid,
        resource_path=os.path.abspath("foo_attachment.txt"),
    )

    # Sources must be pushed before the component. Sources will not be pushed
    # automatically since there are intended to already be in the database when creating
    # a component.
    source = File(
        build_id=bid.id,
        kind=FileKind.source,
        name="foo_source.txt",
        filename="foo_source.txt",
        build_info=bid,
        resource_path=os.path.abspath("foo_source.txt"),
        store=store,
    ).push()

    att_list = [{"name": "foo_att", "att_file": att.as_dict()}]

    # Now we can create the component and push it.
    c = Component(
        build_id=bid.id,
        build_info=bid,
        name="comp",
        specname="comp",
        platform="x86_64-linux",
        version="1.0",
        files=[binary],
        sources=[source],
        attachments=att_list,
        store=store,
    ).push()

    c_dict = c.as_dict()
    att_list[0]["att_file"] = c.attachments["foo_att"].as_dict()
    c_dict["attachments"] = att_list

    with LocalStore(db="att-list.db", online_store=store) as local:
        local._raw_add_component(c_dict)


def test_exceptions(store: StoreRW) -> None:
    with LocalStore(db="empty.db", online_store=store) as local:
        with pytest.raises(
            StoreError,
            match="Cannot find any component matching the following criteria",
        ):
            local.add_component_from_store(store, DEFAULT_SETUP, name="doesnt-exist")


def test_bulk_update(store: StoreRW) -> None:
    with open("file1.txt", "w") as f:
        f.write("Carpette is a cat")
    with open("file2.txt", "w") as f:
        f.write("Carpette is a nice cat")

    bid = BuildInfo.create(store, DEFAULT_SETUP, "1.0", mark_ready=True)

    src = File(
        build_id=bid.id,
        kind=FileKind.source,
        name="src",
        filename="file1.txt",
        resource_path=os.path.abspath("file1.txt"),
        store=store,
    ).push()
    tp = File(
        build_id=bid.id,
        kind=FileKind.thirdparty,
        name="tp",
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
        files=[tp],
        build_info=bid,
        store=store,
    ).push()
    with LocalStore(db="bulk-update.db", online_store=store) as local:
        query_tp = {"query": "source", "kind": "thirdparty", "name": "tp"}
        tmp = local.bulk_update_from_store(store, [query_tp])
        assert len(tmp) == 1, tmp
        tmp_query = tmp[0]["query"]
        tmp_query.pop("bid")
        assert tmp_query == query_tp, tmp[0]

        assert not tmp[0]["msg"], tmp[0]
        assert tmp[0]["response"] == component.files[0].as_dict(), tmp[0]

        query_src = {"query": "source", "name": "src", "bid": bid.id}
        tmp = local.bulk_update_from_store(store, [query_src])
        assert len(tmp) == 1, tmp
        tmp_query = tmp[0]["query"]
        tmp_query.pop("kind")
        assert tmp_query == query_src, tmp[0]
        assert not tmp[0]["msg"], tmp[0]
        assert tmp[0]["response"] == src.as_dict()

        query_comp = {
            "query": "component",
            "setup": DEFAULT_SETUP,
            "platform": "x86_64-linux",
            "name": "comp",
        }
        tmp = local.bulk_update_from_store(store, [query_comp])
        assert len(tmp) == 1, tmp
        assert tmp[0]["query"] == query_comp, tmp[0]
        assert not tmp[0]["msg"], tmp[0]
        assert tmp[0]["response"] == component.as_dict()

        # Try to re-push the query_tp
        query_tp = {
            "query": "source",
            "kind": "thirdparty",
            "name": "tp",
            "setup": DEFAULT_SETUP,
        }
        tmp = local.bulk_update_from_store(store, [query_tp])
        assert len(tmp) == 1, tmp
        tmp_query = tmp[0]["query"]
        tmp_query.pop("bid")
        assert tmp_query == query_tp, tmp[0]
