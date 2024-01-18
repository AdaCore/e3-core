"""SLSA provenance packages tests."""

from __future__ import annotations

import hashlib
import json
import pytest

from datetime import datetime, timezone
from dateutil import parser as date_parser
from pathlib import Path
from time import sleep
from typing import Any

from e3.slsa.provenance import (
    Builder,
    BuildMetadata,
    Predicate,
    ResourceDescriptor,
    ResourceURI,
    Statement,
    TypeURI,
)

# Taken out of https://slsa.dev/spec/v1.0/provenance#builddefinition
EXTERNAL_PARAMETERS: dict = {
    "repository": "https://github.com/octocat/hello-world",
    "ref": "refs/heads/main",
}
INTERNAL_PARAMETERS: dict = {"internal": "parameters"}

# The following algorithms have been tested with:
#
# find . -type f | cut -c3- | LC_ALL=C sort | xargs -r sha256sum \\
#                       | sha256sum | cut -f1 -d' '

# noinspection SpellCheckingInspection
VALID_DIGESTS: dict[str, str] = {
    "blake2b": (
        "0a2293c1133aa5b2bdc84a0c8793db9cc60e8af7bb41acb661dc9c7264d35c8a0"
        "4071840a253c4834470e8e87e46655f22a4c7e923f263c44d75734945d509eb"
    ),
    "md5": "9a2477e53e7a865232aa8c266effdcc6",
    "sha1": "2719edd7f69c5769d1a5169d2edfbbe95bca1daa",
    "sha224": "5813c0c8f5772b9ff36e17b12d10847f3c8f78e892c6dbaf5a7052e8",
    "sha256": "98e967576c9f7401ddf9659fe7fcd8a23bd172ac4206fadec7506fcd1daa3f75",
    "sha384": (
        "7be552e5b91d8815e4238cd59ad5d713b34d3150fa03c61d180504c440d4c6cd5"
        "29245edee34ec40c5406d447f5553b1"
    ),
    "sha512": (
        "96afe1503defb47772f70cf830cc77b4836e9bad16c8cb2576149a5ffb5a9ec73"
        "a5842951889b2c81405291f931a5f639dbd4e8326c3cba87fc07bfe6f2711f5"
    ),
}

VALID_URIS: list[str] = [
    "scheme://netloc/path;parameters?query#fragment",
    "http://docs.python.org:80/3/library/urllib.parse.html?highlight=params#url-parsing",
    "https://www.adacore.com/company",
]


def create_valid_build_definition() -> tuple:
    """Create a valid build definition object."""
    build_type: TypeURI = TypeURI(VALID_URIS[0])
    rd: ResourceDescriptor = create_valid_resource_descriptor()[-1]
    resolved_dependencies: list[ResourceDescriptor] = [rd]

    bd = Predicate.BuildDefinition(
        build_type=build_type,
        external_parameters=EXTERNAL_PARAMETERS,
        internal_parameters=INTERNAL_PARAMETERS,
        resolved_dependencies=resolved_dependencies,
    )
    return build_type, rd, resolved_dependencies, bd


def create_valid_build_metadata() -> tuple[datetime, str, datetime, BuildMetadata]:
    """Create a valid BuildMetadata object."""
    start_time = datetime.now(timezone.utc)
    invocation_id = "invocation id"
    finish_time = datetime.now(timezone.utc)
    bm = BuildMetadata(
        invocation_id=invocation_id, started_on=start_time, finished_on=finish_time
    )
    return start_time, invocation_id, finish_time, bm


def create_valid_builder() -> (
    tuple[TypeURI, list[ResourceDescriptor], dict[str, str], Builder]
):
    """Create a valid builder object.

    :return: A tuple made of:
      - The build ID (TypeURI)
      - The Builder dependencies (list of ResourceDescriptor)
      - The version (dict of str -> str)
      - The created valid Builder (Builder)
    """
    desc = create_valid_resource_descriptor()[-1]
    build_id: TypeURI = TypeURI(VALID_URIS[1])
    builder_dependencies: list[ResourceDescriptor] = [desc]
    version: dict[str, str] = {"version1": "value1"}
    builder: Builder = Builder(
        build_id=build_id,
        builder_dependencies=builder_dependencies,
        version=version,
    )
    return build_id, builder_dependencies, version, builder


def create_valid_resource_descriptor() -> tuple:
    """Create a valid resource descriptor."""
    # Create a new resource descriptor with all input parameters set.
    uri: str = VALID_URIS[0]
    digest: dict[str, str] = {"sha256": VALID_DIGESTS["sha256"]}
    rc_annotations: dict[str, Any] = {"one": 1, "two": "two"}
    name: str = "Resource descriptor"
    dl_loc: str = VALID_URIS[1]
    media_type: str = "Media Type"
    content = "12.34".encode("utf-8")

    desc: ResourceDescriptor = ResourceDescriptor(
        uri=uri,
        digest=digest,
        name=name,
        download_location=dl_loc,
        media_type=media_type,
        content=content,
        resource_annotations=rc_annotations,
    )

    return uri, digest, rc_annotations, name, dl_loc, media_type, content, desc


def create_valid_run_details() -> tuple:
    """Create a valid run details object."""
    builder: Builder = create_valid_builder()[-1]
    metadata: BuildMetadata = create_valid_build_metadata()[-1]
    desc: ResourceDescriptor = create_valid_resource_descriptor()[-1]
    by_products: list[ResourceDescriptor] = [desc]
    rd: Predicate.RunDetails = Predicate.RunDetails(
        builder=builder, metadata=metadata, by_products=by_products
    )
    return builder, metadata, by_products, rd


