# type: ignore
from __future__ import annotations

import datetime
import json
import os
from pathlib import Path
import pytest
from typing import TYPE_CHECKING
import time

from e3.anod.store.interface import StoreError
from e3.anod.store.buildinfo import BuildInfo
from e3.anod.store.component import Component
from e3.anod.store.file import File, FileKind
from e3.dsse import DSSE
from e3.os.fs import touch
from e3.slsa.provenance import Statement

if TYPE_CHECKING:
    from e3.anod.store.component import ComponentDict

DEFAULT_SETUP = "test"


def create_component_with_attachments() -> tuple[Component, File, File]:
    """Create a dummy component with two attached files.

    Only the first returned file is already attached to the component.
    """
    Path("toto_attachment.txt").touch()
    Path("toto_attachment2.txt").touch()
    # Store File must exist, or the sha1 will fail to be computed.
    att_1 = File(
        build_id="dummy.id",
        kind=FileKind.attachment,
        name="toto_attachment.txt",
        filename="toto_att.txt",
        build_info=None,
        resource_path=os.path.abspath("toto_attachment.txt"),
    )
    att_2 = File(
        build_id="dummy.id2",
        kind=FileKind.attachment,
        name="toto_attachment2.txt",
        filename="toto_att2.txt",
        build_info=None,
        resource_path=os.path.abspath("toto_attachment2.txt"),
    )
    c = Component(
        build_id="dummy.id",
        build_info=None,
        name="comp1",
        specname="comp1",
        platform="x86_64-linux",
        version="1.0",
        files=[],
        attachments={"toto_att": att_1},
        store=None,
    )

    return c, att_1, att_2


def push_component(store, metadata: dict[str, object] | None = None) -> Component:
    build_id = store.create_build_id(DEFAULT_SETUP, "20241001", "1.0")["_id"]
    store.mark_build_ready(build_id)
    del build_id

    bid = BuildInfo.latest(store=store, setup=DEFAULT_SETUP)
    touch("toto.txt")
    touch("toto_attachment.txt")

    binary = File(
        build_id=bid.id,
        kind=FileKind.binary,
        name="toto.txt",
        filename="toto.txt",
        build_info=bid,
        resource_path=os.path.abspath("toto.txt"),
    )
    att = File(
        build_id=bid.id,
        kind=FileKind.attachment,
        name="toto_attachment.txt",
        filename="toto_att.txt",
        build_info=bid,
        resource_path=os.path.abspath("toto_attachment.txt"),
    )

    c = Component(
        build_id=bid.id,
        build_info=bid,
        name="comp1",
        specname="comp1",
        platform="x86_64-linux",
        version="1.0",
        files=[binary],
        attachments={"toto_att": att},
        store=store,
        metadata=metadata,
    )
    return c.push()


def test_component_push(store):
    """Check that we can create a component and retrieve it."""
    c = push_component(store=store)
    comp_list = Component.latest(store=store, setup=DEFAULT_SETUP)
    assert len(comp_list) == 1, "Only one component pushed"
    comp = comp_list[0]

    assert comp == c, f"components are different: {comp.as_dict()} != {c.as_dict()}"


