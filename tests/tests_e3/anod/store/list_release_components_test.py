from __future__ import annotations

import os

from e3.anod.store.buildinfo import BuildInfo
from e3.anod.store.file import File, FileKind
from e3.anod.store.component import Component
from e3.os.fs import touch

DEFAULT_SETUP = "test"


def test_list_release_components(store):
    # Use store to simplify the initialization phase.
    build_id = store.create_build_id(DEFAULT_SETUP, "20241001", "1.0")["_id"]
    store.mark_build_ready(build_id)
    del build_id

    bid = BuildInfo.latest(store=store, setup=DEFAULT_SETUP)
    touch("test1.txt")
    touch("test2.txt")

    file1 = File(
        build_id=bid.id,
        kind=FileKind.binary,
        name="test1.txt",
        filename="test1.txt",
        build_info=bid,
        resource_path=os.path.abspath("test1.txt"),
    )
    file2 = File(
        build_id=bid.id,
        kind=FileKind.binary,
        name="test2.txt",
        filename="test2.txt",
        build_info=bid,
        resource_path=os.path.abspath("test2.txt"),
    )

    comp1 = Component(
        build_id=bid.id,
        build_info=bid,
        name="comp1",
        releases=["release-1"],
        specname="comp1",
        platform="x86_64-linux",
        version="1.0",
        files=[file1],
        store=store,
    )
    comp1.push()

    comp2 = Component(
        build_id=bid.id,
        build_info=bid,
        name="comp2",
        releases=["release-1"],
        specname="comp2",
        platform="aarch64-linux",
        version="2.0",
        files=[file2],
        store=store,
    )
    comp2.push()

    comp_list = store.list_release_components(name="release-1")
    assert len(comp_list) == 2

    tmp0 = Component.load(comp_list[0])
    tmp1 = Component.load(comp_list[1])
    assert tmp0 != tmp1
    assert tmp0 == comp1 or tmp0 == comp2
    assert tmp1 == comp1 or tmp1 == comp2

    comp_list = store.list_release_components(name="release-1", component="comp1")
    assert len(comp_list) == 1
    tmp0 = Component.load(comp_list[0])
    assert tmp0 == comp1

    comp_list = store.list_release_components(name="release-1", version="1.0")
    assert len(comp_list) == 1
    tmp0 = Component.load(comp_list[0])
    assert tmp0 == comp1

    comp_list = store.list_release_components(
        name="release-1", platform="aarch64-linux"
    )
    assert len(comp_list) == 1
    tmp0 = Component.load(comp_list[0])
    assert tmp0 == comp2

    comp_list = store.list_release_components(
        name="release-1", component="comp1", version="1.0", platform="x86_64-linux"
    )
    assert len(comp_list) == 1
    tmp0 = Component.load(comp_list[0])
    assert tmp0 == comp1