def test_build_definition_as_dict() -> None:
    """Test dict representation of build definition."""
    build_type, rd, resolved_dependencies, bd = create_valid_build_definition()
    # Check class attributes.
    dict_repr = bd.as_dict()
    assert dict_repr.get(Predicate.BuildDefinition.ATTR_BUILD_TYPE) == build_type
    assert (
        dict_repr.get(Predicate.BuildDefinition.ATTR_EXTERNAL_PARAMETERS)
        == EXTERNAL_PARAMETERS
    )
    assert (
        dict_repr.get(Predicate.BuildDefinition.ATTR_INTERNAL_PARAMETERS)
        == INTERNAL_PARAMETERS
    )
    assert (
        dict_repr.get(Predicate.BuildDefinition.ATTR_RESOLVED_DEPENDENCIES)[0]
        == rd.as_dict()
    )


def test_build_definition_as_json() -> None:
    """Test json representation of build definition."""
    bd: Predicate.BuildDefinition = create_valid_build_definition()[-1]
    json_repr: str = bd.as_json()
    assert json.loads(json_repr)


def test_build_definition_init() -> None:
    """Test initialization of build definition."""
    # Check class attributes.
    build_type, rd, resolved_dependencies, bd = create_valid_build_definition()
    assert bd.build_type == build_type
    assert bd.external_parameters == EXTERNAL_PARAMETERS
    assert bd.internal_parameters == INTERNAL_PARAMETERS
    assert bd.resolved_dependencies[0] == rd
    # Test the __eq__ method with a wrong type.
    assert bd != {}


def test_build_definition_load_dict() -> None:
    """Test loading the dict representation of a build definition."""
    bd: Predicate.BuildDefinition = create_valid_build_definition()[-1]
    dict_repr: dict = bd.as_dict()
    # Initialise a second build definition with that dict.
    bd2: Predicate.BuildDefinition = Predicate.BuildDefinition.load_dict(dict_repr)
    # Now check that all fields match.
    assert bd.build_type == bd2.build_type
    assert bd.external_parameters == bd2.external_parameters
    assert bd.internal_parameters == bd2.internal_parameters
    for resdep in bd.resolved_dependencies:
        assert resdep in bd2.resolved_dependencies


def test_build_definition_load_json() -> None:
    """Test loading the json representation of a build definition."""
    bd: Predicate.BuildDefinition = create_valid_build_definition()[-1]
    json_repr: str = bd.as_json()
    # Initialise a second build definition with that dict.
    bd2: Predicate.BuildDefinition = Predicate.BuildDefinition.load_json(json_repr)
    # Now check that all fields match.
    assert bd.build_type == bd2.build_type
    assert bd.external_parameters == bd2.external_parameters
    assert bd.internal_parameters == bd2.internal_parameters
    for resdep in bd.resolved_dependencies:
        assert resdep in bd2.resolved_dependencies


def test_builder_as_dict() -> None:
    (
        uri,
        digest,
        rc_annotations,
        name,
        dl_loc,
        media_type,
        content,
        desc,
    ) = create_valid_resource_descriptor()
    build_id: TypeURI = TypeURI(VALID_URIS[1])
    builder_dependencies: list[ResourceDescriptor] = [desc]
    version: dict[str, str] = {"version1": "value1"}
    builder: Builder = Builder(
        build_id=build_id,
        builder_dependencies=builder_dependencies,
        version=version,
    )
    # Make sure it is a valid JSON object.
    dict_repr: dict = builder.as_dict()
    dict_dep: dict = desc.as_dict()
    assert json.dumps(dict_repr, indent="  ") != ""
    assert dict_repr.get(Builder.ATTR_BUILD_ID) == build_id
    assert dict_repr.get(Builder.ATTR_BUILDER_DEPENDENCIES)[0] == dict_dep
    assert dict_repr.get(Builder.ATTR_VERSION) == version


def test_builder_as_json() -> None:
    builder: Builder = create_valid_builder()[-1]
    json_repr: str = builder.as_json()
    # Check that the JSON string is valid.
    assert json.loads(json_repr)


def test_builder_init() -> None:
    bid, deps, version, builder = create_valid_builder()
    assert builder.id == bid
    assert builder.builder_dependencies[0] == deps[0]
    assert builder.version == version
    # Try with a string for the build ID.
    builder = Builder(
        build_id=VALID_URIS[0],
        builder_dependencies=deps,
        version=version,
    )
    assert builder.id == TypeURI(VALID_URIS[0])
    assert builder.builder_dependencies[0] == deps[0]
    assert builder.version == version
    # Test the __eq__ method with a wrong type.
    assert builder != {}


def test_builder_load_dict() -> None:
    """Test loading the dict representation of a builder."""
    builder: Builder = create_valid_builder()[-1]
    dict_repr: dict = builder.as_dict()
    # Initialise a second build definition with that dict.
    builder2: Builder = Builder.load_dict(dict_repr)
    # Now check that all fields match.
    for builder_dep in builder.builder_dependencies:
        assert builder_dep in builder2.builder_dependencies
    assert builder.id == builder2.id
    assert builder.version == builder2.version
    # Check with an invalid builder (by setting the build ID to None).
    dict_repr.pop(Builder.ATTR_BUILD_ID)
    with pytest.raises(ValueError) as invalid_builder_id:
        Builder.load_dict(dict_repr)
    assert "Invalid build ID (None)" in invalid_builder_id.value.args[0]


