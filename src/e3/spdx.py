"""Generate an SPDX file.

This is following the specification from https://spdx.github.io/spdx-spec/v2.3/
a simple example can be found at ./tests/tests_e3/spdx_test.py
"""

from __future__ import annotations

from enum import Enum, auto
from abc import ABCMeta, abstractmethod
from dataclasses import dataclass, field, fields
from datetime import datetime, timezone
from uuid import uuid4
import re

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from typing import Literal, Union, Any

NOASSERTION: Literal["NOASSERTION"] = "NOASSERTION"
"""Indicates that the preparer of the SPDX document is not making any assertion
regarding the value of this field.
"""
NONE_VALUE: Literal["NONE"] = "NONE"
"""When this value is used as the object of a property it indicates that the
preparer of the SpdxDocument believes that there is no value for the property.
This value should only be used if there is sufficient evidence to support this
assertion."""

if TYPE_CHECKING:
    MAYBE_STR = Union[str, Literal["NOASSERTION"], Literal["NONE"]]

SPDXID_R = re.compile("[^a-zA-Z0-9.-]")


class InvalidSPDX(Exception):
    """Raise an exception when the SPDX document cannot be generated."""

    pass


class SPDXPackageSupplier(Enum):
    """Used by the SPDX originator field.

    This field is composed of a package supplier type (organization, person, tool)
    and a name.

    This enum represents the package supplier type.
    """

    ORGANIZATION = "Organization"
    PERSON = "Person"
    TOOL = "Tool"


class SPDXEntry(metaclass=ABCMeta):
    """Describe an SPDX Entry."""

    @property
    def entry_key(self) -> str:
        """Name of the SPDXEntry as visible in the SPDX tag:value report."""
        return self.__class__.__name__

    @property
    def json_entry_key(self) -> str:
        """Name of the SPDXEntry as visible in the SPDX JSON report."""
        return self.entry_key[0].lower() + self.entry_key[1:]

    @abstractmethod
    def __str__(self) -> str:
        pass

    def __format__(self, format_spec: str) -> str:
        return self.__str__()

    def to_tagvalue(self) -> str:
        """Return a valid tag:value line."""
        return f"{self.entry_key}: {self}"

    @abstractmethod
    def to_json_dict(self) -> dict[str, Any]:
        """Return a chunk of the SPDX JSON document."""
        pass


class SPDXEntryStr(SPDXEntry):
    """Describe an SPDX Entry accepting a string."""

    def __init__(self, value: str) -> None:
        self.value = value

    def __str__(self) -> str:
        return self.value

    def __gt__(self, other: object) -> bool:
        if isinstance(other, self.__class__):
            return self.value > other.value
        return False

    def to_json_dict(self) -> dict[str, Any]:
        # Force calling __str__ method to simplify overloading
        # e.g. for SPDXID
        return {self.json_entry_key: str(self)}


class SPDXEntryMaybeStr(SPDXEntry):
    """Describe an SPDX Entry accepting a string, NOASSERTION, or NONE."""

    def __init__(self, value: MAYBE_STR) -> None:
        self.value = value

    def __str__(self) -> str:
        return self.value

    def to_json_dict(self) -> dict[str, Any]:
        return {self.json_entry_key: self.value}


class SPDXEntryMaybeStrMultilines(SPDXEntryMaybeStr):
    def to_tagvalue(self) -> str:
        """Return the content that can span to multiple lines.

        In tag:value format multiple lines are delimited by <text>...</text>.
        """
        if self.value in (NOASSERTION, NONE_VALUE):
            return f"{self.entry_key}: {self.value}"
        else:
            return f"{self.entry_key}: <text>{self}</text>"


class SPDXEntryBool(SPDXEntry):
    """Describe an SPDX Entry accepting a boolean."""

    def __init__(self, value: bool) -> None:
        self.value: bool = value

    def __str__(self) -> str:
        return "true" if self.value else "false"

    def to_json_dict(self) -> dict[str, Any]:
        return {self.json_entry_key: self.value}


