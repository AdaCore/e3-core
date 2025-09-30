"""Generate an SPDX file.

This is following the specification from https://spdx.github.io/spdx-spec/v2.3/
a simple example can be found at ./tests/tests_e3/spdx_test.py
"""

from __future__ import annotations

import re

from enum import Enum, auto
from abc import ABCMeta, abstractmethod
from dataclasses import dataclass, field, fields
from datetime import datetime, timezone
from uuid import uuid4

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


def get_entity(value: str | None) -> Organization | Person | Tool | None:
    """Get an entity according to an entity string.

    The entity string looks like ``<entity_type>: <entity_name>``. If the
    entity type is ``Organization``, ``Person`` or ``Tool``, the appropriate
    :class:`Organization`, :class:`Person` or :class:`Tool` initialised with
    *entity_name* is returned.

    If not possible match if found, :const:`None` is returned.

    :param value: A string to extract entity definition from.

    :return: The entity initialised by *value*, or :const:`None` on error.
    """  # noqa RST304
    if isinstance(value, str) and ":" in value:
        entity_type, entity_name = value.split(":", 1)
        if entity_type.lower() == "tool":
            return Tool(entity_name.strip())
        elif entity_type.lower() == "person":
            return Person(entity_name.strip())
        elif entity_type.lower() == "organization":
            return Organization(entity_name.strip())
    return None


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

    @classmethod
    def get_entry_key(cls) -> str:
        """Name of the SPDXEntry as visible in the SPDX tag:value report."""
        return cls.__name__

    @classmethod
    def get_json_entry_key(cls) -> str:
        """Name of the SPDXEntry as visible in the SPDX JSON report."""
        if isinstance(cls.json_entry_key, str):
            return str(cls.json_entry_key)  # type: ignore[unreachable]
        else:
            entry_key: str = cls.get_entry_key()
            return f"{entry_key[0].lower()}{entry_key[1:]}"

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

    VERSION: str = "SPDX-2.3"

    json_entry_key = "spdxVersion"

    @classmethod
    def from_json_dict(cls, obj: dict[str, Any]) -> SPDXVersion:
        """Initialize an :class:`SPDXVersion` from a :class:`dict`.

        If an SPDX version value could not be extracted from *obj*, the default
        value :attr:`SPDXVersion.VERSION` is used.

        :param obj: A :class:`dict` which key is this class' JSON entry key,
            and the value, an object to initialize an :class:`SPDXVersion` with.

        For instance:

        >>> from e3.spdx import SPDXVersion
        >>> SPDXVersion.from_json_dict({"spdxVersion": "1.2.3"}).value
        '1.2.3'
        >>> SPDXVersion.from_json_dict({"xxx": "1.2.3"}).value
        'SPDX-2.3'

        :return: The :class:`SPDXVersion` initialized with the value of *obj*.
        """  # noqa RST304
        return SPDXVersion(obj.get(cls.get_json_entry_key(), cls.VERSION))


class DataLicense(SPDXEntryStr):
    """License of the SPDX Metadata.

    See 6.2 `Data license field
    <https://spdx.github.io/spdx-spec/v2.3/document-creation-information/#62-data-license-field>`_.
    """

    LICENSE: str = "CC0-1.0"

    @classmethod
    def from_json_dict(cls, obj: dict[str, Any]) -> DataLicense:
        """Initialize a :class:`DataLicense` from a :class:`dict`.

        If a data license value could not be extracted from *obj*, the default
        value :attr:`DataLicense.LICENSE` is used.

        :param obj: A :class:`dict` which key is this class' JSON entry key,
            and the value, an object to initialize a :class:`DataLicense` with.

        For instance:

        >>> from e3.spdx import DataLicense
        >>> DataLicense.from_json_dict({"dataLicense": "1.2.3"}).value
        '1.2.3'
        >>> DataLicense.from_json_dict({"xxx": "1.2.3"}).value
        'CC0-1.0'

        :return: The :class:`DataLicense` initialized with the value of *obj*.
        """  # noqa RST304
        return DataLicense(obj.get(cls.get_json_entry_key(), cls.LICENSE))