def test_builder_load_json() -> None:
    """Test loading the JSON representation of a builder."""
    builder: Builder = create_valid_builder()[-1]
    json_repr: str = builder.as_json()
    # Initialise a second build definition with that JSON string.
    builder2: Builder = Builder.load_json(json_repr)
    # Now check that all fields match.
    for builder_dep in builder.builder_dependencies:
        assert builder_dep in builder2.builder_dependencies
    assert builder.id == builder2.id
    assert builder.version == builder2.version


def test_buildmetadata_as_dict() -> None:
    """Test the dict representation of a BuildMetadata."""
    start_time, invocation_id, finish_time, bm = create_valid_build_metadata()
    dict_repr = bm.as_dict()
    assert dict_repr.get(BuildMetadata.ATTR_INVOCATION_ID) == invocation_id
    assert dict_repr.get(BuildMetadata.ATTR_STARTED_ON) == start_time.strftime(
        BuildMetadata.TIMESTAMP_FORMAT
    )
    assert dict_repr.get(BuildMetadata.ATTR_FINISHED_ON) == finish_time.strftime(
        BuildMetadata.TIMESTAMP_FORMAT
    )


def test_buildmetadata_as_json() -> None:
    """Test the JSON representation of a BuildMetadata."""
    start_time, invocation_id, finish_time, bm = create_valid_build_metadata()
    json_repr: str = bm.as_json()
    # Check that the JSON string is valid.
    assert json.loads(json_repr)


def test_buildmetadata_init() -> None:
    """Test the BuildMetadata class initialization."""
    start_time, invocation_id, finish_time, bm = create_valid_build_metadata()
    assert bm.invocation_id == invocation_id
    assert bm.started_on == start_time.replace(microsecond=0)
    assert bm.finished_on == finish_time.replace(microsecond=0)
    # Test the __eq__ method with a wrong type.
    assert bm != {}
    # Initialize with an invalid timestamp type
    with pytest.raises(TypeError) as invalid_timestamp_type:
        # noinspection PyTypeChecker
        BuildMetadata(
            invocation_id=invocation_id, started_on=None, finished_on=finish_time
        )
    assert "Invalid timestamp type" in invalid_timestamp_type.value.args[0]


def test_buildmetadata_load_dict() -> None:
    """Test loading the dict representation of a build metadata."""
    bm: BuildMetadata = create_valid_build_metadata()[-1]
    dict_repr: dict = bm.as_dict()
    # Initialise a second build metadata with that dict.
    bm2: BuildMetadata = BuildMetadata.load_dict(dict_repr)
    # Now check that all fields match.
    assert bm.invocation_id == bm2.invocation_id
    assert bm.started_on == bm2.started_on
    assert bm.finished_on == bm2.finished_on
    # Check initialisation with an invalid invocation ID.
    dict_repr.pop(BuildMetadata.ATTR_INVOCATION_ID)
    with pytest.raises(ValueError) as invalid_init_id:
        BuildMetadata.load_dict(dict_repr)
    assert "Invalid invocation ID (None)" in invalid_init_id.value.args[0]


def test_buildmetadata_load_json() -> None:
    """Test loading the json representation of a build metadata."""
    bm: BuildMetadata = create_valid_build_metadata()[-1]
    json_repr: str = bm.as_json()
    # Initialise a second build metadata with that dict.
    bm2: BuildMetadata = BuildMetadata.load_json(json_repr)
    # Now check that all fields match.
    assert bm.invocation_id == bm2.invocation_id
    assert bm.started_on == bm2.started_on
    assert bm.finished_on == bm2.finished_on


def test_predicate_as_dict() -> None:
    """Test a predicate object dict format."""
    bd: Predicate.BuildDefinition = create_valid_build_definition()[-1]
    rd: Predicate.RunDetails = create_valid_run_details()[-1]
    predicate: Predicate = Predicate(build_definition=bd, run_details=rd)
    dict_repr: dict = predicate.as_dict()
    assert dict_repr.get(Predicate.ATTR_BUILD_DEFINITION) == bd.as_dict()
    assert dict_repr.get(Predicate.ATTR_RUN_DETAILS) == rd.as_dict()


def test_predicate_as_json() -> None:
    """Test a predicate object JSON format."""
    bd: Predicate.BuildDefinition = create_valid_build_definition()[-1]
    rd: Predicate.RunDetails = create_valid_run_details()[-1]
    predicate: Predicate = Predicate(build_definition=bd, run_details=rd)
    json_repr: str = predicate.as_json()
    # Check that the JSON string is valid.
    assert json.loads(json_repr)


def test_predicate_init() -> None:
    """Test a predicate object creation."""
    bd: Predicate.BuildDefinition = create_valid_build_definition()[-1]
    rd: Predicate.RunDetails = create_valid_run_details()[-1]
    predicate: Predicate = Predicate(build_definition=bd, run_details=rd)
    assert predicate.build_definition == bd
    assert predicate.run_details == rd
    # Test the __eq__ method with a wrong type.
    assert predicate != {}


def test_predicate_load_dict() -> None:
    """Test an initialization of a predicate object with dict data."""
    bd: Predicate.BuildDefinition = create_valid_build_definition()[-1]
    rd: Predicate.RunDetails = create_valid_run_details()[-1]
    predicate: Predicate = Predicate(build_definition=bd, run_details=rd)
    dict_repr: dict = predicate.as_dict()
    # Create a second predicate with that dict representation.
    predicate2: Predicate = Predicate.load_dict(dict_repr)
    # Check that all fields match.
    assert predicate.build_definition == predicate2.build_definition
    assert predicate.run_details == predicate2.run_details

    # Set an invalid build definition for the statement.
    build_def = dict_repr.pop(Predicate.ATTR_BUILD_DEFINITION)
    with pytest.raises(ValueError) as missing_build_def:
        Predicate.load_dict(dict_repr)
    assert "Missing build definition" in missing_build_def.value.args[0]

    # Set an invalid run details for the statement. Re-add the build definition
    # first.
    dict_repr[Predicate.ATTR_BUILD_DEFINITION] = build_def
    dict_repr.pop(Predicate.ATTR_RUN_DETAILS)
    with pytest.raises(ValueError) as missing_run_details:
        Predicate.load_dict(dict_repr)
    assert "Missing run details definition" in missing_run_details.value.args[0]