@dataclass
class SPDXSection:
    """Describe an SPDX section."""

    def to_tagvalue(self) -> list[str]:
        """Generate a chunk of an SPDX tag:value document.

        Return a list of SPDX lines
        """
        output = []
        for fd in fields(self):
            section_field = self.__dict__[fd.name]
            if section_field is None:
                continue
            if isinstance(section_field, list):
                for extra_field in section_field:
                    output.append(extra_field.to_tagvalue())
            else:
                output.append(section_field.to_tagvalue())

        return output

    def to_json_dict(self) -> dict[str, Any]:
        result = {}
        for fd in fields(self):
            section_field = self.__dict__[fd.name]
            if section_field is None:
                continue
            if isinstance(section_field, list):
                for extra_field in section_field:
                    for field_key, field_value in extra_field.to_json_dict().items():
                        if field_key not in result:
                            result[field_key] = [field_value]
                        else:
                            result[field_key].append(field_value)
            else:
                result.update(section_field.to_json_dict())
        return result


class SPDXVersion(SPDXEntryStr):
    """Provide the SPDX version used to generate the document.

    See 6.1 `SPDX version field
    <https://spdx.github.io/spdx-spec/v2.3/document-creation-information/#61-spdx-version-field>`_.
    """

    json_entry_key = "spdxVersion"


class DataLicense(SPDXEntryStr):
    """License of the SPDX Metadata.

    See 6.2 `Data license field
    <https://spdx.github.io/spdx-spec/v2.3/document-creation-information/#62-data-license-field>`_.
    """


class SPDXID(SPDXEntryStr):
    """Identify an SPDX Document, or Package.

    See 6.3 `SPDX identifier field
    <https://spdx.github.io/spdx-spec/v2.3/document-creation-information/#63-spdx-identifier-field>`_
    and 7.2 `Package SPDX identifier field
    <https://spdx.github.io/spdx-spec/v2.3/package-information/#72-package-spdx-identifier-field>`_.

    The value is a unique string containing letters, numbers, ., and/or -.
    """

    json_entry_key = "SPDXID"

    def __init__(self, value: str) -> None:
        # The format of the SPDXID should be "SPDXRef-"[idstring]
        # where [idstring] is a unique string containing letters, numbers, .,
        # and/or -.
        super().__init__(re.sub(SPDXID_R, "", value))

    def __str__(self) -> str:
        return f"SPDXRef-{self.value}"

    def __eq__(self, o: object) -> bool:
        return isinstance(o, SPDXID) and o.value == self.value

    def __hash__(self) -> int:
        return hash(self.value)


class DocumentName(SPDXEntryStr):
    """Identify name of this document.

    See 6.4 `Document name field
    <https://spdx.github.io/spdx-spec/v2.3/document-creation-information/#64-document-name-field>`_.
    """

    json_entry_key = "name"


class DocumentNamespace(SPDXEntryStr):
    """Provide a unique URI for this document.

    See 6.5 `SPDX document namespace field
    <https://spdx.github.io/spdx-spec/v2.3/document-creation-information/#65-spdx-document-namespace-field>`_.
    """


class LicenseListVersion(SPDXEntryStr):
    """Provide the version of the SPDX License List used.

    See 6.7 `License list version field
    <https://spdx.github.io/spdx-spec/v2.3/document-creation-information/#67-license-list-version-field>`_.
    """


class Entity(SPDXEntryStr):
    """Represent an Entity (Organization, Person, Tool)."""


class EntityRef(SPDXEntry):
    """Reference an Entity.

    Accept NOASSERTION as a valid value.
    """

    def __init__(self, value: Entity | Literal["NOASSERTION"]) -> None:
        """Initialize an EntityRef.

        :param value: an Entity object or NOASSERTION
        """
        self.value = value

    def __str__(self) -> str:
        if self.value == NOASSERTION:
            return NOASSERTION
        else:
            return self.value.to_tagvalue()

    def to_tagvalue(self) -> str:
        if self.value == NOASSERTION:
            return f"{self.entry_key}: {self.value}"
        else:
            return f"{self.entry_key}: {self.value.to_tagvalue()}"

    def to_json_dict(self) -> dict[str, Any]:
        if self.value == NOASSERTION:
            return {self.json_entry_key: self.value}
        else:
            return {self.json_entry_key: self.value.to_tagvalue()}


class Creator(EntityRef):
    """Identify who (or what, in the case of a tool) created the SPDX document.

    See 6.8 `Creator field
    <https://spdx.github.io/spdx-spec/v2.3/document-creation-information/#68-creator-field>`_.
    """

    json_entry_key = "creators"


class Created(SPDXEntryStr):
    """Identify when the SPDX document was originally created.

    See 6.9 `Created field
    <https://spdx.github.io/spdx-spec/v2.3/document-creation-information/#69-created-field>`_.
    """