def test_component_eq_ne():
    ref_build_id = "a" * 24

    ref_date = datetime.datetime.now(datetime.timezone.utc)

    ref_src = File(
        build_id=ref_build_id,
        kind=FileKind.source,
        name="gdb-8.3-src",
        filename="gdb-8.3-src.tar.gz",
        resource_id="b" * 24,
        internal=False,
    )

    ref_binary = File(
        build_id=ref_build_id,
        kind=FileKind.binary,
        name="gdb-8.3-x86_64-linux-bin",
        filename="gdb-8.3-x86_64-linux-bin.tar.gz",
        resource_id="c" * 24,
        internal=False,
    )

    ref_c = Component(
        build_id=ref_build_id,
        name="gdb",
        specname="gdb",
        platform="x86_64-linux",
        version="121.5",
        files=[ref_binary],
        sources=[ref_src],
        creation_date=ref_date,
    )

    # First things first, verify that comparison with an unrelated
    # object works and returns the expected answer...

    assert (ref_c == {}) is False
    assert (ref_c != {}) is True

    # A slightly different File object to use as binary and source.
    # The purpose is to use those to demonstrate that changing
    # the contents of a File causes the Component to become non-equal.

    src = File(
        build_id=ref_build_id,
        kind=ref_src.kind,
        name=ref_src.name,
        filename=ref_src.filename,
        resource_id="d" * 24,
        internal=False,
    )

    binary = File(
        build_id=ref_build_id,
        kind=ref_binary.kind,
        name=ref_binary.name,
        filename=ref_binary.filename,
        resource_id="e" * 24,
        internal=False,
    )

    # Create another Component using the same parameters as when
    # we created ref_c. Comparing those two should say they are equal.

    c = Component(
        build_id=ref_c.build_id,
        name=ref_c.name,
        specname=ref_c.specname,
        platform=ref_c.platform,
        version=ref_c.version,
        files=[ref_binary],
        sources=[ref_src],
        creation_date=ref_date,
    )

    assert (ref_c == c) is True
    assert (ref_c != c) is False

    # Now, iterate over each attribute, and created a Component
    # that's almost identical to ref_c, except for the one attribute
    # that's different, and then evaluate equality.
    #
    # We perform this check in a systematic way to force us to revisit the
    # implementation of equality/non-equality each time we add/remove an
    # attribute, to avoid introducing subtle bugs related to this feature.

    # A dictionary where, for each attribute of File, we have one
    # element where the key is that attribute name, and the value
    # is a tuple with the following elements:
    #   - A new value to use when modifying this attribute;
    #   - A boolean indicating the modified component is still expected
    #     to be equal to the unmodified one.
    testing_plan = {
        # Attributes which affect comparison...
        "component_id": ("c" * 24, False),
        "build_id": ("d" * 24, False),
        "name": ("new-gdb", False),
        "specname": ("new-gdb", False),
        "platform": ("arm-elf-windows64", False),
        "version": ("243.0", False),
        "files": ([binary], False),
        "sources": ([src], False),
        "readme": ("whatever", False),
        "attachments": ("does not matter", False),
        "releases": (["XX"], False),
        "is_valid": (not c.is_valid, False),
        "is_published": (not c.is_published, False),
        "build_info": ("whatever", False),
        "creation_date": ("some date", False),
        "metadata": ({"some": "dict"}, False),
        # Attributes that do not affect comparison...
        "store": ("unimportant", True),
    }

    # Verify that the TESTING_PLAN above covers all attributes
    # of class File.
    assert sorted(testing_plan.keys()) == sorted(c.__dict__.keys())

    for attr_name in list(testing_plan.keys()):
        # Ignore hidden attributes.
        if attr_name.startswith("_"):
            continue

        new_val, still_equal = testing_plan[attr_name]

        c = Component(
            build_id=ref_c.build_id,
            name=ref_c.name,
            specname=ref_c.specname,
            platform=ref_c.platform,
            version=ref_c.version,
            files=[ref_binary],
            sources=[ref_src],
            creation_date=ref_date,
        )
        setattr(c, attr_name, new_val)

        assert (ref_c == c) is still_equal, attr_name
        assert (ref_c != c) is not still_equal, attr_name


def test_component_attachment(caplog) -> None:  # type: ignore[no-untyped-def]
    """Check component attachment APIs."""
    c, att_1, att_2 = create_component_with_attachments()

    # Get all attachments.
    attachments = c.get_attachments()
    assert len(attachments) == 1
    assert attachments["toto_att"].as_dict() == att_1.as_dict()

    # Add an attachment with the same key, it should be ok, we'll get two
    # attachments.
    att2_key: str | None = c.add_attachment("toto_att", att_2)
    assert isinstance(att2_key, str)

    # Get all attachments of type "toto_att"
    attachments = c.get_attachments("toto_att")
    assert len(attachments) == 2
    assert attachments[att2_key].as_dict() == att_2.as_dict()

    # Try to add an existing attachment. The key should be None as we did not
    # use the overwrite_existing parameter.
    att2_key = c.add_attachment("toto_att", att_2)
    assert att2_key is None

    # Try to add an existing attachment. The key should NOT be None as used the
    # overwrite_existing parameter.
    att2_key = c.add_attachment("toto_att", att_2, overwrite_existing=True)
    assert att2_key is not None
    assert attachments[att2_key].as_dict() == att_2.as_dict()

    # Remove all attachments.
    removed = c.remove_attachment()

    assert removed is True
    assert len(c.get_attachments()) == 0

    # Add an attachment again for more testing.
    att2_key = c.add_attachment("toto_att", att_2)

    # Try with the full key.
    removed = c.remove_attachment(att2_key)
    assert removed is True
    assert len(c.get_attachments()) == 0


