"""Vulnerabilities Exploitability Exchange specifications.

This specification package is based on
https://www.cisa.gov/sites/default/files/2023-04/minimum-requirements-for-vex-508c.pdf.

The document
https://www.cisa.gov/sites/default/files/2023-01/VEX_Use_Cases_Aprill2022.pdf
has also been used for a better understanding of some VEX implementations.
"""

from __future__ import annotations

import json
import yaml

from datetime import datetime, timezone
from dateutil.parser import parse as date_parse
from enum import Enum
from packaging.version import Version
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

from e3.json import JsonData

if TYPE_CHECKING:
    from typing import Any


class ActionOrImpact(JsonData):
    """An object to represent an action or impact for a statement status.

    For *status* :attr:`Status.NOT_AFFECTED`, if *justification* is not
    provided, then a VEX statement **MUST** provide an *impact_statement* that
    further explains how or why the listed *product_id* s are *not affected* by
    *vul_id*.

    If *justification* is provided, then a VEX statement **MAY** provide an
    *impact_statement*.

    :ivar str | None statement: The statement of this action or impact.
    :ivar datetime | None timestamp: The time at which the statement has
        been last modified.
    """  # noqa RST304

    def __init__(
        self,
        statement: str | None = None,
        timestamp: datetime | None = None,
    ):
        """Initialize an action or impact object.

        :param str | None statement: The action or impact statement. If
            :const:`None`, it means that this object has no impact (or no action).
        :param datetime | None timestamp: The time this action or impact has
            been defined. If :const:`None` and *statement* is defined, the timestamp
            is set to the current time.
        """  # noqa RST304
        self.timestamp: datetime | None
        self.statement: str | None = statement
        if self.statement and not timestamp:
            self.timestamp = datetime.now(timezone.utc).replace(microsecond=0)
        elif isinstance(timestamp, datetime):
            self.timestamp = timestamp.replace(microsecond=0)
        else:
            # Should be None
            self.timestamp = None

    def __bool__(self) -> bool:
        """Check if this action or impact is defined.

        An action or impact without a statement is considered as False.

        :return: **True** if this action or impact has a statement defined to
            something else that :const:`None`, **False** else.
        """  # noqa RST304
        return self.statement is not None

    def as_dict(self) -> dict[str, Any]:
        return {
            "statement": self.statement,
            "timestamp": (
                None
                if self.timestamp is None
                else self.timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")
            ),
        }

    @classmethod
    def from_dict(cls, obj: dict) -> ActionOrImpact:
        return cls(
            statement=obj["statement"],
            timestamp=date_parse(obj["timestamp"]) if obj["timestamp"] else None,
        )


class AuthorRole(Enum):
    """Role of the document author.

    The author role **MAY** specify the role of the *author*.

    The author role **MAY** use the *category of publisher* roles defined by
    CSAF 2.0:

    :cvar COORDINATOR: indicates individuals or organizations that manage a
        single vendor’s response or multiple vendors’ responses to a
        vulnerability, a security flaw, or an incident. This includes all
        Computer Emergency/Incident Response Teams (CERTs/CIRTs) or agents
        acting on the behalf of a researcher.
    :cvar DISCOVERER: indicates individuals or organizations that find
        vulnerabilities or security weaknesses. This includes all manner of
        researchers.
    :cvar TRANSLATOR: indicates individuals or organizations that translate
        VEX documents. This includes all manner of language translators, also
        those who work for the party issuing the original advisory.
    :cvar OTHER: indicates a catchall for everyone else. Currently, this
        includes editors, reviewers, forwarders, republishers, and miscellaneous
        contributors.
    :cvar USER: indicates anyone using a vendor’s product.
    :cvar VENDOR: indicates developers or maintainers of information system
        products or services. This includes all authoritative product vendors,
        Product Security Incident Response Teams (PSIRTs), and product resellers
        and distributors, including authoritative vendor partners.
    """

    COORDINATOR = "coordinator"
    DISCOVERER = "discoverer"
    OTHER = "other"
    TRANSLATOR = "translator"
    USER = "user"
    VENDOR = "vendor"

    @classmethod
    def from_value(
        cls, value: str | AuthorRole | None, default: AuthorRole | str = OTHER
    ) -> AuthorRole:
        """Create an author role enum from a given *value*.

        :return: An author role enum set according to *value* and *default*.

        :raise: :exc:`python:ValueError` If *value* is not one of the possible
            values of this enumerate, or if *default* has an invalid value
            **and** *value* is :const:`None`.
        """  # noqa RST304
        if isinstance(value, str) and value:
            return cls(value)
        elif isinstance(value, cls):
            return value
        elif default:
            # The default value is either an AuthorRole or a string, better
            # return a AuthorRole.
            return cls.from_value(default)
        else:
            raise ValueError(f"Invalid default value {default}")