class Organization(Entity):
    """Identify an organization by its name."""


class Person(Entity):
    """Identify a person by its name."""


class Tool(Entity):
    """Identify a tool."""


class PackageName(SPDXEntryStr):
    """Identify the full name of the package.

    See 7.1 `Package name field
    <https://spdx.github.io/spdx-spec/v2.3/package-information/#71-package-name-field>`_
    """

    json_entry_key = "name"


class PackageVersion(SPDXEntryStr):
    """Identify the version of the package.

    See 7.3 `Package version field
    <https://spdx.github.io/spdx-spec/v2.3/package-information/#73-package-version-field>`_
    """

    json_entry_key = "versionInfo"


class PackageFileName(SPDXEntryStr):
    """Provide the actual file name of the package.

    See 7.4 `Package file name field
    <https://spdx.github.io/spdx-spec/v2.3/package-information/#74-package-file-name-field>`_
    """


class PackageSupplier(EntityRef):
    """Identify the actual distribution source for the package.

    See 7.5 `Package supplier field
    <https://spdx.github.io/spdx-spec/v2.3/package-information/#75-package-supplier-field>`_
    """

    json_entry_key = "supplier"


class PackageOriginator(EntityRef):
    """Identify from where the package originally came.

    See 7.6 `Package originator field
    <https://spdx.github.io/spdx-spec/v2.3/package-information/#76-package-originator-field>`_
    """

    json_entry_key = "originator"


class PackageDownloadLocation(SPDXEntryMaybeStr):
    """Identifies the download location of the package.

    See 7.7 `Package download location field
    <https://spdx.github.io/spdx-spec/v2.3/package-information/#77-package-download-location-field>`_
    """

    json_entry_key = "downloadLocation"


class FilesAnalyzed(SPDXEntryBool):
    """Indicates whether the file content of this package have been analyzed.

    See 7.8 `Files analyzed field
    <https://spdx.github.io/spdx-spec/v2.3/package-information/#78-files-analyzed-field>`_
    """


class PackageChecksum(SPDXEntryStr, metaclass=ABCMeta):
    """Provide a mechanism that permits unique identification of the package.

    See 7.10 `Package checksum field
    <https://spdx.github.io/spdx-spec/v2.3/package-information/#710-package-checksum-field>`_
    """

    entry_key = "PackageChecksum"
    json_entry_key = "checksums"

    @property
    @abstractmethod
    def algorithm(self) -> str:
        pass

    def __str__(self) -> str:
        return "{0}: {1}".format(self.algorithm, self.value)

    def to_json_dict(self) -> dict[str, dict[str, str]]:
        return {
            self.json_entry_key: {
                "algorithm": self.algorithm,
                "checksumValue": self.value,
            }
        }


class PackageHomePage(SPDXEntryMaybeStr):
    """Identifies the homepage location of the package.

    See 7.11 `Package home page field
    <https://spdx.github.io/spdx-spec/v2.3/package-information/#711-package-home-page-field>`_
    """

    json_entry_key = "homepage"


class SHA1(PackageChecksum):
    algorithm = "SHA1"


class SHA256(PackageChecksum):
    algorithm = "SHA256"


class PackageLicenseConcluded(SPDXEntryMaybeStr):
    """Contain the license concluded as governing the package.

    See 7.13 `Concluded license field
    <https://spdx.github.io/spdx-spec/v2.3/package-information/#713-concluded-license-field>`_
    """

    json_entry_key = "licenseConcluded"


class PackageLicenseDeclared(SPDXEntryMaybeStr):
    """Contain the license having been declared by the authors of the package.

    See 7.15 `Declared license field
    <https://spdx.github.io/spdx-spec/v2.3/package-information/#715-declared-license-field>`_
    """

    json_entry_key = "licenseDeclared"


class PackageLicenseComments(SPDXEntryMaybeStrMultilines):
    """Record background information or analysis for the Concluded License.

    See 7.16 `Comments on license field
    <https://spdx.github.io/spdx-spec/v2.3/package-information/#716-comments-on-license-field>`_
    """

    json_entry_key = "licenseComments"


class PackageCopyrightText(SPDXEntryMaybeStrMultilines):
    """Identify the copyright holders of the package.

    See 7.17 `Copyright text field
    <https://spdx.github.io/spdx-spec/v2.3/package-information/#717-copyright-text-field>`_
    """

    json_entry_key = "copyrightText"