class SPDXID(SPDXEntryStr):
    """Identify an SPDX Document, or Package.

    See 6.3 `SPDX identifier field
    <https://spdx.github.io/spdx-spec/v2.3/document-creation-information/#63-spdx-identifier-field>`_
    and 7.2 `Package SPDX identifier field
    <https://spdx.github.io/spdx-spec/v2.3/package-information/#72-package-spdx-identifier-field>`_.

    The value is a unique string containing letters, numbers, ., and/or -.
    """

    PREFIX: str = "SPDXRef-"
    DEFAULT_ID: str = "DOCUMENT"

    json_entry_key = "SPDXID"

    def __init__(self, value: str) -> None:
        # The format of the SPDXID should be "SPDXRef-"[idstring]
        # where [idstring] is a unique string containing letters, numbers, .,
        # and/or -.
        if value.startswith(self.PREFIX):
            value = value[len(self.PREFIX) :]
        super().__init__(re.sub(SPDXID_R, "", value))

    def __str__(self) -> str:
        return f"{self.PREFIX}{self.value}"

    def __eq__(self, o: object) -> bool:
        return isinstance(o, SPDXID) and o.value == self.value

    def __hash__(self) -> int:
        return hash(self.value)

    @classmethod
    def from_json_dict(cls, obj: dict[str, Any]) -> SPDXID:
        """Initialize an :class:`SPDXID` from a :class:`dict`.

        If an SPDX ID value could not be extracted from *obj*, the default
        value :attr:`SPDXID.DEFAULT_ID` is used.

        :param obj: A :class:`dict` which key is this class' JSON entry key,
            and the value, an object to initialize an :class:`SPDXID` with.

        For instance:

        >>> from e3.spdx import SPDXID
        >>> SPDXID.from_json_dict({"SPDXID": "1.2.3"}).value
        '1.2.3'
        >>> SPDXID.from_json_dict({"xxx": "1.2.3"}).value
        'DOCUMENT'

        :return: The :class:`SPDXID` initialized with the value of *obj*.
        """  # noqa RST304
        id_from_dict: str = obj.get(cls.get_json_entry_key(), cls.DEFAULT_ID)
        if id_from_dict.startswith(f"{cls.PREFIX}"):
            id_from_dict = id_from_dict[len(cls.PREFIX) :]
        return SPDXID(id_from_dict)


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

    @classmethod
    def from_json_dict(cls, obj: dict[str, Any]) -> DocumentNamespace:
        """Initialize a :class:`DocumentNamespace` from a :class:`dict`.

        If a document namespace value could not be extracted from *obj*, an
        empty string is used.

        :param obj: A :class:`dict` which key is this class' JSON entry key,
            and the value, an object to initialize a :class:`DocumentNamespace`
            with.

        For instance:

        >>> from e3.spdx import DocumentNamespace
        >>> DocumentNamespace.from_json_dict({"documentNamespace": "namespace"}).value
        'namespace'
        >>> DocumentNamespace.from_json_dict({"xxx": "namespace"}).value
        ''

        :return: The :class:`DocumentNamespace` initialized with the value of
            *obj*.
        """  # noqa RST304
        return DocumentNamespace(obj.get(cls.get_json_entry_key(), ""))


class LicenseListVersion(SPDXEntryStr):
    """Provide the version of the SPDX License List used.

    See 6.7 `License list version field
    <https://spdx.github.io/spdx-spec/v2.3/document-creation-information/#67-license-list-version-field>`_.
    """

    VERSION: str = "3.19"
    """Default license list version value."""

    @classmethod
    def from_json_dict(cls, obj: dict[str, str]) -> LicenseListVersion:
        """Initialize a :class:`LicenseListVersion` from a :class:`dict`.

        If a license list version value could not be extracted from *obj*, the
        default :attr:`LicenseListVersion.VERSION` value is used.

        :param obj: A :class:`dict` which key is this class' JSON entry key,
            and the value, an object to initialize a :class:`LicenseListVersion`
            with.

        For instance:

        >>> from e3.spdx import LicenseListVersion
        >>> LicenseListVersion.from_json_dict({"licenseListVersion": "3.2.1"}).value
        '3.2.1'
        >>> LicenseListVersion.from_json_dict({"xxx": "3.2.1"}).value
        '3.19'

        :return: The :class:`LicenseListVersion` initialized with the value of
            *obj*.
        """  # noqa RST304
        return LicenseListVersion(obj.get(cls.get_json_entry_key(), cls.VERSION))


class Entity(SPDXEntryStr):
    """Represent an Entity (Organization, Person, Tool)."""

    @classmethod
    def from_json_dict(cls, obj: dict[str, str]) -> Tool | Person | Organization | None:
        """Initialize an :class:`Entity` from a :class:`dict`.

        :param obj: A :class:`dict` which key is this class' JSON entry key,
            and the value, an object to initialize an :class:`Entity`
            with.

        :return: The :class:`Entity` initialized with the value of *obj*, or
            :const:`None` if the JSON key does not match.
        """  # noqa RST304
        return get_entity(obj.get(cls.get_json_entry_key()))


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

    @classmethod
    def from_json_dict(cls, obj: dict[str, Any]) -> Creator | None:
        """Initialize a :class:`Creator` from a :class:`dict`.

        :param obj: A :class:`dict` which key is this class' JSON entry key,
            and the value, an object to initialize a :class:`Creator` with.

        :return: The :class:`Creator` initialized with the value of *obj*, or
            :const:`None` if the JSON key does not match.
        """  # noqa RST304
        entity: Organization | Person | Tool | None = get_entity(
            obj.get(cls.get_json_entry_key())
        )
        if entity is not None:
            return cls(entity)
        return None