class Document(JsonData):
    """Vulnerabilities Exploitability Exchange document.

    A VEX document is a binding of product information, vulnerability
    information, and the relevant status details relating them.

    Minimum data elements of a VEX document must include the VEX metadata,
    product details, vulnerability details, and product status.

    :ivar Metadata metadata: VEX metadata.
    :ivar list[Statement] statements: The list of statements defined for
        this VEX document.
    """

    FORMAT_JSON: str = "json"
    FORMAT_YAML: str = "yaml"
    FORMATS: tuple = (FORMAT_JSON, FORMAT_YAML)

    def __init__(
        self,
        metadata: Metadata,
        statements: list[Statement] | None = None,
    ):
        """Initialize a VEX document object.

        :param metadata: The metadata defining this VEX document.
        :param statements: The VEX statements statement for this document.
        """
        self.metadata: Metadata = metadata
        # Use add_statement() to update the statements ID if needed.
        self.statements: list[Statement] = []
        if statements is not None:
            for st in statements:
                self.add_statement(st)

    def add_statement(self, new_statement: Statement) -> None:
        """Add a new statement to this VEX document.

        If *statement* has an *_id* set to :const:`None`, the value of the statement
        *_id* is updated to ``<document id>/<statement vuln id>``.

        :param new_statement: The statement to add to this VEX document.
        """  # noqa RST304
        # Check if the statement has an ID. If not, add the statement's
        # vulnerability ID to the document's ID.
        # noinspection PyProtectedMember
        if new_statement.metadata._id is None:
            # noinspection PyProtectedMember
            new_statement.metadata._id = (
                f"{self.metadata._id}/{new_statement.vulnerability._id}"
            )
            # Update the last modification date ?
        self.statements.append(new_statement)

    def as_dict(self) -> dict[str, Any]:
        return {
            "metadata": self.metadata.as_dict(),
            "statements": [st.as_dict() for st in self.statements],
        }

    @classmethod
    def from_dict(cls, obj: dict) -> Document:
        return cls(
            metadata=Metadata.from_dict(obj["metadata"]),
            statements=[Statement.from_dict(s) for s in obj["statements"]],
        )

    @classmethod
    def from_file(cls, path: Path) -> Document:
        """Create a VEX document from a file content.

        The function :func:`yaml.safe_load()` is used to read the file. If the
        file content is JSON, the YAML loader handles it safely and extracts
        data anyway.

        :param path: The path of a VEX document to initialise this document
            with.
        """  # noqa RST304
        with path.open() as f:
            vex_dict: dict = yaml.safe_load(f)

        return cls.from_dict(vex_dict)

    def save(self, path: Path, output_format: str = FORMAT_JSON) -> None:
        """Save this document to a file with the given format.

        :param path: The path of the saved file.
        :param output_format: The file format. May be any of :attr:`FORMATS`.

        :raise: :exc:`python:ValueError` If *output_format* is not one of the
            possible :attr:`FORMATS`.
        """  # noqa RST304
        if output_format not in self.FORMATS:
            raise ValueError(
                f"Invalid output format {output_format}. Accepted output "
                f"formats are: {', '.join(self.FORMATS)}"
            )

        path.parent.mkdir(exist_ok=True, parents=True)
        with path.open("w") as f:
            if output_format == self.FORMAT_JSON:
                json.dump(self.as_dict(), f)
            else:
                yaml.dump(self.as_dict(), f, default_flow_style=False, sort_keys=False)

    def statement(self, cve_id: str) -> Statement | None:
        """Get the statement for given CVE ID.

        If this document does not contain any statement defining a vulnerability
        which ID is *cve_id*, :const:`None` is returned.

        :param cve_id: The ID of the CVE to retrieve in the statements of this
            document.

        :return: A :class:`Statement` object which defines the vulnerability
            *cve_id*, or :const:`None` if such a statement does not exist in this
            document.
        """  # noqa RST304
        for statement in self.statements:
            # noinspection PyProtectedMember
            if statement.vulnerability and statement.vulnerability._id == cve_id:
                return statement
        return None