def test_predicate_load_json() -> None:
    """Test an initialization of a predicate object with JSON data."""
    bd: Predicate.BuildDefinition = create_valid_build_definition()[-1]
    rd: Predicate.RunDetails = create_valid_run_details()[-1]
    predicate: Predicate = Predicate(build_definition=bd, run_details=rd)
    # Make sure the issue https://github.com/AdaCore/e3-core/issues/668 is
    # fixed, add an (at least) one-second delay to make sure the timestamps are
    # really copied from predicate, and not regenerated.
    sleep(2.0)
    json_repr: str = predicate.as_json()
    # Create a second predicate with that dict representation.
    predicate2: Predicate = Predicate.load_json(json_repr)
    # Check that all fields match.
    assert predicate.build_definition == predicate2.build_definition
    assert predicate.run_details == predicate2.run_details


def test_resource_descriptor_add_digest() -> None:
    (
        uri,
        digest,
        rc_annotations,
        name,
        dl_loc,
        media_type,
        content,
        desc,
    ) = create_valid_resource_descriptor()
    assert desc.digest == digest
    # Add a new digest
    desc.add_digest("blake2b", VALID_DIGESTS["blake2b"])
    assert desc.digest.get("blake2b", "") == VALID_DIGESTS["blake2b"]
    # Try to add that digest again.
    with pytest.raises(KeyError) as already_added_error:
        desc.add_digest("blake2b", VALID_DIGESTS["blake2b"])
    assert (
        "Digest algorithm blake2b is already set to"
        in already_added_error.value.args[0]
    )


def test_resource_descriptor_annotations() -> None:
    """Test setting a resource descriptor annotations."""
    desc = ResourceDescriptor()
    # Set a valid annotation.
    desc.annotations = {"one": 1, "two": "two"}
    desc.annotations = {}
    # Try an invalid annotations.
    with pytest.raises(TypeError) as invalid_annotations:
        desc.annotations = "test"
    assert (
        "Invalid resource descriptor annotations" in invalid_annotations.value.args[0]
    )


def test_resource_descriptor_as_dict() -> None:
    """Test the content of the resource descriptor dictionary."""
    desc: ResourceDescriptor = create_valid_resource_descriptor()[-1]
    # Check that it is a valid json object.
    assert json.dumps(desc.as_dict())
    # Set one of the values to None, and retry.
    desc.media_type = None
    assert json.dumps(desc.as_dict())


def test_resource_descriptor_as_json() -> None:
    """Test the content of the resource descriptor JSON representation."""
    desc: ResourceDescriptor = create_valid_resource_descriptor()[-1]
    # Check that it is a valid json object.
    assert json.loads(desc.as_json())
    # Set one of the values to None, and retry.
    desc.media_type = None
    assert json.loads(desc.as_json())


def test_resource_descriptor_content() -> None:
    """Test setting a resource descriptor content."""
    desc = ResourceDescriptor()
    # Set a valid content.
    desc.content = "12.34".encode("utf-8")
    desc.content = None
    # Try an invalid content.
    with pytest.raises(TypeError) as invalid_content:
        desc.content = "test"
    assert "Invalid resource descriptor content" in invalid_content.value.args[0]


def test_resource_descriptor_digest() -> None:
    """Test setting a resource descriptor digest."""
    desc = ResourceDescriptor()
    # Set a valid digest.
    algo = "sha512"
    desc.digest = {algo: VALID_DIGESTS[algo]}
    desc.digest = {}
    # Try an invalid digest.
    with pytest.raises(TypeError) as invalid_digest:
        desc.digest = "test"
    assert "Invalid resource descriptor digest" in invalid_digest.value.args[0]


def test_resource_descriptor_dir_hash() -> None:
    # Create a simple tree and try all algorithms on that tree.
    # The awaited checksum is the same as::
    #
    # find . -type f | cut -c3- | LC_ALL=C sort | xargs -r sha256sum \\
    #                       | sha256sum | cut -f1 -d' '
    tree_dir: Path = Path(Path().cwd(), "tree")
    depth_dir: Path = Path(tree_dir, "depth")
    for d in tree_dir, depth_dir:
        d.mkdir(parents=True, exist_ok=True)
        filenames = ["file1.txt", "file2.txt"]
        for filename in filenames:
            fpath: Path = Path(d, filename)
            with fpath.open("wb") as f:
                f.write(f"{filename} file content\n".encode("utf-8"))

    # Check all algorithms.
    for algo in hashlib.algorithms_guaranteed:
        hashed: str = ResourceDescriptor.dir_hash(tree_dir, algo)
        if algo in VALID_DIGESTS:
            assert hashed == VALID_DIGESTS.get(algo), f" ({algo})"
        else:
            # No way to check the result yet, just
            ResourceDescriptor.dir_hash(tree_dir, algo)

    # Check with an invalid algorithm.

    with pytest.raises(ValueError) as invalid_algo:
        # noinspection PyTypeChecker
        ResourceDescriptor.dir_hash(tree_dir, "algo")
    assert "Unsupported digest algorithm" in invalid_algo.value.args[0]