class Created(SPDXEntryStr):
    """Identify when the SPDX document was originally created.

    See 6.9 `Created field
    <https://spdx.github.io/spdx-spec/v2.3/document-creation-information/#69-created-field>`_.
    """

    @classmethod
    def from_json_dict(cls, obj: dict[str, Any]) -> Created:
        """Initialize a :class:`Created` from a :class:`dict`.

        :param obj: A :class:`dict` which key is this class' JSON entry key,
            and the value, an object to initialize an :class:`Created`
            with.

        :return: The :class:`Created` initialized with the value of *obj*.
        """  # noqa RST304
        if cls.get_json_entry_key() in obj:
            return Created(str(obj.get(cls.get_json_entry_key(), "")))
        return Created(datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))


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

    @classmethod
    def from_json_dict(cls, obj: dict[str, Any]) -> PackageName:
        """Initialize a :class:`PackageName` from a :class:`dict`.

        :param obj: A :class:`dict` which key is this class' JSON entry key,
            and the value, an object to initialize an :class:`PackageName`
            with.

        :return: The :class:`PackageName` initialized with the value of *obj*.
        """  # noqa RST304
        return PackageName(str(obj.get(cls.get_json_entry_key(), "")))


class PackageVersion(SPDXEntryStr):
    """Identify the version of the package.

    See 7.3 `Package version field
    <https://spdx.github.io/spdx-spec/v2.3/package-information/#73-package-version-field>`_
    """

    json_entry_key = "versionInfo"

    @classmethod
    def from_json_dict(cls, obj: dict[str, Any]) -> PackageVersion:
        """Initialize a :class:`PackageVersion` from a :class:`dict`.

        :param obj: A :class:`dict` which key is this class' JSON entry key,
            and the value, an object to initialize an :class:`PackageVersion`
            with.

        :return: The :class:`PackageVersion` initialized with the value of *obj*.
        """  # noqa RST304
        return PackageVersion(str(obj.get(cls.get_json_entry_key(), "")))


class PackageFileName(SPDXEntryStr):
    """Provide the actual file name of the package.

    See 7.4 `Package file name field
    <https://spdx.github.io/spdx-spec/v2.3/package-information/#74-package-file-name-field>`_
    """

    @classmethod
    def from_json_dict(cls, obj: dict[str, Any]) -> PackageFileName:
        """Initialize a :class:`PackageFileName` from a :class:`dict`.

        :param obj: A :class:`dict` which key is this class' JSON entry key,
            and the value, an object to initialize an :class:`PackageFileName`
            with.

        :return: The :class:`PackageFileName` initialized with the value of *obj*.
        """  # noqa RST304
        return PackageFileName(str(obj.get(cls.get_json_entry_key(), "")))


class PackageSupplier(EntityRef):
    """Identify the actual distribution source for the package.

    See 7.5 `Package supplier field
    <https://spdx.github.io/spdx-spec/v2.3/package-information/#75-package-supplier-field>`_
    """

    json_entry_key = "supplier"

    @classmethod
    def from_json_dict(cls, obj: dict[str, Any]) -> PackageSupplier | None:
        """Initialize a :class:`PackageSupplier` from a :class:`dict`.

        :param obj: A :class:`dict` which key is this class' JSON entry key,
            and the value, an object to initialize a :class:`PackageSupplier`
            with.

        :return: The :class:`PackageSupplier` initialized with the value of
            *obj*, or :const:`None` if the JSON key does not match.
        """  # noqa RST304
        entity: Organization | Person | Tool | None = get_entity(
            obj.get(cls.get_json_entry_key())
        )
        if entity is not None:
            return cls(entity)
        return None


class PackageOriginator(EntityRef):
    """Identify from where the package originally came.

    See 7.6 `Package originator field
    <https://spdx.github.io/spdx-spec/v2.3/package-information/#76-package-originator-field>`_
    """

    json_entry_key = "originator"

    @classmethod
    def from_json_dict(cls, obj: dict[str, Any]) -> PackageOriginator | None:
        """Initialize a :class:`PackageOriginator` from a :class:`dict`.

        :param obj: A :class:`dict` which key is this class' JSON entry key,
            and the value, an object to initialize a :class:`PackageOriginator`
            with.

        :return: The :class:`PackageOriginator` initialized with the value of
            *obj*, or :const:`None` if the JSON key does not match.
        """  # noqa RST304
        entity: Organization | Person | Tool | None = get_entity(
            obj.get(cls.get_json_entry_key())
        )
        if entity is not None:
            return cls(entity)
        return None


