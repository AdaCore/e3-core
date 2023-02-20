from e3.spdx import (
    Document,
    Creator,
    Organization,
    Tool,
    PackageOriginator,
    PackageSupplier,
    Person,
    SHA1,
    SHA256,
    NOASSERTION,
    Relationship,
    RelationshipType,
    InvalidSPDX,
)

import pytest


def test_entities_ref_spdx():
    org = Organization("AdaCore")
    assert org.to_tagvalue() == "Organization: AdaCore"

    assert Creator(org).to_tagvalue() == "Creator: Organization: AdaCore"

    assert (
        PackageSupplier(org).to_tagvalue() == "PackageSupplier: Organization: AdaCore"
    )
    assert (
        PackageOriginator(NOASSERTION).to_tagvalue() == "PackageOriginator: NOASSERTION"
    )


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

    doc.add_package(
        name="my-spdx-test-main-pkg",
        version="2.2.2",
        file_name="main-pkg.zip",
        checksum=[
            SHA1("6476df3aac780622368173fe6e768a2edc3932c8"),
            SHA256(
                "91751cee0a1ab8414400238a761411daa29643ab4b8243e9a91649e25be53ada",
            ),
        ],
        license_concluded="GPL-3.0-or-later",
        license_declared="GPL-3.0-or-later",
        supplier=Organization("AdaCore"),
        originator=Organization("AdaCore"),
        download_location=NOASSERTION,
        files_analyzed=False,
        copyright_text="2023 AdaCore",
        is_main_package=True,
    )

    doc.add_package(
        name="my-dep",
        version="1b2",
        file_name="my-dep-1b2.tgz",
        checksum=[
            SHA1("6876df3aa8780622368173fe6e868a2edc3932c8"),
        ],
        license_concluded="GPL-3.0-or-later",
        supplier=Organization("AdaCore"),
        originator=Organization("AdaCore"),
        download_location=NOASSERTION,
        files_analyzed=False,
        copyright_text="2023 AdaCore",
    )
    pkg_id = doc.add_package(
        name="my-dep2",
        version="1c3",
        file_name="my-dep2-1c3.tgz",
        checksum=[
            SHA1("6176df3aa1710633361173fe6e161a3edd3933d1"),
        ],
        license_concluded="GPL-3.0-or-later",
        supplier=Organization("AdaCore"),
        originator=Organization("AdaCore"),
        download_location=NOASSERTION,
        files_analyzed=False,
        copyright_text="2023 AdaCore",
        add_relationship=False,
    )

    doc.add_relationship(
        relationship=Relationship(
            spdx_element_id=pkg_id,
            relationship_type=RelationshipType.BUILD_DEPENDENCY_OF,
            related_spdx_element=doc.main_package_spdx_id,
        )
    )

    tagvalue_content = doc.to_tagvalue()
    json_content = doc.to_json_dict()

    # Change fields that are not stable: DocumentNamespace containing an UUID
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
        "SPDXVersion: SPDX-1.2",
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
        "Relationship: SPDXRef-DOCUMENT DESCRIBES SPDXRef-my-spdx-test-main-pkg-2.2.2",
        "Relationship: SPDXRef-my-spdx-test-main-pkg-2.2.2 CONTAINS SPDXRef-my-dep-1b2",
        "Relationship: SPDXRef-my-dep2-1c3 BUILD_DEPENDENCY_OF "
        "SPDXRef-my-spdx-test-main-pkg-2.2.2",
        "",
        "",
        "# Package",
        "",
        "PackageName: my-spdx-test-main-pkg",
        "SPDXID: SPDXRef-my-spdx-test-main-pkg-2.2.2",
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
        "PackageDownloadLocation: NOASSERTION",
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
    ]

    assert json_content == {
        "SPDXID": "SPDXRef-DOCUMENT",
        "spdxVersion": "SPDX-1.2",
        "dataLicense": "CC0-1.0",
        "documentNamespace": document_namespace,
        "documentDescribes": ["SPDXRef-my-spdx-test-main-pkg-2.2.2"],
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
                "spdxElementId": "SPDXRef-my-spdx-test-main-pkg-2.2.2",
                "relationshipType": "CONTAINS",
                "relatedSpdxElement": "SPDXRef-my-dep-1b2",
            },
            {
                "relatedSpdxElement": "SPDXRef-my-spdx-test-main-pkg-2.2.2",
                "relationshipType": "BUILD_DEPENDENCY_OF",
                "spdxElementId": "SPDXRef-my-dep2-1c3",
            },
        ],
        "packages": [
            {
                "SPDXID": "SPDXRef-my-spdx-test-main-pkg-2.2.2",
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
                "name": "my-spdx-test-main-pkg",
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
                "copyrightText": "2023 AdaCore",
                "downloadLocation": "NOASSERTION",
                "packageFileName": "my-dep-1b2.tgz",
                "licenseConcluded": "GPL-3.0-or-later",
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
        return doc.add_package(
            name="my-spdx-test-main-pkg",
            version="2.2.2",
            file_name="main-pkg.zip",
            checksum=[
                SHA1("6476df3aac780622368173fe6e768a2edc3932c8"),
                SHA256(
                    "91751cee0a1ab8414400238a761411daa29643ab4b8243e9a91649e25be53ada",
                ),
            ],
            license_concluded="GPL-3.0-or-later",
            supplier=Organization("AdaCore"),
            originator=Organization("AdaCore"),
            download_location=NOASSERTION,
            files_analyzed=False,
            copyright_text="2023 AdaCore",
            is_main_package=is_main_package,
        )

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
            doc.add_package(
                name=name,
                version="1b2",
                file_name="my-dep-1b2.tgz",
                checksum=[
                    SHA1("6876df3aa8780622368173fe6e868a2edc3932c8"),
                ],
                license_concluded="GPL-3.0-or-later",
                supplier=Organization("AdaCore"),
                originator=Organization("AdaCore"),
                download_location=NOASSERTION,
                files_analyzed=False,
                copyright_text="2023 AdaCore",
            )
    assert (
        "A package with the same SPDXID SPDXRef-my-dep-1b2 has already been added"
        in str(err)
    )