def test_resource_descriptor_download_location() -> None:
    """Test setting a resource descriptor digest."""
    desc = ResourceDescriptor()
    # Set a valid download location.
    desc.download_location = VALID_URIS[0]
    desc.download_location = ResourceURI(VALID_URIS[0])
    desc.download_location = None
    # Try an invalid download location.
    with pytest.raises(TypeError) as invalid_loc:
        desc.download_location = 2
    assert "Invalid resource descriptor download location" in invalid_loc.value.args[0]


def test_resource_descriptor_init() -> None:
    """Test a resource descriptor initialization."""
    # Create an empty ResourceDescriptor.
    desc = ResourceDescriptor()
    assert desc.is_valid is False
    with pytest.raises(ValueError) as invalid_desc:
        # Getting the dict representation should fail.
        desc.as_dict()
    assert "Invalid resource descriptor" in invalid_desc.value.args[0]

    (
        uri,
        digest,
        rc_annotations,
        name,
        dl_loc,
        media_type,
        content,
        desc,
    ) = create_valid_resource_descriptor()

    assert desc.is_valid is True
    assert desc.uri == ResourceURI(uri)
    assert desc.digest == digest
    assert desc.name == name
    assert desc.download_location == ResourceURI(dl_loc)
    assert desc.media_type == media_type
    assert desc.content == content
    assert desc.annotations == rc_annotations

    # Test the __eq__ method with a wrong type.
    assert desc != {}

    # Check that a resource descriptor is valid with only one of uri, content
    # or digest.

    desc: ResourceDescriptor = ResourceDescriptor(
        uri=uri,
    )
    assert desc.is_valid is True

    desc: ResourceDescriptor = ResourceDescriptor(
        digest=digest,
    )
    assert desc.is_valid is True

    desc: ResourceDescriptor = ResourceDescriptor(
        content=content,
    )
    assert desc.is_valid is True


def test_resource_descriptor_load_dict() -> None:
    """Test the content of the resource descriptor dictionary."""
    desc: ResourceDescriptor = create_valid_resource_descriptor()[-1]
    # Create a second resource descriptor out of it.
    desc2: ResourceDescriptor = ResourceDescriptor.load_dict(desc.as_dict())

    # Check that all fields match.
    assert desc2.uri == desc.uri
    assert desc2.digest == desc.digest
    assert desc2.annotations == desc.annotations
    assert desc2.name == desc.name
    assert desc2.download_location == desc.download_location
    assert desc2.media_type == desc.media_type
    assert desc2.content == desc.content

    # Set one of the values to None, and retry.
    desc.media_type = None
    ResourceDescriptor.load_dict(desc.as_dict())
    # Check with an empty dict.
    with pytest.raises(ValueError) as invalid_dict:
        ResourceDescriptor.load_dict({})
    assert "Invalid resource descriptor" in invalid_dict.value.args[0]


def test_resource_descriptor_load_json() -> None:
    """Test the content of the resource descriptor JSON representation."""
    desc: ResourceDescriptor = create_valid_resource_descriptor()[-1]
    # Create a second resource descriptor out of it.
    desc2: ResourceDescriptor = ResourceDescriptor.load_json(desc.as_json())

    # Check that all fields match.
    assert desc2.uri == desc.uri
    assert desc2.digest == desc.digest
    assert desc2.annotations == desc.annotations
    assert desc2.name == desc.name
    assert desc2.download_location == desc.download_location
    assert desc2.media_type == desc.media_type
    assert desc2.content == desc.content

    # Set one of the values to None, and retry.
    desc.media_type = None
    ResourceDescriptor.load_json(desc.as_json())
    # Check with an empty dict.
    with pytest.raises(ValueError) as invalid_json:
        ResourceDescriptor.load_json(json.dumps({}))
    assert "Invalid resource descriptor" in invalid_json.value.args[0]


def test_resource_descriptor_media_type() -> None:
    """Test setting a resource descriptor mediaType."""
    desc = ResourceDescriptor()
    # Set a valid mediaType.
    desc.media_type = "media type"
    desc.media_type = None
    # Try an invalid mediaType.
    with pytest.raises(TypeError) as invalid_media_type:
        desc.media_type = 2
    assert "Invalid resource descriptor media type" in invalid_media_type.value.args[0]


def test_resource_descriptor_name() -> None:
    """Test setting a resource descriptor name."""
    desc = ResourceDescriptor()
    # Set a valid name.
    desc.name = "name"
    desc.name = None
    # Try an invalid name.
    with pytest.raises(TypeError) as invalid_name:
        desc.name = 2
    assert "Invalid resource descriptor name" in invalid_name.value.args[0]


def test_resource_descriptor_uri() -> None:
    """Test setting a resource descriptor uri."""
    desc = ResourceDescriptor()
    # Set a valid uri.
    desc.uri = VALID_URIS[0]
    desc.uri = ResourceURI(VALID_URIS[0])
    # Try an invalid uri.
    with pytest.raises(ValueError) as invalid_uri:
        desc.uri = "test"
    assert "Invalid URI" in invalid_uri.value.args[0]

    with pytest.raises(TypeError) as invalid_uri:
        desc.uri = 2
    assert "Invalid resource descriptor uri" in invalid_uri.value.args[0]