class PackageComment(SPDXEntryMaybeStrMultilines):
    """Record background information or analysis for the Concluded License.

    See 7.20 `Package comment field
    <https://spdx.github.io/spdx-spec/v2.3/package-information/#720-package-comment-field>`_
    """

    json_entry_key = "comment"


class ExternalRefCategory(Enum):
    """Identify the category of an ExternalRef."""

    security = "SECURITY"
    package_manager = "PACKAGE-MANAGER"
    persistent_id = "PERSISTENT-ID"
    other = "OTHER"


# Create some constants to make writing easier
SECURITY = ExternalRefCategory.security
PACKAGE_MANAGER = ExternalRefCategory.package_manager
PERSISTENT_ID = ExternalRefCategory.persistent_id
OTHER = ExternalRefCategory.other

# List of valid external reference types when Category is not OTHER
SPDX_EXTERNAL_REF_TYPES = (
    (SECURITY, "cpe22Type"),
    (SECURITY, "cpe23Type"),
    (SECURITY, "advisory"),
    (SECURITY, "fix"),
    (SECURITY, "url"),
    (SECURITY, "swid"),
    (PACKAGE_MANAGER, "maven-central"),
    (PACKAGE_MANAGER, "npm"),
    (PACKAGE_MANAGER, "nuget"),
    (PACKAGE_MANAGER, "bower"),
    (PACKAGE_MANAGER, "purl"),
    (PERSISTENT_ID, "swh"),
    (PERSISTENT_ID, "gitoid"),
)


class ExternalRef(SPDXEntry):
    """Reference an external source of information relevant to the package.

    See 7.21 `External reference field
    <https://spdx.github.io/spdx-spec/v2.3/package-information/#721-external-reference-field>`_
    """

    json_entry_key = "externalRefs"

    def __init__(
        self,
        reference_category: ExternalRefCategory,
        reference_type: str,
        reference_locator: str,
    ) -> None:
        """Initialize an ExternalRef object.

        :param reference_category: the external reference category
        :param reference_type: one of the type listed in SPDX spec annex F
        :param reference_locator: unique string with no space
        """
        self.reference_category = reference_category
        self.reference_type = reference_type
        self.reference_locator = reference_locator

    def __str__(self) -> str:
        return " ".join(
            (self.reference_category.value, self.reference_type, self.reference_locator)
        )

    def to_json_dict(self) -> dict[str, dict[str, str]]:
        """Return a chunk of the SPDX JSON document."""
        return {
            self.json_entry_key: {
                "referenceCategory": self.reference_category.value,
                "referenceType": self.reference_type,
                "referenceLocator": self.reference_locator,
            }
        }

    @classmethod
    def from_dict(cls, external_ref_dict: dict[str, str]) -> ExternalRef:
        """Generate an External Ref from a dict compatible with the JSON format.

        :param external_ref_dict: a dict with the referenceCategory, referenceType,
            and referenceLocator keys
        :return: a new ExternalRef instance
        """
        return ExternalRef(
            reference_category=ExternalRefCategory(
                external_ref_dict["referenceCategory"]
            ),
            reference_type=external_ref_dict["referenceType"],
            reference_locator=external_ref_dict["referenceLocator"],
        )