class Justification(Enum):
    """Justification for a statement status.

    For *status* :attr:`Status.NOT_AFFECTED`, a VEX statement **SHOULD** provide
    *justification*.

    If *justification* is not provided then *impact_statement* **MUST** be
    provided.

    :cvar str COMPONENT_NOT_PRESENT: The vulnerable *subcomponent_id* is not
        included in *product_id*.
    :cvar str INLINE_MITIGATIONS_ALREADY_EXIST: *product_id* includes built-in
        protections or features that prevent exploitation of the vulnerability.
        These built-in protections cannot be subverted by the attacker and
        cannot be configured or disabled by the user. These mitigations
        completely prevent exploitation based on known attack vectors.
    :cvar str NO_JUSTIFICATION: Use to state that there is no justification set
        yet.
    :cvar str VULNERABLE_CODE_CANNOT_BE_CONTROLLED_BY_ADVERSARY: The vulnerable
        code is present and used by *product_id* but cannot be controlled by an
        attacker to exploit the vulnerability.
    :cvar str VULNERABLE_CODE_NOT_IN_EXECUTE_PATH: The vulnerable code (likely
        in *subcomponent_id*) cannot be executed due to the way it is used
        by *product_id*. Typically, this case occurs when *product_id* includes
        the vulnerable code but does not call or otherwise use it.
    :cvar str VULNERABLE_CODE_NOT_PRESENT: The vulnerable *subcomponent_id* is
        included in *product_id* but the vulnerable code is not present.
        Typically, this case occurs when source code is configured or built in
        a way that excludes the vulnerable code.
    """  # noqa RST304

    COMPONENT_NOT_PRESENT = "Component not present"
    INLINE_MITIGATIONS_ALREADY_EXIST = "Inline mitigations already exist"
    VULNERABLE_CODE_CANNOT_BE_CONTROLLED_BY_ADVERSARY = (
        "Vulnerable code cannot be controlled by adversary"
    )
    VULNERABLE_CODE_NOT_IN_EXECUTE_PATH = "Vulnerable code not in execute path"
    VULNERABLE_CODE_NOT_PRESENT = "Vulnerable code not present"

    NO_JUSTIFICATION = "No justification"

    def __bool__(self) -> bool:
        """Check if this justification is defined.

        :return: **False** only if justification is set to
            :attr:`Justification.NO_JUSTIFICATION`, else **True** is returned.
        """  # noqa RST304
        return self != Justification.NO_JUSTIFICATION

    @classmethod
    def from_value(
        cls,
        value: str | Justification | None,
        default: Justification | str = NO_JUSTIFICATION,
    ) -> Justification:
        """Create a justification enum from a given *value*.

        :return: A justification enum set according to *value* and *default*.

        :raise: :exc:`python:ValueError` If *value* is not one of the possible
            values of this enumerate, or if *default* has an invalid value
            **and** *value* is :const:`None`.
        """  # noqa RST304
        if isinstance(value, str) and value:
            return cls(value)
        elif isinstance(value, cls):
            return value
        elif default:
            # The default value is either a Justification object or a string,
            # better return a Justification.
            return cls.from_value(default)
        else:
            raise ValueError(f"Invalid default value {default}")


