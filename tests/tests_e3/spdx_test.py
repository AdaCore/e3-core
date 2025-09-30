from __future__ import annotations

import json

import pytest

from e3.spdx import (
    NONE_VALUE,
    Created,
    Document,
    Entity,
    EntityRef,
    ExternalRef,
    ExternalRefCategory,
    FilesAnalyzed,
    Creator,
    Organization,
    Tool,
    Package,
    PackageChecksum,
    PackageComment,
    PackageCopyrightText,
    PackageDescription,
    PackageDownloadLocation,
    PackageFileName,
    PackageLicenseComments,
    PackageLicenseConcluded,
    PackageLicenseDeclared,
    PackageName,
    PackageOriginator,
    PackageSupplier,
    PackageVersion,
    Person,
    PrimaryPackagePurpose,
    SHA1,
    SHA256,
    SHA512,
    SPDXID,
    SPDXEntryStr,
    SPDXEntryMaybeStrMultilines,
    NOASSERTION,
    Relationship,
    RelationshipType,
    InvalidSPDX,
    PackageHomePage,
    CreationInformation,
)


def create_spdx() -> Document:
    doc = Document(
        document_name="my-spdx-test",
        creators=[
            Organization("AdaCore"),
            Tool("e3-core"),
            Person("e3-core maintainer"),
        ],
    )
    package: Package = Package(
        name=PackageName("my-spdx-test-main"),
        version=PackageVersion("2.2.2"),
        spdx_id=SPDXID("my-spdx-test-main-2.2.2"),
        file_name=PackageFileName("main-pkg.zip"),
        checksum=[
            SHA1("6476df3aac780622368173fe6e768a2edc3932c8"),
            SHA256(
                "91751cee0a1ab8414400238a761411daa29643ab4b8243e9a91649e25be53ada",
            ),
        ],
        license_concluded=PackageLicenseConcluded("GPL-3.0-or-later"),
        license_declared=PackageLicenseDeclared("GPL-3.0-or-later"),
        license_comments=None,
        supplier=PackageSupplier(Organization("AdaCore")),
        originator=PackageOriginator(Organization("AdaCore")),
        download_location=PackageDownloadLocation(NOASSERTION),
        files_analyzed=FilesAnalyzed(False),
        copyright_text=PackageCopyrightText("2023 AdaCore"),
        external_refs=None,
        homepage=None,
        primary_purpose=PrimaryPackagePurpose.ARCHIVE,
        description=PackageDescription(
            "My SPDX test main package\nmade of several\nlines."
        ),
    )

    doc.add_package(package, is_main_package=True)

    package = Package(
        name=PackageName("my-dep"),
        version=PackageVersion("1b2"),
        spdx_id=SPDXID("my-dep-1b2"),
        file_name=PackageFileName("my-dep-1b2.tgz"),
        checksum=[
            SHA1("6876df3aa8780622368173fe6e868a2edc3932c8"),
        ],
        license_concluded=PackageLicenseConcluded("GPL-3.0-or-later"),
        license_declared=None,
        license_comments=PackageLicenseComments("Pretty sure this is GPL v3"),
        supplier=PackageSupplier(Organization("AdaCore")),
        originator=PackageOriginator(Organization("AdaCore")),
        download_location=PackageDownloadLocation(NOASSERTION),
        files_analyzed=FilesAnalyzed(False),
        copyright_text=PackageCopyrightText("2023 AdaCore"),
        external_refs=[
            ExternalRef(
                reference_category=ExternalRefCategory.package_manager,
                reference_type="purl",
                reference_locator="pkg:generic/my-dep@1b2",
            )
        ],
        homepage=None,
        comment=PackageComment("A very useful comment on that package !"),
    )

    doc.add_package(package)

    package = Package(
        name=PackageName("my-dep2"),
        version=PackageVersion("1c3"),
        spdx_id=SPDXID("my-dep2-1c3"),
        file_name=PackageFileName("my-dep2-1c3.tgz"),
        checksum=[
            SHA1("6176df3aa1710633361173fe6e161a3edd3933d1"),
        ],
        license_concluded=PackageLicenseConcluded("GPL-3.0-or-later"),
        license_declared=None,
        license_comments=None,
        supplier=PackageSupplier(Organization("AdaCore")),
        originator=PackageOriginator(Organization("AdaCore")),
        download_location=PackageDownloadLocation(NOASSERTION),
        files_analyzed=FilesAnalyzed(False),
        copyright_text=PackageCopyrightText("2023 AdaCore"),
        external_refs=None,
        homepage=None,
    )

    pkg_id = doc.add_package(package, add_relationship=False)

    doc.add_relationship(
        relationship=Relationship(
            spdx_element_id=pkg_id,
            relationship_type=RelationshipType.BUILD_DEPENDENCY_OF,
            related_spdx_element=doc.main_package_spdx_id,
        )
    )

    return doc