class PackageDownloadLocation(SPDXEntryMaybeStr):
    """Identifies the download location of the package.

    See 7.7 `Package download location field
    <https://spdx.github.io/spdx-spec/v2.3/package-information/#77-package-download-location-field>`_
    """

    json_entry_key = "downloadLocation"

    @classmethod
    def from_json_dict(cls, obj: dict[str, Any]) -> PackageDownloadLocation:
        """Initialize a :class:`PackageDownloadLocation` from a :class:`dict`.

        :param obj: A :class:`dict` which key is this class' JSON entry key,
            and the value, an object to initialize an :class:`PackageDownloadLocation`
            with.

        :return: The :class:`PackageDownloadLocation` initialized with the value of *obj*.
        """  # noqa RST304
        return PackageDownloadLocation(obj.get(cls.get_json_entry_key(), NONE_VALUE))


class FilesAnalyzed(SPDXEntryBool):
    """Indicates whether the file content of this package have been analyzed.

    See 7.8 `Files analyzed field
    <https://spdx.github.io/spdx-spec/v2.3/package-information/#78-files-analyzed-field>`_
    """

    @classmethod
    def from_json_dict(cls, obj: dict[str, Any]) -> FilesAnalyzed:
        """Initialize a :class:`FilesAnalyzed` from a :class:`dict`.

        By default, if *obj* does not contain this class' JSON entry key,
        ``FilesAnalyzed(False)`` is returned.

        :param obj: A :class:`dict` which key is this class' JSON entry key,
            and the value, an object to initialize an :class:`FilesAnalyzed`
            with.

        :return: The :class:`FilesAnalyzed` initialized with the value of *obj*.
        """  # noqa RST304
        if cls.get_json_entry_key() in obj:
            return FilesAnalyzed(obj.get(cls.get_json_entry_key(), False))
        return FilesAnalyzed(False)


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

    @classmethod
    def from_json_dict(cls, obj: dict[str, Any]) -> PackageChecksum:
        """Initialize a :class:`PackageChecksum` from a :class:`dict`.

        Supported algorithms so far:

        - `sha1`
        - `sha256`
        - `sha512`

        :param obj: A :class:`dict` which key is this class' JSON entry key,
            and the value, an object to initialize an :class:`PackageChecksum`
            with.

        :return: The :class:`PackageChecksum` initialized with the value of *obj*.

        :raise: :exc:`ValueError` if the algorithm defined by *obj* is not supported.
        """  # noqa RST304
        if isinstance(obj, dict) and "algorithm" in obj and "checksumValue" in obj:
            if obj["algorithm"].upper() == SHA1.algorithm:
                return SHA1(obj["checksumValue"])
            elif obj["algorithm"].upper() == SHA256.algorithm:
                return SHA256(obj["checksumValue"])
            elif obj["algorithm"].upper() == SHA512.algorithm:
                return SHA512(obj["checksumValue"])
            else:
                raise ValueError(f"Unsupported checksum algorithm {obj['algorithm']}.")
        raise ValueError(f"Invalid input checksum dict {obj!r}.")


class PackageHomePage(SPDXEntryMaybeStr):
    """Identifies the homepage location of the package.

    See 7.11 `Package home page field
    <https://spdx.github.io/spdx-spec/v2.3/package-information/#711-package-home-page-field>`_
    """

    json_entry_key = "homepage"

    @classmethod
    def from_json_dict(cls, obj: dict[str, Any]) -> PackageHomePage | None:
        """Initialize a :class:`PackageHomePage` from a :class:`dict`.

        :param obj: A :class:`dict` which key is this class' JSON entry key,
            and the value, an object to initialize an :class:`PackageHomePage`
            with.

        :return: The :class:`PackageHomePage` initialized with the value of *obj*.
        """  # noqa RST304
        homepage: Literal["NOASSERTION", "NONE"] | str | None = obj.get(
            cls.get_json_entry_key()
        )
        if homepage is not None:
            return PackageHomePage(homepage)
        return None


class SHA1(PackageChecksum):
    algorithm = "SHA1"


class SHA256(PackageChecksum):
    algorithm = "SHA256"


class SHA512(PackageChecksum):
    algorithm = "SHA512"


class PackageLicenseConcluded(SPDXEntryMaybeStr):
    """Contain the license concluded as governing the package.

    See 7.13 `Concluded license field
    <https://spdx.github.io/spdx-spec/v2.3/package-information/#713-concluded-license-field>`_
    """

    json_entry_key = "licenseConcluded"

    @classmethod
    def from_json_dict(cls, obj: dict[str, Any]) -> PackageLicenseConcluded:
        """Initialize a :class:`PackageLicenseConcluded` from a :class:`dict`.

        By default a :class:`PackageLicenseConcluded(NONE_VALUE)` is returned.

        :param obj: A :class:`dict` which key is this class' JSON entry key,
            and the value, an object to initialize an
            :class:`PackageLicenseConcluded` with.

        :return: The :class:`PackageLicenseConcluded` initialized with the value
            of *obj*.
        """  # noqa RST304
        lic: Literal["NOASSERTION", "NONE"] | str | None = obj.get(
            cls.get_json_entry_key(), NONE_VALUE
        )
        if lic is not None:
            return PackageLicenseConcluded(lic)
        return PackageLicenseConcluded(NONE_VALUE)