class Metadata(JsonData):
    """VEX metadata.

    To the greatest extent possible, VEX metadata is defined and maintained at
    the VEX document level.

    When appropriate and necessary, VEX metadata is defined at the VEX statement
    level.

    VEX document metadata **MAY** be synthesized or derived from VEX statement
    metadata; for example, *doc_time_last_updated* **MUST** be at least as
    recent as the newest *statement_time_last_updated*.

    VEX document metadata **MUST** accurately apply to all contained VEX
    statements.

    Must include: VEX Format Identifier, Identifier string for the VEX
    document, Author, Author role, Timestamp.

    :ivar str author: The author of the VEX document. The *author* is
        responsible for the content of the VEX document. A VEX document **MUST**
        identify the author. To describe tools or other mechanisms used to
        generate VEX content, consider *tooling*.
    :ivar AuthorRole author_role: The role of the other of this document. See
        :class:`AuthorRole`.
    :ivar str | None tooling: Document tooling **MAY** specify tools or
        automated mechanisms that generate VEX documents, VEX statements, or
        other VEX information. Contrast with *author*.
    :ivar int version: The version of a VEX document.
    :ivar str _id: The ID of a VEX document.
    :ivar datetime created_on: The time this VEX document was created at.
    :ivar datetime last_updated_on: The time this VEX document was updated.
    :ivar str spec_version: The VEX requirements version used by the parent
        document. By default, it is set to :attr:`SPEC_VERSION`.
    """  # noqa RST304

    AUTHOR: str = "AdaCore"
    AUTHOR_ROLE: AuthorRole = AuthorRole.VENDOR
    SPEC_VERSION: str = "1.0.0"
    VERSION: int = 1

    def __init__(
        self,
        author: str = AUTHOR,
        author_role: AuthorRole | str = AUTHOR_ROLE,
        tooling: str | None = None,
        version: int = VERSION,
        _id: str | None = None,
        created_on: datetime | None = None,
        last_updated_on: datetime | None = None,
        spec_version: str = SPEC_VERSION,
    ):
        """Initialize a VEX specification metadata.

        :param author: The author of this VEX document.
        :param author_role: The author role. See :class:`AuthorRole`.
        :param tooling: Automated tools used to create this VEX document (if
            any).
        :param version: Version of this VEX document.
        :param _id: The ID of this document. If not set, a new ID is generated,
            and set to `f"{author}/{uuid4()}"`.
        :param created_on: The date this VEX document was created on. If not
            set, use the current time.
        :param last_updated_on: The date this VEX document was last updated on.
            If not set, use the current time.
        :param spec_version: The specification version used to build this VEX
            document.
        """  # noqa RST304
        self.author: str = author
        self.author_role: AuthorRole = AuthorRole.from_value(
            author_role, self.AUTHOR_ROLE
        )
        self.tooling: str | None = tooling
        self.version: int = version

        # Generated attributes.
        self._id: str = _id if _id is not None else f"{self.author}/{uuid4()}"
        self.created_on: datetime = (
            datetime.now(timezone.utc).replace(microsecond=0)
            if created_on is None
            else created_on
        )
        self.last_updated_on: datetime = (
            datetime.now(timezone.utc).replace(microsecond=0)
            if last_updated_on is None
            else last_updated_on
        )

        # If a spec_version different from SPEC_VERSION is used, make sure it
        # is smaller than our own version (hoping it is backward compatible).
        if Version(spec_version) > Version(Metadata.SPEC_VERSION):
            raise ValueError(
                "VEX specification version currently supported is "
                f"{self.SPEC_VERSION}. The specification version "
                f"{spec_version} is not supported."
            )
        else:
            self.spec_version = spec_version

    def as_dict(self) -> dict[str, Any]:
        return {
            "_id": self._id,
            "version": self.version,
            "author": self.author,
            "author_role": self.author_role.value,
            "tooling": self.tooling,
            "created_on": self.created_on.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "last_updated_on": self.last_updated_on.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "spec_version": self.spec_version,
        }

    @classmethod
    def from_dict(cls, obj: dict) -> Metadata:
        return cls(
            _id=obj["_id"],
            author=obj["author"],
            author_role=obj["author_role"],
            tooling=obj["tooling"],
            version=obj["version"],
            created_on=(date_parse(obj["created_on"]) if obj["created_on"] else None),
            last_updated_on=(
                date_parse(obj["last_updated_on"]) if obj["last_updated_on"] else None
            ),
            spec_version=obj["spec_version"],
        )