def test_entities_ref_spdx():
    org = Organization("AdaCore")
    assert org.to_tagvalue() == "Organization: AdaCore"
    assert "AdaCore" in str(org)
    assert "NOASSERTION" in str(Organization(NOASSERTION))
    assert Organization(NOASSERTION).to_json_dict() == {"organization": "NOASSERTION"}

    assert Creator(org).to_tagvalue() == "Creator: Organization: AdaCore"

    assert (
        PackageSupplier(org).to_tagvalue() == "PackageSupplier: Organization: AdaCore"
    )
    assert (
        PackageOriginator(NOASSERTION).to_tagvalue() == "PackageOriginator: NOASSERTION"
    )


def test_entity_ref() -> None:
    """Tests for the EntityRef class which are not covered by the other tests."""
    org: EntityRef = EntityRef(Organization("AdaCore"))
    no_assertion: EntityRef = EntityRef(NOASSERTION)

    assert org.to_tagvalue() == "EntityRef: Organization: AdaCore"
    assert no_assertion.to_tagvalue() == "EntityRef: NOASSERTION"
    assert str(no_assertion) == "NOASSERTION"
    assert str(org) == "Organization: AdaCore"
    assert no_assertion.to_json_dict() == {"entityRef": "NOASSERTION"}
    assert org.to_json_dict() == {"entityRef": "Organization: AdaCore"}


def test_external_ref():
    value = {
        "referenceType": "purl",
        "referenceLocator": "pkg:pypi/wheel@0.36.2",
        "referenceCategory": "PACKAGE-MANAGER",
    }
    assert (
        ExternalRef.from_dict(value).to_tagvalue()
        == "ExternalRef: PACKAGE-MANAGER purl pkg:pypi/wheel@0.36.2"
    )
    assert ExternalRef.from_dict(value).to_json_dict() == {
        "externalRefs": {
            "referenceCategory": "PACKAGE-MANAGER",
            "referenceLocator": "pkg:pypi/wheel@0.36.2",
            "referenceType": "purl",
        }
    }