class RelationshipType(Enum):
    """Describes the type of relationship between two SPDX elements."""

    #  Is to be used when SPDXRef-DOCUMENT describes SPDXRef-A
    DESCRIBES = auto()
    #  Is to be used when SPDXRef-A is described by SPDXREF-Document
    DESCRIBED_BY = auto()
    #  Is to be used when SPDXRef-A contains SPDXRef-B
    CONTAINS = auto()
    #  Is to be used when SPDXRef-A is contained by SPDXRef-B
    CONTAINED_BY = auto()
    #  Is to be used when SPDXRef-A depends on SPDXRef-B
    DEPENDS_ON = auto()
    #  Is to be used when SPDXRef-A is dependency of SPDXRef-B
    DEPENDENCY_OF = auto()
    #  Is to be used when SPDXRef-A is a manifest file that lists
    #  a set of dependencies for SPDXRef-B
    DEPENDENCY_MANIFEST_OF = auto()
    #  Is to be used when SPDXRef-A is a build dependency of SPDXRef-B
    BUILD_DEPENDENCY_OF = auto()
    #  Is to be used when SPDXRef-A is a development dependency of SPDXRef-B
    DEV_DEPENDENCY_OF = auto()
    #  Is to be used when SPDXRef-A is an optional dependency of SPDXRef-B
    OPTIONAL_DEPENDENCY_OF = auto()
    #  Is to be used when SPDXRef-A is to be a provided dependency of SPDXRef-B
    PROVIDED_DEPENDENCY_OF = auto()
    #  Is to be used when SPDXRef-A is a test dependency of SPDXRef-B
    TEST_DEPENDENCY_OF = auto()
    #  Is to be used when SPDXRef-A is a dependency required for the
    #  execution of SPDXRef-B
    RUNTIME_DEPENDENCY_OF = auto()
    #  Is to be used when SPDXRef-A is an example of SPDXRef-B
    EXAMPLE_OF = auto()
    #  Is to be used when SPDXRef-A generates SPDXRef-B
    GENERATES = auto()
    #  Is to be used when SPDXRef-A was generated from SPDXRef-B
    GENERATED_FROM = auto()
    #  Is to be used when SPDXRef-A is an ancestor
    #  (same lineage but pre-dates) SPDXRef-B
    ANCESTOR_OF = auto()
    #  Is to be used when SPDXRef-A is a descendant of
    #  (same lineage but postdates) SPDXRef-B
    DESCENDANT_OF = auto()
    #  Is to be used when SPDXRef-A is a variant of
    #  (same lineage but not clear which came first) SPDXRef-B
    VARIANT_OF = auto()
    #  Is to be used when distributing SPDXRef-A requires that SPDXRef-B
    #  also be distributed
    DISTRIBUTION_ARTIFACT = auto()
    #  Is to be used when SPDXRef-A is a patch file for
    #  (to be applied to) SPDXRef-B
    PATCH_FOR = auto()
    #  Is to be used when SPDXRef-A is a patch file that has been applied
    #  to SPDXRef-B
    PATCH_APPLIED = auto()
    #  Is to be used when SPDXRef-A is an exact copy of SPDXRef-B
    COPY_OF = auto()
    #  Is to be used when SPDXRef-A is a file that was added to SPDXRef-B
    FILE_ADDED = auto()
    #  Is to be used when SPDXRef-A is a file that was deleted from SPDXRef-B
    FILE_DELETED = auto()
    #  Is to be used when SPDXRef-A is a file that was modified from SPDXRef-B
    FILE_MODIFIED = auto()
    #  Is to be used when SPDXRef-A is expanded from the archive SPDXRef-B
    EXPANDED_FROM_ARCHIVE = auto()
    #  Is to be used when SPDXRef-A dynamically links to SPDXRef-B
    DYNAMIC_LINK = auto()
    #  Is to be used when SPDXRef-A statically links to SPDXRef-B
    STATIC_LINK = auto()
    #  Is to be used when SPDXRef-A is a data file used in SPDXRef-B
    DATA_FILE_OF = auto()
    #  Is to be used when SPDXRef-A is a test case used in testing SPDXRef-B
    TEST_CASE_OF = auto()
    #  Is to be used when SPDXRef-A is used to build SPDXRef-B
    BUILD_TOOL_OF = auto()
    #  Is to be used when SPDXRef-A is used as a development tool for SPDXRef-B
    DEV_TOOL_OF = auto()
    #  Is to be used when SPDXRef-A is used for testing SPDXRef-B
    TEST_OF = auto()
    #  Is to be used when SPDXRef-A is used as a test tool for SPDXRef-B
    TEST_TOOL_OF = auto()
    #  Is to be used when SPDXRef-A provides documentation of SPDXRef-B
    DOCUMENTATION_OF = auto()
    #  Is to be used when SPDXRef-A is an optional component of SPDXRef-B
    OPTIONAL_COMPONENT_OF = auto()
    #  Is to be used when SPDXRef-A is a metafile of SPDXRef-B
    METAFILE_OF = auto()
    #  Is to be used when SPDXRef-A is used as a package as part of SPDXRef-B
    PACKAGE_OF = auto()
    #  Is to be used when (current) SPDXRef-DOCUMENT amends the SPDX
    #  information in SPDXRef-B
    AMENDS = auto()
    #  Is to be used when SPDXRef-A is a prerequisite for SPDXRef-B
    PREREQUISITE_FOR = auto()
    #  Is to be used when SPDXRef-A has as a prerequisite SPDXRef-B
    HAS_PREREQUISITE = auto()
    #  Is to be used when SPDXRef-A describes, illustrates, or specifies
    #  a requirement statement for SPDXRef-B
    REQUIREMENT_DESCRIPTION_FOR = auto()
    #  Is to be used when SPDXRef-A describes, illustrates, or defines a
    #  design specification for SPDXRef-B
    SPECIFICATION_FOR = auto()
    #  Is to be used for a relationship which has not been defined
    #  in the formal SPDX specification
    OTHER = auto()