class Product(JsonData):
    """Product details.

    :ivar list[ProductID] products: Product details **MUST** include one or more
        *product_id* and **MAY** include one or more *subcomponent_id*.
    :ivar str supplier: Product details **SHOULD** identify the *supplier* of
        *product_id* or *subcomponent_id*. *supplier* **MUST** clearly indicate
        the *product_id* or *subcomponent_id* to which *supplier* applies. For
        example:

        - [supplier]/[product_id]
        - [supplier]/[subcomponent_id]

    :ivar list[ProductId] | None subcomponents: A VEX statement **MAY** include
        one or more identifiers for subcomponents associated with vulnerability
        details.

        A VEX statement asserts the *status* of *product_id* with respect to
        *vul_id*. A VEX statement **MAY** also convey that *subcomponent_id* is
        included in *product_id*. A common VEX use case is to convey that
        *subcomponent_id* is **affected** by *vul_id* while *product_id* is
        **not_affected** by *vul_id*.

        *subcomponent_id* **MAY** be derived from *product_id*, particularly if
        *product_id* is associated with SBOM or other references that convey
        dependencies.

        *subcomponent_id* **MAY** be derived from *vul_id* or *vul_description*.
    """

    def __init__(
        self,
        products: list[ProductId],
        supplier: str,
        subcomponents: list[SubProductId] | None = None,
    ):
        """Initialize a product object.

        :param products: The list of product IDs defined by this product.
        :param supplier: The product supplier name.
        :param subcomponents: The list of subcomponents defined for the given
            product IDs.
        """
        self.products: list[ProductId] = products
        self.subcomponents: list[SubProductId] | None = subcomponents
        self.supplier: str = supplier

    def as_dict(self) -> dict[str, Any]:
        dict_representation: dict = {
            "supplier": self.supplier,
            "products": [product.as_dict() for product in self.products],
        }
        if self.subcomponents:
            dict_representation.update(
                {
                    "subcomponents": [
                        subcomponent.as_dict() for subcomponent in self.subcomponents
                    ]
                }
            )

        return dict_representation

    @classmethod
    def from_dict(cls, obj: dict) -> Product:
        return cls(
            products=[ProductId.from_dict(product) for product in obj["products"]],
            supplier=obj["supplier"],
            subcomponents=(
                [SubProductId.from_dict(sc) for sc in obj["subcomponents"]]
                if "subcomponents" in obj and obj["subcomponents"]
                else None
            ),
        )

    def subcomponent(self, _id: str, version: str) -> SubProductId | None:
        """Get a subcomponent with given ID if any.

        :param _id: The ID of the subcomponent to look for.
        :param version: The version of the subcomponent to look for.

        :return: A matching subcomponent ID, or :const:`None` if no such subcomponent
            could be found.
        """  # noqa RST304
        if self.subcomponents is not None:
            for subcomponent in self.subcomponents:
                # noinspection PyProtectedMember
                if subcomponent._id == _id and subcomponent.version == version:
                    return subcomponent
        return None


class ProductId(JsonData):
    """VEX statement product identifier.

    The specifications say:

        *product_id* **MUST** identify the product or component that *vul_id*
        and *status* applies to.

        *product_id* **MAY** specify a set of products or components and
        **MUST** specify at least one of:

        - *subcomponent_id*
        - A component (often a subcomponent of a product)
        - A product, for example, a final good assembled
        - A set of products or components, for example, a product line or family
        - A supplier (indicating the set of all products or components from the
          supplier)

    :ivar str _id: The ID of the product.
    :ivar str version: Version, or version range of the product.
    """

    def __init__(
        self,
        _id: str,
        version: str,
    ):
        """Initialize this product ID object.

        :param _id: The ID defining this product.
        :param version: The version of this product.
        """
        self._id = _id
        self.version = version

    def as_dict(self) -> dict[str, Any]:
        dict_representation: dict = {
            "_id": self._id,
            "version": self.version,
        }
        return dict_representation


class ProductStatus(Enum):
    """Status information about a vulnerability in that product.

    :cvar NOT_AFFECTED: No remediation is required regarding this vulnerability.
    :cvar AFFECTED: Actions are recommended to remediate or address this
        vulnerability.
    :cvar FIXED: These product versions contain a fix for the vulnerability.
    :cvar UNDER_INVESTIGATION: It is not yet known whether these product
        versions are affected by the vulnerability. An update will be provided
        in a later release.
    """

    NOT_AFFECTED = "Not affected"
    AFFECTED = "Affected"
    FIXED = "Fixed"
    UNDER_INVESTIGATION = "Under investigation"

    @classmethod
    def from_value(
        cls,
        value: str | ProductStatus | None,
        default: ProductStatus | str = UNDER_INVESTIGATION,
    ) -> ProductStatus:
        """Create a product status enum from a given *value*.

        :return: A product status enum set according to *value* and *default*.

        :raise: :exc:`python:ValueError` If *value* is not one of the possible
            values of this enumerate, or if *default* has an invalid value
            **and** *value* is :const:`None`.
        """  # noqa RST304
        if isinstance(value, str) and value:
            return cls(value)
        elif isinstance(value, cls):
            return value
        elif default:
            # The default value is either a Product status or a string, better
            # return a ProductStatus.
            return cls.from_value(default)
        else:
            raise ValueError(f"Invalid default value {default}")