class PackageLicenseDeclared(SPDXEntryMaybeStr):
    """Contain the license having been declared by the authors of the package.

    See 7.15 `Declared license field
    <https://spdx.github.io/spdx-spec/v2.3/package-information/#715-declared-license-field>`_
    """

    json_entry_key = "licenseDeclared"

    @classmethod
    def from_json_dict(cls, obj: dict[str, Any]) -> PackageLicenseDeclared | None:
        """Initialize a :class:`PackageLicenseDeclared` from a :class:`dict`.

        By default :const:`None` is returned.

        :param obj: A :class:`dict` which key is this class' JSON entry key,
            and the value, an object to initialize an
            :class:`PackageLicenseDeclared` with.

        :return: The :class:`PackageLicenseDeclared` initialized with the value
            of *obj*.
        """  # noqa RST304
        lic: Literal["NOASSERTION", "NONE"] | str | None = obj.get(
            cls.get_json_entry_key()
        )
        if lic is not None:
            return PackageLicenseDeclared(lic)
        return None


class PackageLicenseComments(SPDXEntryMaybeStrMultilines):
    """Record background information or analysis for the Concluded License.

    See 7.16 `Comments on license field
    <https://spdx.github.io/spdx-spec/v2.3/package-information/#716-comments-on-license-field>`_
    """

    json_entry_key = "licenseComments"

    @classmethod
    def from_json_dict(cls, obj: dict[str, Any]) -> PackageLicenseComments | None:
        """Initialize a :class:`PackageLicenseComments` from a :class:`dict`.

        By default :const:`None` is returned.

        :param obj: A :class:`dict` which key is this class' JSON entry key,
            and the value, an object to initialize an
            :class:`PackageLicenseComments` with.

        :return: The :class:`PackageLicenseComments` initialized with the value
            of *obj*.
        """  # noqa RST304
        comment: Literal["NOASSERTION", "NONE"] | str | None = obj.get(
            cls.get_json_entry_key()
        )
        if comment is not None:
            return PackageLicenseComments(comment)
        return None


class PackageCopyrightText(SPDXEntryMaybeStrMultilines):
    """Identify the copyright holders of the package.

    See 7.17 `Copyright text field
    <https://spdx.github.io/spdx-spec/v2.3/package-information/#717-copyright-text-field>`_
    """

    json_entry_key = "copyrightText"

    @classmethod
    def from_json_dict(cls, obj: dict[str, Any]) -> PackageCopyrightText | None:
        """Initialize a :class:`PackageCopyrightText` from a :class:`dict`.

        By default :const:`None` is returned.

        :param obj: A :class:`dict` which key is this class' JSON entry key,
            and the value, an object to initialize an
            :class:`PackageCopyrightText` with.

        :return: The :class:`PackageCopyrightText` initialized with the value
            of *obj*.
        """  # noqa RST304
        txt: Literal["NOASSERTION", "NONE"] | str | None = obj.get(
            cls.get_json_entry_key()
        )
        if txt is not None:
            return PackageCopyrightText(txt)
        return None


class PackageDescription(SPDXEntryMaybeStrMultilines):
    """A more detailed description of the package.

    It may also be extracted from the packages itself.

    Provides recipients of the SPDX document with a detailed technical
    explanation of the functionality, anticipated use, and anticipated
    implementation of the package. This field may also include a description
    of improvements over prior versions of the package.

    See 7.19 `Package detailed description field
    <https://spdx.github.io/spdx-spec/v2.3/package-information/#719-package-detailed-description-field>`_
    """

    json_entry_key = "description"

    @classmethod
    def from_json_dict(cls, obj: dict[str, Any]) -> PackageDescription | None:
        """Initialize a :class:`PackageDescription` from a :class:`dict`.

        By default :const:`None` is returned.

        :param obj: A :class:`dict` which key is this class' JSON entry key,
            and the value, an object to initialize an
            :class:`PackageDescription` with.

        :return: The :class:`PackageDescription` initialized with the value
            of *obj*.
        """  # noqa RST304
        desc: Literal["NOASSERTION", "NONE"] | str | None = obj.get(
            cls.get_json_entry_key()
        )
        if desc is not None:
            return PackageDescription(desc)
        return None