def test_spdx():
    """Test a SPDX document creation."""
    doc = create_spdx()

    tagvalue_content = doc.to_tagvalue()
    json_content = doc.to_json_dict()

    # Change fields that are not stable: DocumentNamespace containing a UUID
    # and Created timestamp
    document_namespace = "my-spdx-test-c5c1e261-fb57-474a-b3c3-dc2adf3a4e06"
    created = "2023-02-10T14:54:01Z"

    for idx, field in enumerate(tagvalue_content):
        if field.startswith("DocumentNamespace: my-spdx-test-"):
            tagvalue_content[idx] = f"DocumentNamespace: {document_namespace}"
        if field.startswith("Created: "):
            tagvalue_content[idx] = f"Created: {created}"

    # Perform the same changes for the JSON content
    json_content["documentNamespace"] = document_namespace
    json_content["creationInfo"]["created"] = created

    assert tagvalue_content == [
        "# Document Information",
        "",
        "DocumentName: my-spdx-test",
        f"DocumentNamespace: {document_namespace}",
        "SPDXVersion: SPDX-2.3",
        "DataLicense: CC0-1.0",
        "SPDXID: SPDXRef-DOCUMENT",
        "",
        "",
        "# Creation Info",
        "",
        "Creator: Organization: AdaCore",
        "Creator: Tool: e3-core",
        "Creator: Person: e3-core maintainer",
        f"Created: {created}",
        "LicenseListVersion: 3.19",
        "",
        "",
        "# Relationships",
        "",
        "Relationship: SPDXRef-DOCUMENT DESCRIBES SPDXRef-my-spdx-test-main-2.2.2-pkg",
        "Relationship: SPDXRef-my-spdx-test-main-2.2.2-pkg CONTAINS SPDXRef-my-dep-1b2",
        "Relationship: SPDXRef-my-dep2-1c3 BUILD_DEPENDENCY_OF "
        "SPDXRef-my-spdx-test-main-2.2.2-pkg",
        "",
        "",
        "# Package",
        "",
        "PackageName: my-spdx-test-main",
        "SPDXID: SPDXRef-my-spdx-test-main-2.2.2-pkg",
        "PackageVersion: 2.2.2",
        "PackageFileName: main-pkg.zip",
        "PackageChecksum: SHA1: 6476df3aac780622368173fe6e768a2edc3932c8",
        "PackageChecksum: SHA256: "
        "91751cee0a1ab8414400238a761411daa29643ab4b8243e9a91649e25be53ada",
        "PackageSupplier: Organization: AdaCore",
        "PackageOriginator: Organization: AdaCore",
        "PackageCopyrightText: <text>2023 AdaCore</text>",
        "FilesAnalyzed: false",
        "PackageLicenseConcluded: GPL-3.0-or-later",
        "PackageLicenseDeclared: GPL-3.0-or-later",
        "PackageDownloadLocation: NOASSERTION",
        "PrimaryPackagePurpose: ARCHIVE",
        "PackageDescription: <text>My SPDX test main package\n"
        "made of several\n"
        "lines.</text>",
        "",
        "",
        "# Package",
        "",
        "PackageName: my-dep",
        "SPDXID: SPDXRef-my-dep-1b2",
        "PackageVersion: 1b2",
        "PackageFileName: my-dep-1b2.tgz",
        "PackageChecksum: SHA1: 6876df3aa8780622368173fe6e868a2edc3932c8",
        "PackageSupplier: Organization: AdaCore",
        "PackageOriginator: Organization: AdaCore",
        "PackageCopyrightText: <text>2023 AdaCore</text>",
        "FilesAnalyzed: false",
        "PackageLicenseConcluded: GPL-3.0-or-later",
        "PackageLicenseComments: <text>Pretty sure this is GPL v3</text>",
        "PackageDownloadLocation: NOASSERTION",
        "ExternalRef: PACKAGE-MANAGER purl pkg:generic/my-dep@1b2",
        "PackageComment: <text>A very useful comment on that package !</text>",
        "",
        "",
        "# Package",
        "",
        "PackageName: my-dep2",
        "SPDXID: SPDXRef-my-dep2-1c3",
        "PackageVersion: 1c3",
        "PackageFileName: my-dep2-1c3.tgz",
        "PackageChecksum: SHA1: 6176df3aa1710633361173fe6e161a3edd3933d1",
        "PackageSupplier: Organization: AdaCore",
        "PackageOriginator: Organization: AdaCore",
        "PackageCopyrightText: <text>2023 AdaCore</text>",
        "FilesAnalyzed: false",
        "PackageLicenseConcluded: GPL-3.0-or-later",
        "PackageDownloadLocation: NOASSERTION",
        "",
        "",
    ]

    assert json_content == {
        "SPDXID": "SPDXRef-DOCUMENT",
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "documentNamespace": document_namespace,
        "documentDescribes": ["SPDXRef-my-spdx-test-main-2.2.2-pkg"],
        "name": "my-spdx-test",
        "creationInfo": {
            "licenseListVersion": "3.19",
            "created": created,
            "creators": [
                "Organization: AdaCore",
                "Tool: e3-core",
                "Person: e3-core maintainer",
            ],
        },
        "relationships": [
            {
                "spdxElementId": "SPDXRef-my-spdx-test-main-2.2.2-pkg",
                "relationshipType": "CONTAINS",
                "relatedSpdxElement": "SPDXRef-my-dep-1b2",
            },
            {
                "relatedSpdxElement": "SPDXRef-my-spdx-test-main-2.2.2-pkg",
                "relationshipType": "BUILD_DEPENDENCY_OF",
                "spdxElementId": "SPDXRef-my-dep2-1c3",
            },
        ],
        "packages": [
            {
                "SPDXID": "SPDXRef-my-spdx-test-main-2.2.2-pkg",
                "filesAnalyzed": False,
                "checksums": [
                    {
                        "algorithm": "SHA1",
                        "checksumValue": "6476df3aac780622368173fe6e768a2edc3932c8",
                    },
                    {
                        "algorithm": "SHA256",
                        "checksumValue": "91751cee0a1ab8414400238a761411daa"
                        "29643ab4b8243e9a91649e25be53ada",
                    },
                ],
                "copyrightText": "2023 AdaCore",
                "description": "My SPDX test main package\n"
                "made of several\n"
                "lines.",
                "downloadLocation": "NOASSERTION",
                "packageFileName": "main-pkg.zip",
                "licenseConcluded": "GPL-3.0-or-later",
                "licenseDeclared": "GPL-3.0-or-later",
                "name": "my-spdx-test-main",
                "originator": "Organization: AdaCore",
                "primaryPackagePurpose": "ARCHIVE",
                "supplier": "Organization: AdaCore",
                "versionInfo": "2.2.2",
            },
            {
                "SPDXID": "SPDXRef-my-dep-1b2",
                "filesAnalyzed": False,
                "checksums": [
                    {
                        "algorithm": "SHA1",
                        "checksumValue": "6876df3aa8780622368173fe6e868a2edc3932c8",
                    }
                ],
                "comment": "A very useful comment on that package !",
                "copyrightText": "2023 AdaCore",
                "downloadLocation": "NOASSERTION",
                "externalRefs": [
                    {
                        "referenceCategory": "PACKAGE-MANAGER",
                        "referenceLocator": "pkg:generic/my-dep@1b2",
                        "referenceType": "purl",
                    }
                ],
                "packageFileName": "my-dep-1b2.tgz",
                "licenseConcluded": "GPL-3.0-or-later",
                "licenseComments": "Pretty sure this is GPL v3",
                "name": "my-dep",
                "originator": "Organization: AdaCore",
                "supplier": "Organization: AdaCore",
                "versionInfo": "1b2",
            },
            {
                "SPDXID": "SPDXRef-my-dep2-1c3",
                "checksums": [
                    {
                        "algorithm": "SHA1",
                        "checksumValue": "6176df3aa1710633361173fe6e161a3edd3933d1",
                    }
                ],
                "copyrightText": "2023 AdaCore",
                "downloadLocation": "NOASSERTION",
                "filesAnalyzed": False,
                "licenseConcluded": "GPL-3.0-or-later",
                "name": "my-dep2",
                "originator": "Organization: AdaCore",
                "packageFileName": "my-dep2-1c3.tgz",
                "supplier": "Organization: AdaCore",
                "versionInfo": "1c3",
            },
        ],
    }