class Statement(JsonData):
    """VEX statement.

    A VEX statement is a declaration that **MUST** convey a single *status* that
    applies to a single *vul_id* for one or more *product_id* s.

    A VEX statement **MUST** be logically contained within a VEX document.

    A VEX statement **MUST** exist only within one VEX document, that is, VEX
    statements are logically local to their containing VEX document.

    :ivar Metadata metadata: The metadata defining this VEX statement.
    :ivar Status status: The status of this VEX statement.
    :ivar Vulnerability vulnerability: The details of the unique vulnerability
        defined for this VEX statement.
    :ivar Product product: The details of the products for the given
        vulnerability of this VEX statement.
    """

    def __init__(
        self,
        metadata: StatementMetadata,
        status: StatementStatus,
        vulnerability: Vulnerability,
        product: Product,
    ):
        """Initialize a VEX document statement object.

        :param metadata: The metadata of this statement.
        :param status: The current status of this statement.
        :param vulnerability: The description of the vulnerability defined by
            this statement.
        :param product: The product affected by this statement.
        """
        self.metadata: StatementMetadata = metadata
        self.status: StatementStatus = status
        self.vulnerability: Vulnerability = vulnerability
        self.product: Product = product

    def as_dict(self) -> dict[str, Any]:
        return {
            "metadata": self.metadata.as_dict(),
            "vulnerability": self.vulnerability.as_dict(),
            "status": self.status.as_dict(),
            "product": self.product.as_dict(),
        }

    @classmethod
    def from_dict(cls, obj: dict) -> Statement:
        return cls(
            metadata=StatementMetadata.from_dict(obj["metadata"]),
            status=StatementStatus.from_dict(obj["status"]),
            vulnerability=Vulnerability.from_dict(obj["vulnerability"]),
            product=Product.from_dict(obj["product"]),
        )


class StatementMetadata(JsonData):
    """Metadata for a VEX statement.

    To the extent possible, VEX metadata is stored in VEX documents. Certain
    metadata is specific to VEX statements.

    :ivar int version: indicates the version of the VEX statement.

        - A VEX statement **MUST** provide one *version*.
        - *version* **MUST** clearly convey positive incremental change.
        - *version* MUST be incremented when any content within the VEX
          statement changes.
        - *version* **MAY** be derived from or otherwise be related to
          *document_version*.
    :ivar str | None _id: *_id* uniquely identifies a VEX statement within a VEX
        document.

        - A VEX statement **MUST** be able to be specifically referenced within
          a VEX document.
        - A VEX statement **SHOULD** provide one *_id*.
        - *_id* **SHOULD** be created within the *author* and *doc_id*
          namespaces and **MAY** be generated from other VEX information, for
          example, ``author/doc_id/statement_id``.
        - *_id* **MAY** minimally be an index of VEX statements within the scope
          of *doc_id*.
    :ivar datetime first_issued_on: A VEX statement **MUST** provide the date
        and time that the VEX statement was first issued.

        - *first_issued_on* **MAY** be derived from or otherwise related to
          *doc_time_first_issued*.
        - *first_issued_on* **MAY** be derived from or otherwise related to
          *impact_statement_time* or *action_statement_time*.
    :ivar datetime last_updated_on: A VEX statement **MUST** provide the date
        and time that the VEX statement was last modified.

        - *last_updated_on* **MUST** initially be equivalent to
          *first_issued_on*.
        - *last_updated_on* **MAY** be derived from or otherwise related to
          *impact_statement_time* or *action_statement_time*.
        - *last_updated_on* **MUST** be equivalent to or newer than the most
          recent *impact_statement_time* or *action_statement_time*.
    """

    def __init__(
        self,
        version: int | None = None,
        _id: str | None = None,
        first_issued_on: datetime | None = None,
        last_updated_on: datetime | None = None,
    ):
        """Initialize a statement metadata object.

        :param version: The version of this statement.
        :param _id: The ID of this VEX metadata statement. It may be set to
            :const:`None` to be set later on, according to the document metadata.
        :param first_issued_on: The time this statement was first issued. If
            :const:`None`, current time is used.
        :param last_updated_on: The time this statement was last updated. If
            :const:`None`, current time is used.
        """  # noqa RST304
        self._id: str | None = _id
        self.version: int = version if isinstance(version, int) else 1
        self.first_issued_on: datetime = (
            datetime.now(timezone.utc).replace(microsecond=0)
            if first_issued_on is None
            else first_issued_on
        )
        self.last_updated_on: datetime = (
            datetime.now(timezone.utc).replace(microsecond=0)
            if last_updated_on is None
            else last_updated_on
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "_id": self._id,
            "version": self.version,
            "first_issued_on": self.first_issued_on.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "last_updated_on": self.last_updated_on.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }

    @classmethod
    def from_dict(cls, obj: dict) -> StatementMetadata:
        return cls(
            _id=obj["_id"],
            version=obj["version"],
            first_issued_on=(
                date_parse(obj["first_issued_on"]) if obj["first_issued_on"] else None
            ),
            last_updated_on=(
                date_parse(obj["last_updated_on"]) if obj["last_updated_on"] else None
            ),
        )