class PackageComment(SPDXEntryMaybeStrMultilines):
    """Record background information or analysis for the Concluded License.

    See 7.20 `Package comment field
    <https://spdx.github.io/spdx-spec/v2.3/package-information/#720-package-comment-field>`_
    """

    json_entry_key = "comment"

    @classmethod
    def from_json_dict(cls, obj: dict[str, Any]) -> PackageComment | None:
        """Initialize a :class:`PackageComment` from a :class:`dict`.

        By default :const:`None` is returned.

        :param obj: A :class:`dict` which key is this class' JSON entry key,
            and the value, an object to initialize an
            :class:`PackageComment` with.

        :return: The :class:`PackageComment` initialized with the value
            of *obj*.
        """  # noqa RST304
        comment: Literal["NOASSERTION", "NONE"] | str | None = obj.get(
            cls.get_json_entry_key()
        )
        if comment is not None:
            return PackageComment(comment)
        return None


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
        """Initialize an :class:`ExternalRef` from a :class:`dict`.

        :param external_ref_dict: A :class:`dict` containing the
            ``"referenceCategory"``, ``"referenceType"`` and
            ``"referenceLocator"`` keys. The values of those keys are used
            to initialize a new :class:`ExternalRef`.

        :return: The :class:`ExternalRef` initialized with the value
            of *external_ref_dict*.
        """  # noqa RST304
        return ExternalRef(
            reference_category=ExternalRefCategory(
                external_ref_dict["referenceCategory"]
            ),
            reference_type=external_ref_dict["referenceType"],
            reference_locator=external_ref_dict["referenceLocator"],
        )