class Relationship(SPDXEntry):
    """Provides information about the relationship between two SPDX elements.

    See 11.1 `Relationship field
    <https://spdx.github.io/spdx-spec/v2.3/relationships-between-SPDX-elements/#111-relationship-field>`_.
    """

    def __init__(
        self,
        spdx_element_id: SPDXID,
        relationship_type: RelationshipType,
        related_spdx_element: SPDXID,
    ) -> None:
        """Initialize a Relationship object.

        :param spdx_element_id: the left side of the relationship, should be the
            SPDXID of an element
        :param relationship_type: the type of the relationship
        :param related_spdx_element: the right side of the relationship, should
            be the SPDXID of an element
        """
        self.spdx_element_id = spdx_element_id
        self.relationship_type = relationship_type
        self.related_spdx_element = related_spdx_element

    def __str__(self) -> str:
        return (
            f"{self.spdx_element_id} {self.relationship_type.name}"
            f" {self.related_spdx_element}"
        )

    def to_json_dict(self) -> dict[str, str]:
        return {
            "spdxElementId": str(self.spdx_element_id),
            "relationshipType": self.relationship_type.name,
            "relatedSpdxElement": str(self.related_spdx_element),
        }


@dataclass
class Package(SPDXSection):
    """Describe a package.

    If the SPDX information describes a package, the following fields shall be
    included per package. See `7 Package information section
    <https://spdx.github.io/spdx-spec/v2.3/package-information/>`_

    :ivar PackageName name: A mandatory single line of text identifying the full
        name of the package as given by the Package Originator
        (:class:`PackageOriginator`).
    :ivar SPDXID spdx_id: Uniquely identify any element in an SPDX document
        which may be referenced by other elements. These may be referenced
        internally and externally with the addition of the SPDX document
        identifier. Generally made of ``f"{name}-{version}"``.
    :ivar PackageVersion version: Identify the version of the package.
    :ivar PackageFileName file_name: Provide the actual file name of the
        package, or path of the directory being treated as a package. This may
        include the packaging and compression methods used as part of the file
        name, if appropriate.
    :ivar list[PackageChecksum] checksum: Provide an independently reproducible
        mechanism that permits unique identification of a specific package that
        correlates to the data in this SPDX document. This identifier enables a
        recipient to determine if any file in the original package has been
        changed. If the SPDX document is to be included in a package, this value
        should not be calculated. The SHA1 algorithm shall be used to provide
        the checksum by default. The only supported checksum algorithms (for
        now) are :class:`SHA1` and :class:`SHA256`.
    :ivar PackageSupplier supplier: Identify the actual distribution source for
        the package/directory identified in the SPDX document. This might or
        might not be different from the originating distribution source for the
        package. The name of the Package Supplier shall be an organization or
        recognized author and not a website. For example, SourceForge is a host
        website, not a supplier, the supplier for
        https://sourceforge.net/projects/bridge/ is *The Linux Foundation*.
    :ivar PackageOriginator originator: If the package identified in the SPDX
        document originated from a different person or organization than
        identified as Package Supplier (see *supplier* above), this field
        identifies from where or whom the package originally came. In some
        cases, a package may be created and originally distributed by a
        different third party than the Package Supplier of the package. For
        example, the SPDX document identifies the package as ``glibc`` and the
        Package Supplier as *Red Hat*, but the *Free Software Foundation* is the
        Package Originator.
    :ivar PackageCopyrightText copyright_text: Identify the copyright holders of
        the package, as well as any dates present. This will be a free form text
        field extracted from package information files.
    :ivar FilesAnalyzed files_analyzed: Indicates whether the file content of
        this package has been available for or subjected to analysis when
        creating the SPDX document. If false, indicates packages that represent
        metadata or URI references to a project, product, artifact, distribution
        or a component. If ``False``, the package shall not contain any files.
    :ivar PackageLicenseConcluded license_concluded: Contain the license the
        SPDX document creator has concluded as governing the package or
        alternative values, if the governing license cannot be determined.
    :ivar PackageLicenseComments | None license_comments: This field provides a
        place for the SPDX document creator to record any relevant background
        information or analysis that went in to arriving at the Concluded
        License for a package. If the Concluded License does not match the
        Declared License or License Information from Files, this should be
        explained by the SPDX document creator. It is also preferable to include
        an explanation here when the Concluded License is :attr:`NOASSERTION`.
    :ivar PackageLicenseDeclared license_declared: List the licenses that have
        been declared by the authors of the package. Any license information
        that does not originate from the package authors, e.g. license
        information from a third-party repository, should not be included in
        this field.
    :ivar PackageHomePage | None homepage: Provide a place for the SPDX document
        creator to record a website that serves as the package's home page. This
        link can also be used to reference further information about the package
        referenced by the SPDX document creator.
    :ivar PackageDownloadLocation download_location: This section identifies the
        download Uniform Resource Locator (URL), or a specific location within a
        version control system (VCS) for the package at the time that the SPDX
        document was created.
    :ivar list[ExternalRef] | None external_refs: An External Reference allows a
        Package to reference an external source of additional information,
        metadata, enumerations, asset identifiers, or downloadable content
        believed to be relevant to the Package. For instance:

        .. code-block:: python

                ExternalRef(
                    reference_category=ExternalRefCategory.package_manager,
                    reference_type="purl",
                    reference_locator="pkg:generic/my-dep@1b2"
                )
    :ivar PackageComment | None comment: This field provides a place for the
        SPDX document creator to record any general comments about the package
        being described.
    """  # noqa RST304

    name: PackageName
    spdx_id: SPDXID
    version: PackageVersion
    file_name: PackageFileName
    checksum: list[PackageChecksum]
    supplier: PackageSupplier
    originator: PackageOriginator
    copyright_text: PackageCopyrightText
    files_analyzed: FilesAnalyzed
    license_concluded: PackageLicenseConcluded
    license_comments: PackageLicenseComments | None
    license_declared: PackageLicenseDeclared | None
    homepage: PackageHomePage | None
    download_location: PackageDownloadLocation
    external_refs: list[ExternalRef] | None
    comment: PackageComment | None = field(default=None)