def test_component_metadata(store) -> None:  # type: ignore[no-untyped-def]
    """Check component metadata APIs."""
    metadata: dict[str, object] = {
        "one": 1,
        "two": "two",
        "three": {1: 1, 2: 2},
        "none": None,
        "list": '["one", "two"]',
    }
    comp: Component = push_component(store=store, metadata=metadata)

    # !!! The creation date field, used to retrieve the latest component, has a
    # precision of seconds. When two consecutive component pushes are done, like in
    # this test, it may result in two components with the same creation_date field.
    #
    # To avoid this error and make a better fix, we will simply sleep for one second
    # between two pushes.
    time.sleep(1)

    # Add a metadata statement
    statement: Statement = Statement(
        statement_type=Statement.SCHEMA_TYPE_VALUE, subject=[]
    )
    comp.set_metadata_statement(
        "provenance",
        DSSE(body=statement.as_json(), payload_type="application/provenance-data+json"),
    )
    comp.push()

    # Retrieve the component from store, and check metadata
    comp_list = Component.latest(store=store, setup=DEFAULT_SETUP)
    assert len(comp_list) == 1, "Too many registered components"
    latest_comp: Component = comp_list[0]
    assert "provenance" in latest_comp.metadata, "Missing provenance metadata"
    latest_statement: DSSE = latest_comp.get_metadata_statement("provenance")
    assert isinstance(
        latest_statement, DSSE
    ), f"Invalid provenance metadata type ({latest_statement.__class__.__name__}!r)"
    # Now compare the retrieved statement
    assert (
        Statement.load_json(latest_statement.body) == statement
    ), "Statement metadata has been modified"
    # Check initial metadata values
    for key, value in metadata.items():
        if isinstance(value, dict):
            # Compare through JSON
            assert json.dumps(latest_comp.metadata[key], sort_keys=True) == json.dumps(
                value, sort_keys=True
            )
        else:
            assert (
                latest_comp.metadata[key] == value
            ), "Missing key/value pair in metadata"

    # More code coverage for the get_metadata_statement() method
    assert latest_comp.get_metadata_statement("none") is None
    with pytest.raises(TypeError, match="the JSON object must be"):
        latest_comp.get_metadata_statement("one")
    # assert "the JSON object must be" in te.value.args[0]
    with pytest.raises(json.decoder.JSONDecodeError, match="Expecting value"):
        latest_comp.get_metadata_statement("two")

    with pytest.raises(TypeError, match="Corrupted metadata:"):
        latest_comp.get_metadata_statement("list")

    # More code coverage for the set_metadata_statement() method
    with pytest.raises(
        StoreError, match="Metadata statement should be a DSSE envelope."
    ):
        comp.set_metadata_statement("Not-a-DSSE", None)


def test_compononent_submit_attachment(store) -> None:  # type: ignore[no-untyped-def]
    """Make sure it is possible to submit an attachment to Store."""
    # First create a component
    build_id = store.create_build_id(DEFAULT_SETUP, "20241001", "1.0")["_id"]
    store.mark_build_ready(build_id)
    del build_id

    bid = BuildInfo.latest(store=store, setup=DEFAULT_SETUP)
    touch("toto.txt")
    att1: Path = Path("att1.txt")
    att2: Path = Path("att2.txt")
    with att1.open("w") as f:
        f.write("First attachment.")
    with att2.open("w") as f:
        f.write("Attachment added with Component.submit_attachment().")

    binary = File(
        build_id=bid.id,
        kind=FileKind.binary,
        name="toto.txt",
        filename="toto.txt",
        build_info=bid,
        resource_path=os.path.abspath("toto.txt"),
    )

    c = Component(
        build_id=bid.id,
        build_info=bid,
        name="comp1",
        specname="comp1",
        platform="x86_64-linux",
        version="1.0",
        files=[binary],
        store=store,
    )
    att_file: File = File(
        build_id=c.build_id,
        kind=FileKind.attachment,
        name=os.path.basename(att1),
        filename=os.path.basename(att1),
        internal=True,
        resource_path=str(att1),
    )
    c.add_attachment("test", att_file)
    c.push()

    # Now add the second attachment using Component.submit_attachment().

    att_file = File(
        build_id=c.build_id,
        kind=FileKind.attachment,
        name=os.path.basename(att2),
        filename=os.path.basename(att2),
        internal=True,
        resource_path=str(att2),
    )
    c_dict: ComponentDict = c.submit_attachment("test", att_file)
    # Make sure this attachment has been added.
    comp: Component = Component.load(c_dict, store)
    assert len(comp.attachments) == 2

    attachment: File
    for attachment in comp.attachments.values():
        if attachment.name not in ("att1.txt", "att2.txt"):
            raise ValueError(f"Unknown attachment {attachment.name}")