def test_resourceuri_init() -> None:
    """Tests for the ResourceURI constructor."""
    # First test on some valid URIs.
    for valid_uri in VALID_URIS:
        ResourceURI(valid_uri)

    # Make sure that invalid URIs raise a value error.
    invalid_uris: list = [
        "//www.cwi.nl:80/%7Eguido/Python.html",
        "www.cwi.nl/%7Eguido/Python.html",
        42,
        "anydata",
    ]
    for invalid_uri in invalid_uris:
        with pytest.raises(ValueError):
            ResourceURI(invalid_uri)


def test_resourceuri_str() -> None:
    """Tests for the ResourceURI string conversion."""
    # First test on some valid URIs.
    for valid_uri in VALID_URIS:
        resource_uri: ResourceURI = ResourceURI(valid_uri)
        assert str(resource_uri) == valid_uri


def test_resourceuri_uri() -> None:
    """Tests for the ResourceURI string conversion."""
    # First test on some valid URIs.
    for valid_uri in VALID_URIS:
        type_uri: ResourceURI = ResourceURI(valid_uri)
        assert type_uri.uri == valid_uri


def test_run_details_as_dict() -> None:
    """Test the dictionary representation of a predicate run details object."""
    builder, metadata, by_products, rd = create_valid_run_details()
    dict_repr: dict = rd.as_dict()
    assert dict_repr.get(Predicate.RunDetails.ATTR_BUILDER) == builder.as_dict()
    assert dict_repr.get(Predicate.RunDetails.ATTR_METADATA) == metadata.as_dict()
    assert dict_repr.get(Predicate.RunDetails.ATTR_BY_PRODUCTS) == [
        product.as_dict() for product in by_products
    ]


def test_run_details_as_json() -> None:
    """Test the JSON representation of a predicate run details object."""
    rd: Predicate.RunDetails = create_valid_run_details()[-1]
    # Make sure the JSOn representation is readable.
    assert json.loads(rd.as_json())


def test_run_details_init() -> None:
    """Test the initialization of a predicate run details object."""
    builder, metadata, by_products, rd = create_valid_run_details()
    assert rd.builder == builder
    assert rd.metadata == metadata
    assert rd.by_products == by_products
    # Test the __eq__ method with a wrong type.
    assert rd != {}


def test_run_details_load_dict() -> None:
    """Test the initialization of a predicate run details with dictionary."""
    rd: Predicate.RunDetails = create_valid_run_details()[-1]
    dict_repr: dict = rd.as_dict()
    rd2: Predicate.RunDetails = Predicate.RunDetails.load_dict(dict_repr)
    # Check that all fields match.
    assert rd.builder == rd2.builder
    assert rd.metadata == rd2.metadata
    assert rd.by_products == rd2.by_products

    # Set an invalid metadata for the run details.
    dict_repr.pop(Predicate.RunDetails.ATTR_METADATA)
    with pytest.raises(ValueError) as missing_metadata:
        Predicate.RunDetails.load_dict(dict_repr)
    assert "Missing metadata definition" in missing_metadata.value.args[0]

    # Set an invalid builder for the run details.
    dict_repr.pop(Predicate.RunDetails.ATTR_BUILDER)
    with pytest.raises(ValueError) as missing_builder:
        Predicate.RunDetails.load_dict(dict_repr)
    assert "Missing builder definition" in missing_builder.value.args[0]


def test_run_details_load_json() -> None:
    """Test the initialization of a predicate run details with dictionary."""
    rd: Predicate.RunDetails = create_valid_run_details()[-1]
    rd2: Predicate.RunDetails = Predicate.RunDetails.load_json(rd.as_json())
    # Check that all fields match.
    assert rd.builder == rd2.builder
    assert rd.metadata == rd2.metadata
    assert rd.by_products == rd2.by_products


def test_statement_as_dict() -> None:
    """Test a SLSA statement object as_dict() method."""
    statement_type: TypeURI = TypeURI(VALID_URIS[0])
    subject: list[ResourceDescriptor] = [create_valid_resource_descriptor()[-1]]
    predicate_type: TypeURI = TypeURI(Statement.PREDICATE_TYPE_VALUE)
    bd: Predicate.BuildDefinition = create_valid_build_definition()[-1]
    rd: Predicate.RunDetails = create_valid_run_details()[-1]
    predicate: Predicate = Predicate(build_definition=bd, run_details=rd)
    statement: Statement = Statement(
        statement_type=statement_type,
        subject=subject,
        predicate_type=predicate_type,
        predicate=predicate,
    )
    dict_repr: dict = statement.as_dict()
    assert dict_repr.get(Statement.ATTR_TYPE) == str(statement_type)
    assert dict_repr.get(Statement.ATTR_SUBJECT) == [s.as_dict() for s in subject]
    assert dict_repr.get(Statement.ATTR_PREDICATE_TYPE) == str(predicate_type)
    assert dict_repr.get(Statement.ATTR_PREDICATE) == predicate.as_dict()

    # Try with an empty predicate type.
    statement = Statement(
        statement_type=statement_type, subject=subject, predicate=predicate
    )
    dict_repr: dict = statement.as_dict()
    assert dict_repr.get(Statement.ATTR_TYPE) == str(statement_type)
    assert dict_repr.get(Statement.ATTR_SUBJECT) == [s.as_dict() for s in subject]
    assert (
        dict_repr.get(Statement.ATTR_PREDICATE_TYPE) == Statement.PREDICATE_TYPE_VALUE
    )
    assert dict_repr.get(Statement.ATTR_PREDICATE) == predicate.as_dict()

    # Try with an empty predicate.
    statement = Statement(
        statement_type=statement_type,
        subject=subject,
        predicate_type=predicate_type,
    )
    dict_repr: dict = statement.as_dict()
    assert dict_repr.get(Statement.ATTR_TYPE) == str(statement_type)
    assert dict_repr.get(Statement.ATTR_SUBJECT) == [s.as_dict() for s in subject]
    assert dict_repr.get(Statement.ATTR_PREDICATE_TYPE) == str(predicate_type)
    assert dict_repr.get(Statement.ATTR_PREDICATE) is None

    # Try with an empty predicate type and an empty predicate.
    statement = Statement(
        statement_type=statement_type,
        subject=subject,
    )
    dict_repr: dict = statement.as_dict()
    assert dict_repr.get(Statement.ATTR_TYPE) == str(statement_type)
    assert dict_repr.get(Statement.ATTR_SUBJECT) == [s.as_dict() for s in subject]
    assert (
        dict_repr.get(Statement.ATTR_PREDICATE_TYPE) == Statement.PREDICATE_TYPE_VALUE
    )
    assert dict_repr.get(Statement.ATTR_PREDICATE) is None