class PrimaryPackagePurpose(Enum):
    """Provides information about the primary purpose of the identified package.

    Package Purpose is intrinsic to how the package is being used rather than
    the content of the package. The options to populate this field are limited
    to the values below.

    See 7.24 `Primary Package Purpose field
    <https://spdx.github.io/spdx-spec/v2.3/package-information/#724-primary-package-purpose-field>`_
    """  # noqa: B950

    APPLICATION = auto()
    # If the package is a software application
    FRAMEWORK = auto()
    # If the package is a software framework
    LIBRARY = auto()
    # If the package is a software library
    CONTAINER = auto()
    # If the package refers to a container image which can be used by a
    # container runtime application
    OPERATING_SYSTEM = auto()
    # If the package refers to an operating system
    DEVICE = auto()
    # If the package refers to a chipset, processor, or electronic board
    FIRMWARE = auto()
    # If the package provides low level control over a device's hardware
    SOURCE = auto()
    # If the package is a collection of source files
    ARCHIVE = auto()
    # If the package refers to an archived collection of files (.tar, .zip,
    # etc.)
    FILE = auto()
    # If the package is a single file which can be independently distributed
    # (configuration file, statically linked binary, Kubernetes deployment,
    # etc.)
    INSTALL = auto()
    # If the package is used to install software on disk
    OTHER = auto()
    # If the package doesn't fit into the above categories.

    @classmethod
    def get_json_entry_key(cls) -> str:
        return f"{cls.__name__[0].lower()}{cls.__name__[1:]}"

    def to_tagvalue(self) -> str:
        return f"{self.__class__.__name__}: {self.name}"

    def to_json_dict(self) -> dict[str, str]:
        return {self.get_json_entry_key(): self.name}

    @classmethod
    def from_json_dict(cls, obj: dict[str, Any]) -> PrimaryPackagePurpose | None:
        """Initialize a :class:`PrimaryPackagePurpose` from a :class:`dict`.

        By default :const:`None` is returned.

        :param obj: A :class:`dict` which key is this class' JSON entry key,
            and the value, an object to initialize an
            :class:`PrimaryPackagePurpose` with.

        :return: The :class:`PrimaryPackagePurpose` initialized with the value
            of *obj*.
        """  # noqa RST304
        purpose_name: str | None = obj.get(cls.get_json_entry_key(), None)
        if purpose_name:
            return PrimaryPackagePurpose.__members__[purpose_name]
        return None


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

    @classmethod
    def get_json_entry_key(cls) -> str:
        return f"{cls.__name__[0].lower()}{cls.__name__[1:]}"

    def to_tagvalue(self) -> str:
        return f"{self.__class__.__name__}: {self.name}"

    def to_json_dict(self) -> dict[str, str]:
        return {self.get_json_entry_key(): self.name}

    @classmethod
    def from_json_dict(cls, obj: dict[str, Any]) -> RelationshipType:
        """Initialize a :class:`RelationshipType` from a :class:`dict`.

        By default ``RelationshipType.OTHER`` is returned.

        :param obj: A :class:`dict` which key is this class' JSON entry key,
            and the value, an object to initialize an
            :class:`RelationshipType` with.

        :return: The :class:`RelationshipType` initialized with the value
            of *obj*.
        """  # noqa RST304
        if cls.get_json_entry_key() in obj:
            rela_name: str = obj.get(
                cls.get_json_entry_key(), RelationshipType.OTHER.name
            )
            return RelationshipType.__members__[rela_name]
        return RelationshipType.OTHER


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

    @classmethod
    def from_json_dict(cls, obj: dict[str, Any]) -> Relationship:
        """Initialize a :class:`Relationship` from a :class:`dict`.

        :param obj: A :class:`dict` which key is this class' JSON entry key,
            and the value, an object to initialize an
            :class:`Relationship` with.

        :return: The :class:`Relationship` initialized with the value
            of *obj*.
        """  # noqa RST304
        return Relationship(
            spdx_element_id=SPDXID.from_json_dict(
                {SPDXID.get_json_entry_key(): obj.get("spdxElementId")}
            ),
            relationship_type=RelationshipType.from_json_dict(obj),
            related_spdx_element=SPDXID.from_json_dict(
                {SPDXID.get_json_entry_key(): obj.get("relatedSpdxElement")}
            ),
        )


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
    :ivar PrimaryPackagePurposeType | None primary_purpose: Provides information
        about the primary purpose of the identified package. Package Purpose is
        intrinsic to how the package is being used rather than the content of
        the package.
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
    :ivar PackageDescription | None description: This field is a more detailed
        description of the package. It may also be extracted from the packages
        itself.
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
    copyright_text: PackageCopyrightText | None
    files_analyzed: FilesAnalyzed
    license_concluded: PackageLicenseConcluded
    license_comments: PackageLicenseComments | None
    license_declared: PackageLicenseDeclared | None
    homepage: PackageHomePage | None
    download_location: PackageDownloadLocation
    external_refs: list[ExternalRef] | None
    comment: PackageComment | None = field(default=None)
    primary_purpose: PrimaryPackagePurpose | None = field(default=None)
    description: PackageDescription | None = field(default=None)

    @classmethod
    def from_json_dict(cls, package_dict: dict[str, Any]) -> Package:
        """Initialize a :class:`Package` from a :class:`dict`.

        :param package_dict: A :class:`dict` containing JSON elements to
            initialize this :class:`Package` with.

        :return: The :class:`Package` initialized with the values of *obj*.
        """  # noqa RST304
        checksums: list[PackageChecksum] = [
            PackageChecksum.from_json_dict(ck_dict)
            for ck_dict in package_dict.get(PackageChecksum.get_json_entry_key(), [])
        ]
        external_refs: list[ExternalRef] | None = None
        if ExternalRef.get_json_entry_key() in package_dict:
            external_refs = []
            for ext_ref_dict in package_dict.get(ExternalRef.get_json_entry_key(), {}):
                external_refs.append(ExternalRef.from_dict(ext_ref_dict))
        pkg: Package = Package(
            name=PackageName.from_json_dict(package_dict),
            spdx_id=SPDXID.from_json_dict(package_dict),
            version=PackageVersion.from_json_dict(package_dict),
            file_name=PackageFileName.from_json_dict(package_dict),
            checksum=checksums,
            supplier=PackageSupplier.from_json_dict(package_dict)
            or PackageSupplier(Organization("AdaCore")),
            originator=PackageOriginator.from_json_dict(package_dict)
            or PackageOriginator(Organization("AdaCore")),
            copyright_text=PackageCopyrightText.from_json_dict(package_dict),
            files_analyzed=FilesAnalyzed.from_json_dict(package_dict),
            license_concluded=PackageLicenseConcluded.from_json_dict(package_dict),
            license_comments=PackageLicenseComments.from_json_dict(package_dict),
            license_declared=PackageLicenseDeclared.from_json_dict(package_dict),
            homepage=PackageHomePage.from_json_dict(package_dict),
            download_location=PackageDownloadLocation.from_json_dict(package_dict),
            external_refs=external_refs,
            comment=PackageComment.from_json_dict(package_dict),
            primary_purpose=PrimaryPackagePurpose.from_json_dict(package_dict),
            description=PackageDescription.from_json_dict(package_dict),
        )
        return pkg


@dataclass
class DocumentInformation(SPDXSection):
    """Describe the SPDX Document."""

    document_name: DocumentName
    document_namespace: DocumentNamespace = field(init=False)
    version: SPDXVersion = SPDXVersion(SPDXVersion.VERSION)
    data_license: DataLicense = DataLicense(DataLicense.LICENSE)
    spdx_id: SPDXID = SPDXID(SPDXID.DEFAULT_ID)

    def __post_init__(self) -> None:
        self.document_namespace = DocumentNamespace(f"{self.document_name}-{uuid4()}")

    @classmethod
    def from_json_dict(cls, obj: dict[str, Any]) -> DocumentInformation:
        """Initialize a :class:`DocumentInformation` from a :class:`dict`.

        :param obj: A :class:`dict` containing JSON elements to initialize this
            :class:`DocumentInformation` with.

        :return: The :class:`DocumentInformation` initialized with the values of
            *obj*.
        """  # noqa RST304
        res: DocumentInformation = DocumentInformation(
            DocumentName(obj.get("name", ""))
        )
        if DocumentNamespace.get_json_entry_key() in obj:
            res.document_namespace = DocumentNamespace.from_json_dict(obj)
        if SPDXVersion.get_json_entry_key() in obj:
            res.version = SPDXVersion.from_json_dict(obj)
        if DataLicense.get_json_entry_key() in obj:
            res.data_license = DataLicense.from_json_dict(obj)
        if SPDXID.get_json_entry_key() in obj:
            res.spdx_id = SPDXID.from_json_dict(obj)
        return res