@dataclass
class DocumentInformation(SPDXSection):
    """Describe the SPDX Document."""

    document_name: DocumentName
    document_namespace: DocumentNamespace = field(init=False)
    version: SPDXVersion = SPDXVersion("SPDX-2.3")
    data_license: DataLicense = DataLicense("CC0-1.0")
    spdx_id: SPDXID = SPDXID("DOCUMENT")

    def __post_init__(self) -> None:
        self.document_namespace = DocumentNamespace(f"{self.document_name}-{uuid4()}")


@dataclass
class CreationInformation(SPDXSection):
    """Document where and by whom the SPDX document has been created."""

    creators: list[Creator]
    created_now: Created = field(init=False)
    license_list_version: LicenseListVersion = LicenseListVersion("3.19")

    def __post_init__(self) -> None:
        self.created_now = Created(
            datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        )


class Document:
    """Describe the SPDX Document."""

    def __init__(
        self,
        document_name: str,
        creators: list[Entity],
    ) -> None:
        """Initialize the SPDX Document.

        :param document_name: The name of this document.
        :param creators: A list of Entity objects, considered as the creators
            of this document.
        """
        self.doc_info = DocumentInformation(document_name=DocumentName(document_name))
        self.creation_info = CreationInformation(
            creators=[Creator(c) for c in creators]
        )
        self.packages: dict[SPDXID, Package] = {}
        self.relationships: list[Relationship] = []
        self.main_package_spdx_id: SPDXID | None = None

    @property
    def spdx_id(self) -> SPDXID:
        """Return the Document SPDXID."""
        return self.doc_info.spdx_id

    def add_package(
        self,
        package: Package,
        is_main_package: bool = False,
        add_relationship: bool = True,
    ) -> SPDXID:
        """Add a new Package and describe its relationship to other elements.

        :param package: An already created :class:`Package` to be added to this
            SPDX document
        :param is_main_package: whether the package is the main package, in
            which case a relationship will automatically be added to record
            that the document DESCRIBES this package. If false, it is assumed
            that the package is contained by the main package unless a
            relationship is explicitely passed
        :param add_relationship: whether to automatically add a relationship
            element - either (DOCUMENT DESCRIBES <main package>) if is_main_package
            is True or (<main package> CONTAINS <package>)

        :return: the package SPDX_ID
        """  # noqa RST304
        if is_main_package and not package.spdx_id.value.endswith("-pkg"):
            # This is the main package, given that is often occurs that
            # a main package depends on a source package of the same name
            # appends a "-pkg" suffix
            package.spdx_id = SPDXID(f"{package.spdx_id.value}-pkg")

        if package.spdx_id in self.packages:
            raise InvalidSPDX(
                f"A package with the same SPDXID {package.spdx_id}"
                " has already been added"
            )
        if is_main_package:
            self.main_package_spdx_id = package.spdx_id

        if add_relationship:
            if is_main_package:
                relationship = Relationship(
                    spdx_element_id=self.spdx_id,
                    relationship_type=RelationshipType.DESCRIBES,
                    related_spdx_element=package.spdx_id,
                )
            else:
                if self.main_package_spdx_id is None:
                    raise InvalidSPDX("missing a main package")
                relationship = Relationship(
                    spdx_element_id=self.main_package_spdx_id,
                    relationship_type=RelationshipType.CONTAINS,
                    related_spdx_element=package.spdx_id,
                )

            self.relationships.append(relationship)
        self.packages[package.spdx_id] = package
        return package.spdx_id

    def add_relationship(self, relationship: Relationship) -> None:
        """Add a new relationship to the document.

        :param relationship: the Relationship to add
        """
        self.relationships.append(relationship)

    def to_tagvalue(self) -> list[str]:
        """Generate a list of tag:value lines describing the SPDX document."""
        output: list[str] = []
        is_first_section = True

        def add_section(section: str) -> None:
            nonlocal is_first_section
            nonlocal output
            if not is_first_section:
                output += ["", ""]
            is_first_section = False
            output += [f"# {section}", ""]

        add_section("Document Information")
        output += self.doc_info.to_tagvalue()

        add_section("Creation Info")
        output += self.creation_info.to_tagvalue()

        # Keep track of the packages which should appear first.
        pkg_ids: list[SPDXID] = []
        add_section("Relationships")
        relas: list[str] = []
        rel_ix: int = 0
        for rel in sorted(
            self.relationships, key=lambda rela: rela.related_spdx_element
        ):
            if (
                rel.spdx_element_id == self.spdx_id
                and rel.relationship_type == RelationshipType.DESCRIBES
            ):
                # Make the described packages appear first in list.
                relas.insert(rel_ix, rel.to_tagvalue())
                rel_ix += 1
                # Keep track of those leading packages IDs.
                pkg_ids.append(rel.related_spdx_element)
            else:
                relas.append(rel.to_tagvalue())

        output += relas

        packages: list[str] = ["", ""]

        for pkg in sorted(self.packages.values(), key=lambda package: package.name):
            if pkg.spdx_id in pkg_ids:
                packages = ["", "", "# Package", ""] + pkg.to_tagvalue() + packages
            else:
                packages += ["# Package", ""] + pkg.to_tagvalue() + ["", ""]

        output += packages
        return output

    def to_json_dict(self) -> dict[str, Any]:
        """Generate a representation of an SPDX following the JSON schema.

        Generate a dictionary that can be dumped into a JSON.
        """
        output: dict[str, Any] = self.doc_info.to_json_dict()
        output["creationInfo"] = self.creation_info.to_json_dict()
        output["documentDescribes"] = []
        output["relationships"] = []
        for rel in sorted(
            self.relationships, key=lambda rela: rela.related_spdx_element
        ):
            if (
                rel.spdx_element_id == self.spdx_id
                and rel.relationship_type == RelationshipType.DESCRIBES
            ):
                output["documentDescribes"].append(str(rel.related_spdx_element))
            else:
                output["relationships"].append(rel.to_json_dict())

        packages: list[dict] = []
        described_ix: int = 0
        for p in sorted(self.packages.values(), key=lambda package: package.name):
            if str(p.spdx_id) in output["documentDescribes"]:
                # Make the described packages appear first in list.
                packages.insert(described_ix, p.to_json_dict())
                described_ix += 1
            else:
                # Other packages are already sorted by name, append them as
                # they come.
                packages.append(p.to_json_dict())

        output["packages"] = packages

        return output