def test_statement_as_json() -> None:
    """Test a SLSA statement object as_json() method."""
    statement_type: TypeURI = TypeURI(VALID_URIS[0])
    subject: list[ResourceDescriptor] = [create_valid_resource_descriptor()[-1]]
    predicate_type: TypeURI = TypeURI(Statement.PREDICATE_TYPE_VALUE)
    bd: Predicate.BuildDefinition = create_valid_build_definition()[-1]
    rd: Predicate.RunDetails = create_valid_run_details()[-1]
    predicate: Predicate = Predicate(build_definition=bd, run_details=rd)
    statement: Statement = Statement(
        statement_type=statement_type,
        subject=subject,
        predicate_type=predicate_type,
        predicate=predicate,
    )
    # simply check that it is a valid JSON string.
    assert json.loads(statement.as_json())


def test_statement_init() -> None:
    """Test a SLSA statement object initialization."""
    statement_type: TypeURI = TypeURI(VALID_URIS[0])
    subject: list[ResourceDescriptor] = [create_valid_resource_descriptor()[-1]]
    predicate_type: TypeURI = TypeURI(Statement.PREDICATE_TYPE_VALUE)
    bd: Predicate.BuildDefinition = create_valid_build_definition()[-1]
    rd: Predicate.RunDetails = create_valid_run_details()[-1]
    predicate: Predicate = Predicate(build_definition=bd, run_details=rd)
    statement: Statement = Statement(
        statement_type=statement_type,
        subject=subject,
        predicate_type=predicate_type,
        predicate=predicate,
    )
    assert statement.type == statement_type
    assert statement.subject == subject
    assert statement.predicate_type == predicate_type
    assert statement.predicate == predicate

    # Test the __eq__ method with a wrong type.
    assert statement != {}

    # Try with an empty predicate type.
    statement = Statement(
        statement_type=statement_type, subject=subject, predicate=predicate
    )
    assert statement.type == statement_type
    assert statement.subject == subject
    assert statement.predicate_type == TypeURI(Statement.PREDICATE_TYPE_VALUE)
    assert statement.predicate == predicate

    # Try with an empty predicate.
    statement = Statement(
        statement_type=statement_type,
        subject=subject,
        predicate_type=predicate_type,
    )
    assert statement.type == statement_type
    assert statement.subject == subject
    assert statement.predicate_type == predicate_type
    assert statement.predicate is None

    # Try with an empty predicate type and an empty predicate.
    statement = Statement(
        statement_type=statement_type,
        subject=subject,
    )
    assert statement.type == statement_type
    assert statement.subject == subject
    assert statement.predicate_type == TypeURI(Statement.PREDICATE_TYPE_VALUE)
    assert statement.predicate is None


def test_statement_load_dict() -> None:
    """Test a SLSA statement object load_dict() method."""
    statement_type: TypeURI = TypeURI(VALID_URIS[0])
    subject: list[ResourceDescriptor] = [create_valid_resource_descriptor()[-1]]
    predicate_type: TypeURI = TypeURI(Statement.PREDICATE_TYPE_VALUE)
    bd: Predicate.BuildDefinition = create_valid_build_definition()[-1]
    rd: Predicate.RunDetails = create_valid_run_details()[-1]
    predicate: Predicate = Predicate(build_definition=bd, run_details=rd)
    statement: Statement = Statement(
        statement_type=statement_type,
        subject=subject,
        predicate_type=predicate_type,
        predicate=predicate,
    )
    dict_repr: dict = statement.as_dict()
    statement2: Statement = Statement.load_dict(dict_repr)
    # Now check that all fields match.
    assert statement.type == statement2.type
    for subject in statement.subject:
        assert subject in statement2.subject
    assert statement.predicate_type == statement2.predicate_type
    assert statement.predicate == statement2.predicate
    # Set an invalid type for a statement.
    dict_repr.pop(Statement.ATTR_TYPE)
    with pytest.raises(ValueError) as invalid_statement_type:
        Statement.load_dict(dict_repr)
    assert "Invalid statement type (None)" in invalid_statement_type.value.args[0]


def test_statement_load_file() -> None:
    """Check the statement can read the default file."""
    template_file: Path = Path(Path(__file__).parent, "provenance-example.json")
    with template_file.open() as f:
        Statement.load_dict(json.load(f))