class StatementStatus(JsonData):
    """Statement status.

    A VEX statement **MUST** provide one *status* that applies to all contained
    *product_id* s with respect to *vul_id*.

    The statement status is made of a product status (not affected,fixed ...),
    and *impact* depending on the *status* and *justification*.

    For **affected* products, an *action* **MUST** be defined which **SHOULD**
    describe actions to remediate or mitigate *vul_id*.

    :ivar ProductStatus status: The current status of this statement.
    :ivar ActionOrImpact impact: For *status*
        :attr:`ProductStatus.NOT_AFFECTED`, if *justification* is not provided,
        then a VEX statement **MUST** provide an *impact statement*  that
        further explains how or why the listed product ids are
        :attr:`ProductStatus.NOT_AFFECTED` by given vulnerability.

        If *justification* is provided, then a VEX statement **MAY** provide an
        *impact statement*.

        An *impact statement* **MAY** include an *impact statement* time, recording
        when the *impact statement* was issued.
    :ivar Justification justification: Justification for the current *status*.
    :ivar ActionOrImpact action: For *status* :attr:`ProductStatus.AFFECTED`, a
        VEX statement **MUST** include one *action statement* that **SHOULD**
        describe actions to remediate or mitigate given vulnerability.

        An *action statement* **MAY** include *action statement time* recording
        when the *action statement* was issued.
    :ivar str | None notes: Status notes **MAY** convey information about how
        *status* was determined and **MAY** reference other VEX information.
    """  # noqa RST304

    def __init__(
        self,
        status: ProductStatus | str | None = ProductStatus.UNDER_INVESTIGATION,
        impact: ActionOrImpact | None = None,
        justification: Justification | str | None = Justification.NO_JUSTIFICATION,
        action: ActionOrImpact | None = None,
        notes: str | None = None,
    ):
        """Initialize a statement status.

        :param status: The product status with regard to the current statement.
        :param impact: The impact (if any) of the current statement on given
            product.
        :param justification: The justification of the impact or action.
        :param action: The action to take if any.
        :param notes: Notes for this statement status (if any).
        """
        self.action_statement_time: datetime

        self.status: ProductStatus = ProductStatus.from_value(status)
        self.impact: ActionOrImpact = impact if impact is not None else ActionOrImpact()
        self.action: ActionOrImpact = action if action is not None else ActionOrImpact()
        self.justification: Justification = Justification.from_value(justification)
        self.notes: str | None = notes

        # Check values consistency.

        if status == ProductStatus.UNDER_INVESTIGATION:
            # No checks to perform.
            pass
        elif self.status == ProductStatus.NOT_AFFECTED:
            if not self.justification and not self.impact:
                raise ValueError(
                    f"When status is {self.status.value}, either an impact "
                    "statement or a justification must be provided."
                )
        elif self.status == ProductStatus.AFFECTED and not self.action:
            raise ValueError(
                f"When status is {self.status.value}, an action statement "
                "must be provided."
            )

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "justification": self.justification.value,
            "impact": self.impact.as_dict(),
            "action": self.action.as_dict(),
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, obj: dict) -> StatementStatus:
        return cls(
            status=obj["status"],
            impact=ActionOrImpact.from_dict(obj["impact"]) if "impact" in obj else None,
            justification=obj["justification"],
            action=ActionOrImpact.from_dict(obj["action"]) if "action" in obj else None,
            notes=obj["notes"] if "notes" in obj else None,
        )