def test_invalid_spdx():
    """Test creating an invalid SPDX document."""
    doc = Document(
        document_name="my-spdx-test",
        creators=[
            Organization("AdaCore"),
            Tool("e3-core"),
            Person("e3-core maintainer"),
        ],
    )

    def add_main(is_main_package):
        package: Package = Package(
            name=PackageName("my-spdx-test-main"),
            version=PackageVersion("2.2.2"),
            spdx_id=SPDXID("my-spdx-test-main-2.2.2"),
            file_name=PackageFileName("main-pkg.zip"),
            checksum=[
                SHA1("6476df3aac780622368173fe6e768a2edc3932c8"),
                SHA256(
                    "91751cee0a1ab8414400238a761411daa29643ab4b8243e9a91649e25be53ada",
                ),
            ],
            license_concluded=PackageLicenseConcluded("GPL-3.0-or-later"),
            license_declared=PackageLicenseDeclared("GPL-3.0-or-later"),
            license_comments=None,
            supplier=PackageSupplier(Organization("AdaCore")),
            originator=PackageOriginator(Organization("AdaCore")),
            download_location=PackageDownloadLocation(NOASSERTION),
            files_analyzed=FilesAnalyzed(False),
            copyright_text=PackageCopyrightText("2023 AdaCore"),
            external_refs=None,
            homepage=None,
        )
        return doc.add_package(package, is_main_package=is_main_package)

    with pytest.raises(InvalidSPDX) as err:
        add_main(is_main_package=False)

    assert "missing a main package" in str(err)

    add_main(is_main_package=True)

    with pytest.raises(InvalidSPDX) as err:
        for idx in range(0, 2):
            if idx == 0:
                name = "my-dep"
            else:
                name = "my___-dep"
            dep: Package = Package(
                name=PackageName(name),
                version=PackageVersion("1b2"),
                spdx_id=SPDXID("my-dep-1b2"),
                file_name=PackageFileName("my-dep-1b2.tgz"),
                checksum=[
                    SHA1("6876df3aa8780622368173fe6e868a2edc3932c8"),
                ],
                license_concluded=PackageLicenseConcluded("GPL-3.0-or-later"),
                license_declared=None,
                license_comments=None,
                supplier=PackageSupplier(Organization("AdaCore")),
                originator=PackageOriginator(Organization("AdaCore")),
                download_location=PackageDownloadLocation(NOASSERTION),
                files_analyzed=FilesAnalyzed(False),
                copyright_text=PackageCopyrightText("2023 AdaCore"),
                external_refs=None,
                homepage=None,
            )
            doc.add_package(dep)
    assert (
        "A package with the same SPDXID SPDXRef-my-dep-1b2 has already been added"
        in str(err)
    )