def test_component_download(store):
    bid = BuildInfo.create(store=store, setup=DEFAULT_SETUP, version="1.0")
    c = Component(
        build_id=bid.id,
        name="comp",
        platform="x86_64-linux",
        version="1.0",
        files=[],
        store=store,
    )
    assert c.download(None) is None

    with open("f1.txt", "w") as f:
        f.write("XXXX")
    f1 = File(
        build_id=bid.id,
        kind=FileKind.binary,
        name="f1.txt",
        filename="f1.txt",
        build_info=bid,
        resource_path=os.path.abspath("f1.txt"),
        internal=False,
        store=store,
    )
    c.files.append(f1)
    cwd = os.getcwd()
    assert c.download(cwd) is True
    f1_downloaded = os.path.join("f1.txt")
    assert os.path.isfile(f1_downloaded)

    c.files[0].internal = True
    with open("f2.txt", "w") as f:
        f.write("AAAAA")
    f2 = File(
        build_id=bid.id,
        kind=FileKind.binary,
        name="f2.txt",
        filename="f2.txt",
        build_info=bid,
        resource_path=os.path.abspath("f2.txt"),
        internal=False,
        store=store,
    )
    c.files.append(f2)
    assert c.download(cwd) is True
    f2_downloaded = os.path.join("f2.txt")
    assert os.path.isfile(f2_downloaded)

    c.files.append(f2)
    with pytest.raises(
        StoreError, match="cannot download: multiple external files found"
    ):
        c.download(cwd)


def test_component_meta_file() -> None:
    """Check component meta file APIs."""
    c, att_1, att_2 = create_component_with_attachments()
    cwd: Path = Path.cwd()

    with pytest.raises(StoreError, match="non existing metafile"):
        Component.load_from_meta_file(str(cwd), c.name, ignore_errors=False)
    assert Component.load_from_meta_file(str(cwd), c.name, ignore_errors=True) is None

    # Save to meta file. Use the old API with a name provided.
    c.save_to_meta_file(str(cwd), c.name)
    metadata_file: Path = Path(c.metadata_path(str(cwd), c.name))
    assert metadata_file.exists() is True

    tmp = Component.load_from_meta_file(str(cwd), c.name)
    assert tmp == c

    with metadata_file.open("r+") as f:
        data = json.load(f)
        del data["build_id"]
        f.write(json.dumps(data, indent=2))
    with pytest.raises(StoreError, match="error while loading component metadata file"):
        Component.load_from_meta_file(str(cwd), c.name, ignore_errors=False)
    assert Component.load_from_meta_file(str(cwd), c.name, ignore_errors=True) is None

    # Remove the file before the next test.
    metadata_file.unlink()
    assert metadata_file.exists() is False

    # Save to meta file. Use the new API with a default name.
    c.save_to_meta_file(str(cwd))
    assert metadata_file.exists() is True

    # Try with a provided name.
    c.save_to_meta_file(str(cwd), "my_component")
    metadata_file = Path(c.metadata_path(str(cwd), "my_component"))
    assert metadata_file.exists() is True


def test_component_latest(store) -> None:
    buildinfo = store.create_build_id("test", "20241029", "1.0")
    store.mark_build_ready(buildinfo["_id"])

    # First create a component
    bid = BuildInfo.latest(store=store, setup="test")
    with open("test1.txt", "w") as fd:
        fd.write("1")

    binary = File(
        build_id=bid.id,
        kind=FileKind.binary,
        name="test1.txt",
        filename="test1.txt",
        build_info=bid,
        resource_path=os.path.abspath("test1.txt"),
    )

    c = Component(
        build_id=bid.id,
        build_info=bid,
        name="comp1",
        specname="comp1spec",
        platform="x86_64-linux",
        version="1.0",
        files=[binary],
        store=store,
    )
    c.push()

    def assert_right_comp(comp: Component) -> None:
        assert comp.name == "comp1"
        assert comp.specname == "comp1spec"
        assert comp.version == "1.0"
        assert comp.platform == "x86_64-linux"
        assert comp.build_info.build_date == "20241029"

    tmp = Component.latest(store, "test", date="20241029")
    assert len(tmp) == 1
    assert_right_comp(tmp[0])

    tmp = Component.latest(store, "test", date="00000000")
    assert not tmp

    tmp = Component.latest(store, "test", component="comp1")
    assert len(tmp) == 1
    assert_right_comp(tmp[0])

    tmp = Component.latest(store, "test", component="notfound")
    assert not tmp

    tmp = Component.latest(store, "test", specname="comp1spec")
    assert len(tmp) == 1
    assert_right_comp(tmp[0])

    tmp = Component.latest(store, "test", specname="notfound")
    assert not tmp

    tmp = Component.latest(store, "test", build_id=bid.id)
    assert len(tmp) == 1
    assert_right_comp(tmp[0])

    tmp = Component.latest(store, "test", build_id="notfound")
    assert not tmp