class SubProductId(ProductId):
    """Sub-product ID.

    :ivar str _id: see :class:`ProductId`
    :ivar str version: see :class:`ProductId`
    :ivar list[str] platforms: The list of platform for this sub-product ID.
    :ivar StatementStatus status: The status of the sub product.
    """  # noqa RST304

    def __init__(
        self,
        _id: str,
        version: str,
        platforms: list[str],
        status: StatementStatus | None,
    ):
        """Initialize a Sub-product ID.

        :ivar str _id: see :class:`ProductId`
        :ivar str version: see :class:`ProductId`
        :ivar list[str] platforms: The list of platform for this sub-product ID.
        :ivar StatementStatus | None status: The status of the sub product. If
            :const:`None`, the status of the parent statement is assumed.
        """  # noqa RST304
        super().__init__(_id=_id, version=version)
        self.platforms: list[str] = platforms or []
        self.status: StatementStatus | None = status

    def as_dict(self) -> dict[str, Any]:
        dict_repr: dict = super().as_dict()
        dict_repr.update(
            {
                "platforms": self.platforms,
            }
        )
        if self.status is not None:
            dict_repr.update(
                {
                    "status": self.status.as_dict(),
                }
            )
        return dict_repr

    @classmethod
    def from_dict(cls, obj: dict) -> SubProductId:
        return cls(
            _id=obj["_id"],
            version=obj["version"],
            platforms=obj["platforms"],
            status=(
                StatementStatus.from_dict(obj["status"]) if "status" in obj else None
            ),
        )


class Vulnerability(JsonData):
    """Statement vulnerability details.

    Vulnerability details identify and provide information about the
    vulnerability in a VEX statement.

    :ivar str _id: Identifies the vulnerability in a VEX statement.

        - A VEX statement **MUST** specify one *_id*.
        - *_id* **SHOULD** use existing, readily available, and well-known
          identifiers such as: CVE, the Global Security Database (GSD), or a
          supplier’s vulnerability identification system. It is expected that
          vulnerability identification systems are external to and maintained
          separately from VEX.
        - *_id* **MAY** be URIs or URLs.
        - *_id* **MAY** be arbitrary and **MAY** be created by the *author*.
    :ivar str description: A VEX statement **MUST** include or reference one
        *description* that corresponds to *_id*.

        *description* **MUST** either be included in the VEX statement or made
        available to VEX consumers (for example, through a URL).
    :ivar str component: The name of the component this vulnerability applies to.
    :ivar float | None score: The base score for this vulnerability as defined
        by https://nvd.nist.gov/vuln-metrics/cvss/v3-calculator and the CVE
        vector. Set to :const:`None` if there is no such computed metric for this
        vulnerability.
    :ivar str | None vector: The CVE score vector are defined by
        https://nvd.nist.gov/vuln-metrics/cvss/v3-calculator. Set to :const:`None` if
        no such vector is defined.
    :ivar str | None version: The version(s) of *component* for which this
        vulnerability is defined.
    :ivar str | None source: The emitter of the above *score* and *vector* if
        any.
    :ivar str | None url: An url to get details on this vulnerability.
    """  # noqa RST304

    def __init__(
        self,
        _id: str,
        component: str,
        description: str,
        score: float | None = None,
        vector: str | None = None,
        version: str | None = None,
        source: str | None = None,
        url: str | None = None,
    ):
        """Initialize a VEX vulnerability object.

        :param _id: The vulnerability ID.
        :param component: The component the vulnerability id defined for. For
            instance, it may be `zlib` for vulnerability `CVE-2023-45853`.
        :param description: The description of the vulnerability as defined by
            the various CVE databases (MITRE, NVD ...).
        :param score: The base score of the vulnerability as defined by the
            CVSS calculator.
        :param vector: The vulnerability CVSS score vector.
        :param version: The version(s) of *component* for which this
            vulnerability is defined.
        :param source: The emitter of the above *score* and *vector* if any.
        :param url: An url to get details on this vulnerability.
        """
        self._id: str = _id
        self.component: str = component
        self.description: str = description
        self.score: float | None = score
        self.vector: str | None = vector
        self.version: str | None = version
        self.source: str | None = source
        self.url: str | None = url

    def as_dict(self) -> dict[str, Any]:
        dict_repr: dict = {
            "_id": self._id,
            "component": self.component,
        }
        if self.version is not None:
            dict_repr["version"] = self.version
        dict_repr["description"] = self.description
        if self.url is not None:
            dict_repr["url"] = self.url
        if self.source is not None:
            dict_repr["source"] = self.source
        if self.score is not None:
            dict_repr["score"] = self.score
        if self.vector is not None:
            dict_repr["vector"] = self.vector

        return dict_repr