def test_spdx_entry_maybe_str_multilines() -> None:
    """SPDXEntryMaybeStrMultilines class tests.

    Tests for the SPDXEntryMaybeStrMultilines class which are not covered by
    the other tests.
    """
    ml: SPDXEntryMaybeStrMultilines = SPDXEntryMaybeStrMultilines("value")
    no_assertion: SPDXEntryMaybeStrMultilines = SPDXEntryMaybeStrMultilines(NOASSERTION)

    assert ml.to_tagvalue() == "SPDXEntryMaybeStrMultilines: <text>value</text>"
    assert no_assertion.to_tagvalue() == "SPDXEntryMaybeStrMultilines: NOASSERTION"


def test_spdx_entry_str_gt() -> None:
    """Check SPDXEntryStr class's __gt__() method."""
    e1 = SPDXEntryStr("One")
    e2 = SPDXEntryStr("Two")

    assert e2 > e1
    # Check the branch where two different objects are compared.
    assert e2.__gt__("One") is False


def test_spdx_from_json_dict() -> None:
    doc = create_spdx()
    doc2: Document = Document.from_json_dict(doc.to_json_dict())
    spdx = doc.to_json_dict()
    spdx2 = doc2.to_json_dict()
    assert json.dumps(spdx, indent=2, sort_keys=True) == json.dumps(
        spdx2, indent=2, sort_keys=True
    )


def test_creator() -> None:
    creator: Creator | None = Creator(Organization("AdaCore"))
    creator_dict: dict = creator.to_json_dict()
    creator2: Creator = Creator.from_json_dict(creator_dict)
    creator_dict2 = creator2.to_json_dict()
    assert json.dumps(creator_dict, indent=2, sort_keys=True) == json.dumps(
        creator_dict2, indent=2, sort_keys=True
    )
    creator = Creator.from_json_dict({Creator.get_json_entry_key(): "Person: me"})
    assert creator.value.value == "me"
    assert isinstance(creator, Creator)
    assert isinstance(creator.value, Person)
    creator = Creator.from_json_dict({"xxx": "Person: me"})
    assert creator is None
    creator = Creator.from_json_dict(
        {Creator.get_json_entry_key(): "Organization: AdaCore"}
    )
    assert creator.value.value == "AdaCore"
    assert isinstance(creator, Creator)
    assert isinstance(creator.value, Organization)
    creator = Creator.from_json_dict({Creator.get_json_entry_key(): "Tool: e3"})
    assert creator.value.value == "e3"
    assert isinstance(creator, Creator)
    assert isinstance(creator.value, Tool)
    creator = Creator.from_json_dict(
        {Creator.get_json_entry_key(): "Anything: anything"}
    )
    assert creator is None


def test_entity() -> None:
    entity: Entity | None = Entity.from_json_dict({"entity": "Person: me"})
    assert entity.value == "me"
    assert isinstance(entity, Person)
    entity = Entity.from_json_dict({"xxx": "Person: me"})
    assert entity is None
    entity = Entity.from_json_dict({"entity": "Organization: AdaCore"})
    assert entity.value == "AdaCore"
    assert isinstance(entity, Organization)
    entity = Entity.from_json_dict({"entity": "Tool: e3"})
    assert entity.value == "e3"
    assert isinstance(entity, Tool)
    entity = Entity.from_json_dict({"entity": "Anything: anything"})
    assert entity is None