def test_statement_recreate_file() -> None:
    template_file: Path = Path(Path(__file__).parent, "provenance-example.json")
    # Resource descriptors for the statement's subject.
    rd1: ResourceDescriptor = ResourceDescriptor(
        name="file1.txt",
        digest={"sha256": "123456789abcdef"},
    )
    rd2: ResourceDescriptor = ResourceDescriptor(
        name="file2.o",
        digest={"sha512": "123456789abcdeffedcba987654321"},
    )
    rd3: ResourceDescriptor = ResourceDescriptor(
        name="out.exe",
        digest={"md5": "123456789"},
    )
    # ----------------
    # Build definition
    # ResourceDescriptors for build definition's resolved dependencies
    bd_rd1: ResourceDescriptor = ResourceDescriptor(
        name="e3-core",
        uri="https://github.com/AdaCore/e3-core",
        media_type="git",
        resource_annotations={"branch": "master"},
        digest={"gitCommit": "f9c158d"},
    )
    bd_rd2: ResourceDescriptor = ResourceDescriptor(
        name="config",
        content=b"{'config': 'hello'}",
    )
    bd: Predicate.BuildDefinition = Predicate.BuildDefinition(
        build_type="https://www.myproduct.org/build",
        external_parameters=[{"option": "-xxx"}, {"out_format": "exe"}],
        internal_parameters=[{"env": {"MY_VAR": "my_value"}}],
        resolved_dependencies=[bd_rd1, bd_rd2],
    )
    # ----------------
    # ----------------
    # Run details builder
    version: str = "3.12.0"
    build_dep: ResourceDescriptor = ResourceDescriptor(
        name="Python",
        uri=f"https://www.python.org/ftp/python/{version}/Python-{version}.tgz",
        download_location=f"https://www.python.org/ftp/python/{version}/Python-{version}.tgz",
        media_type="application/gzip",
        digest={"md5": "d6eda3e1399cef5dfde7c4f319b0596c"},
        resource_annotations={"version": version},
    )
    builder: Builder = Builder(
        build_id="https://www.myproduct.org/build/647eda74f5cd7dc1cf55d12b",
        builder_dependencies=[
            build_dep,
        ],
        version={version: "2023/10/02"},
    )
    # Run details metadata.
    metadata: BuildMetadata = BuildMetadata(
        invocation_id="c47eda74f5cd7dc1cf55d12b",
        started_on=date_parser.parse("2023-10-02T13:39:53Z"),
        finished_on=date_parser.parse("2023-10-02T14:59:22Z"),
    )
    # Run details by product
    by_p1: ResourceDescriptor = ResourceDescriptor(
        name="My Product",
        uri="https://www.myproduct.org",
        digest={"md5": "d6eda3e1399caf5dfde7c4f319b0596c"},
        download_location="https://www.myproduct.org/download/my-product.tgz",
        media_type="application/gzip",
        resource_annotations={"version": "1.7.1"},
    )
    # Run details
    run_details: Predicate.RunDetails = Predicate.RunDetails(
        builder=builder,
        metadata=metadata,
        by_products=[
            by_p1,
        ],
    )
    # ----------------
    # ----------------
    # Predicate
    predicate: Predicate = Predicate(
        build_definition=bd,
        run_details=run_details,
    )
    # ----------------
    statement: Statement = Statement(
        statement_type="https://in-toto.io/Statement/v1",
        subject=[rd1, rd2, rd3],
        predicate_type="https://slsa.dev/provenance/v1",
        predicate=predicate,
    )
    file_content: str
    with template_file.open() as f:
        file_content = json.dumps(json.load(f), sort_keys=True)

    assert Statement.load_json(file_content) == statement


def test_statement_load_json() -> None:
    """Test a SLSA statement object load_json() method."""
    statement_type: TypeURI = TypeURI(VALID_URIS[0])
    subject: list[ResourceDescriptor] = [create_valid_resource_descriptor()[-1]]
    predicate_type: TypeURI = TypeURI(Statement.PREDICATE_TYPE_VALUE)
    bd: Predicate.BuildDefinition = create_valid_build_definition()[-1]
    rd: Predicate.RunDetails = create_valid_run_details()[-1]
    predicate: Predicate = Predicate(build_definition=bd, run_details=rd)
    statement: Statement = Statement(
        statement_type=statement_type,
        subject=subject,
        predicate_type=predicate_type,
        predicate=predicate,
    )
    statement2: Statement = Statement.load_json(statement.as_json())
    # Now check that all fields match.
    assert statement.type == statement2.type
    for subject in statement.subject:
        assert subject in statement2.subject
    assert statement.predicate_type == statement2.predicate_type
    assert statement.predicate == statement2.predicate


def test_typeuri_eq() -> None:
    """Tests for the TypeURI equal method."""
    # First test on some valid URIs.
    uri: ResourceURI = ResourceURI(VALID_URIS[0])
    assert ResourceURI(VALID_URIS[0]) == uri
    assert uri != 2


def test_typeuri_init() -> None:
    """Tests for the TypeURI constructor."""
    # First test on some valid URIs.
    for valid_uri in VALID_URIS:
        TypeURI(valid_uri)

    # Make sure that invalid URIs raise a value error.
    invalid_uris: list = [
        "//www.cwi.nl:80/%7Eguido/Python.html",
        "www.cwi.nl/%7Eguido/Python.html",
        42,
        "anydata",
    ]
    for invalid_uri in invalid_uris:
        with pytest.raises(ValueError):
            TypeURI(invalid_uri)


def test_typeuri_str() -> None:
    """Tests for the TypeURI string conversion."""
    for valid_uri in VALID_URIS:
        type_uri: TypeURI = TypeURI(valid_uri)
        assert str(type_uri) == valid_uri


def test_typeuri_uri() -> None:
    """Tests for the TypeURI string conversion."""
    # First test on some valid URIs.
    for valid_uri in VALID_URIS:
        type_uri: TypeURI = TypeURI(valid_uri)
        assert type_uri.uri == valid_uri