@dataclass
class CreationInformation(SPDXSection):
    """Document where and by whom the SPDX document has been created."""

    creators: list[Creator]
    created_now: Created = field(init=False)
    license_list_version: LicenseListVersion = LicenseListVersion(
        LicenseListVersion.VERSION
    )

    def __post_init__(self) -> None:
        self.created_now = Created(
            datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        )

    @classmethod
    def from_json_dict(cls, obj: dict[str, Any]) -> CreationInformation:
        """Initialize a :class:`CreationInformation` from a :class:`dict`.

        :param obj: A :class:`dict` containing JSON elements to initialize this
            :class:`CreationInformation` with.

        :return: The :class:`CreationInformation` initialized with the values of
            *obj*.
        """  # noqa RST304
        if "creationInfo" in obj:
            ci_dict: dict = obj.get("creationInfo", {})
            creators: list[Creator] = []
            for entity in ci_dict.get(Creator.json_entry_key, []):
                creator: Creator | None = Creator.from_json_dict(
                    {Creator.get_json_entry_key(): entity}
                )
                if creator is not None:
                    creators.append(creator)
            creation_info: CreationInformation = CreationInformation(
                license_list_version=LicenseListVersion.from_json_dict(ci_dict),
                creators=creators,
            )
            if Created.get_json_entry_key() in ci_dict:
                creation_info.created_now = Created.from_json_dict(ci_dict)
            return creation_info
        return CreationInformation(
            license_list_version=cls.license_list_version,
            creators=[Creator(NOASSERTION)],
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

    @classmethod
    def from_json_dict(cls, doc_dict: dict[str, Any]) -> Document:
        """Create a :class:`Document` out of a JSON :class:`dict`.

        This may be used when initializing a :class:`Document` from an SPDX
        JSON file, or to duplicate a :class:`Document`.

        For instance:

        >>> import json
        >>> from pathlib import Path
        >>> with Path("my.spdx.json").(encoding="utf-8", errors="replace") as spdx_handle:
        >>>     spdx_dict = json.load(spdx_handle)
        >>> spdx_doc: Document = Document.from_json_dict(spdx_dict)
        >>> spdx_doc2: Document = Document.from_json_dict(spdx_doc.to_json_dict())

        :param doc_dict: The :class:`dict` containing JSON values to initialize
            this :class:`Document` with.

        :returns: A new :class:`Document` initialized with the JSON values of
            *doc_dict*.
        """  # noqa RST304
        creators: list[Entity] = []
        # As the Entity.from_json_dict() may return None, better handle the
        # case.
        for creator in doc_dict.get("creationInfo", {}).get("creators", []):
            entity: Entity | None = Entity.from_json_dict(
                {Entity.get_json_entry_key(): creator}
            )
            if entity is not None:
                creators.append(entity)

        doc: Document = Document(
            document_name=doc_dict.get("name", ""),
            creators=creators,
        )
        doc.creation_info = CreationInformation.from_json_dict(doc_dict)
        doc.doc_info = DocumentInformation.from_json_dict(doc_dict)

        # Look for the main package in documentDescribes entry. If it does not
        # exist, we may look at packages with a primaryPackagePurpose field.
        main_packages: list[SPDXID] = []
        for spdx_id in doc_dict.get("documentDescribes", []):
            main_packages.append(SPDXID(spdx_id))
        if not main_packages:
            # Look for a package with  a primaryPackagePurpose field.
            for package_dict in doc_dict.get("packages", []):
                if PrimaryPackagePurpose.get_json_entry_key() in package_dict:
                    main_packages.append(package_dict.get(SPDXID.json_entry_key))

        # Now that we know which package is the main package, we may add all
        # packages to the SPDX document.
        package: Package
        for package_dict in doc_dict.get("packages", []):
            package = Package.from_json_dict(package_dict)
            is_main_package: bool = package.spdx_id in main_packages

            # Set add_relationship for main package only, all other
            # relationships are added later on.
            doc.add_package(
                package,
                is_main_package=is_main_package,
                add_relationship=is_main_package,
            )

        for relationship_dict in doc_dict.get("relationships", []):
            rela = Relationship.from_json_dict(relationship_dict)
            doc.add_relationship(rela)

        return doc