def test_misc_from_json_dict() -> None:
    created: Created = Created.from_json_dict(
        {Created.get_json_entry_key(): "2025-09-26"}
    )
    assert isinstance(created, Created)
    # Test the default assignment
    created = Created.from_json_dict({"invalid": "2025-09-26"})
    assert isinstance(created, Created)
    supplier: PackageSupplier | None = PackageSupplier.from_json_dict({})
    assert supplier is None
    originator: PackageOriginator | None = PackageOriginator.from_json_dict({})
    assert originator is None
    analyzed: FilesAnalyzed | None = FilesAnalyzed.from_json_dict({})
    assert analyzed.value is False
    cksum: PackageChecksum = PackageChecksum.from_json_dict(
        {"algorithm": SHA512.algorithm, "checksumValue": "not checked"}
    )
    assert cksum.value == "not checked"
    with pytest.raises(ValueError, match="Invalid input checksum dict"):
        PackageChecksum.from_json_dict({})
    with pytest.raises(ValueError, match="Unsupported checksum algorithm"):
        PackageChecksum.from_json_dict(
            ({"algorithm": "invalid", "checksumValue": "not checked"})
        )
    homepage: PackageHomePage | None = PackageHomePage.from_json_dict(
        {PackageHomePage.get_json_entry_key(): "homepage"}
    )
    assert homepage.value == "homepage"
    assert PackageHomePage.from_json_dict({"not homepage": "not a homepage"}) is None
    license_concluded: PackageLicenseConcluded = PackageLicenseConcluded.from_json_dict(
        {"not license": "not a license"}
    )
    assert license_concluded.value == NONE_VALUE
    license_concluded: PackageLicenseConcluded = PackageLicenseConcluded.from_json_dict(
        {PackageLicenseConcluded.get_json_entry_key(): None}
    )
    assert license_concluded.value == NONE_VALUE
    copyright_text: PackageCopyrightText | None = PackageCopyrightText.from_json_dict(
        {PackageCopyrightText.get_json_entry_key(): None}
    )
    assert copyright_text is None
    rela_type: RelationshipType = RelationshipType.from_json_dict(
        {RelationshipType.get_json_entry_key(): RelationshipType.DATA_FILE_OF.name}
    )
    assert rela_type.value == RelationshipType.DATA_FILE_OF.value
    # Some tests for to_tagvalue() and to_json_dict()
    assert rela_type.to_tagvalue() == "RelationshipType: DATA_FILE_OF"
    assert rela_type.to_json_dict() == {
        RelationshipType.get_json_entry_key(): RelationshipType.DATA_FILE_OF.name
    }
    rela_type = RelationshipType.from_json_dict(
        {"anything": RelationshipType.DATA_FILE_OF.name}
    )
    assert rela_type == RelationshipType.OTHER
    creation_info: CreationInformation = CreationInformation.from_json_dict(
        {"an invalid": "dict"}
    )
    assert isinstance(creation_info, CreationInformation)


def test_spdx_without_main_package() -> None:
    doc_dict: dict = {
        "SPDXID": "SPDXRef-DOCUMENT",
        "creationInfo": {
            "created": "2025-09-24T09:54:19.745Z",
            "creators": ["Tool: npm/cli-11.4.2"],
        },
        "dataLicense": "CC0-1.0",
        "documentNamespace": (
            "http://spdx.org/spdxdocs/ada-26.0.202508111-f5857bbc-8122-4a8c-a90e-4349d65c0a11"
        ),
        "name": "ada@26.0.202508111",
        "packages": [
            {
                "SPDXID": "SPDXRef-Package-ada-26.0.202508111",
                "description": (
                    "Ada & SPARK IntelliSense, code browsing, debugging and more."
                ),
                "downloadLocation": "NOASSERTION",
                "externalRefs": [
                    {
                        "referenceCategory": "PACKAGE-MANAGER",
                        "referenceLocator": "pkg:npm/ada@26.0.202508111",
                        "referenceType": "purl",
                    }
                ],
                "filesAnalyzed": False,
                "homepage": "https://github.com/AdaCore/ada_language_server#readme",
                "licenseDeclared": "GPL-3.0",
                "name": "ada",
                "packageFileName": "",
                "primaryPackagePurpose": "LIBRARY",
                "versionInfo": "26.0.202508111",
            },
            {
                "SPDXID": "SPDXRef-Package-colors.colors-1.6.0",
                "checksums": [
                    {
                        "algorithm": "SHA512",
                        "checksumValue": (
                            "22bf803a26eaceb22c2fa6a3b77473dcbb2407b3a23151ea96"
                            "d666b296d6fd326e4d5bb238c8ab56a0248df63a2484a22c78"
                            "3236a89c002f00c871c6ccd77f74"
                        ),
                    }
                ],
                "description": "get colors in your node.js console",
                "downloadLocation": "NOASSERTION",
                "externalRefs": [
                    {
                        "referenceCategory": "PACKAGE-MANAGER",
                        "referenceLocator": "pkg:npm/%40colors/colors@1.6.0",
                        "referenceType": "purl",
                    }
                ],
                "filesAnalyzed": False,
                "homepage": "https://github.com/DABH/colors.js",
                "licenseDeclared": "MIT",
                "name": "@colors/colors",
                "packageFileName": "node_modules/@colors/colors",
                "versionInfo": "1.6.0",
            },
        ],
    }
    doc: Document = Document.from_json_dict(doc_dict)
    assert "documentDescribes" in doc.to_json_dict()
