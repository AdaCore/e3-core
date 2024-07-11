from e3.spdx import (
    Document,
    EntityRef,
    ExternalRef,
    ExternalRefCategory,
    FilesAnalyzed,
    Creator,
    Organization,
    Tool,
    Package,
    PackageComment,
    PackageCopyrightText,
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
    SHA1,
    SHA256,
    SPDXID,
    SPDXEntryStr,
    SPDXEntryMaybeStrMultilines,
    NOASSERTION,
    Relationship,
    RelationshipType,
    InvalidSPDX,
)

import pytest


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
                "downloadLocation": "NOASSERTION",
                "packageFileName": "main-pkg.zip",
                "licenseConcluded": "GPL-3.0-or-later",
                "licenseDeclared": "GPL-3.0-or-later",
                "name": "my-spdx-test-main",
                "originator": "Organization: AdaCore",
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
