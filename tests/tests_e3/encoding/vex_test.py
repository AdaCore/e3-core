"""AdaCore product security VEX tests."""

from __future__ import annotations

import json
import pytest
import yaml

from datetime import datetime, timezone
from dateutil.parser import parse as date_parse
from pathlib import Path

from e3.encoding.vex import (
    AuthorRole,
    Document,
    Metadata,
    ProductStatus,
    ActionOrImpact,
    Justification,
    Product,
    ProductId,
    Statement,
    StatementMetadata,
    StatementStatus,
    SubProductId,
    Vulnerability,
)


METADATA_ARGUMENTS = [
    (
        (Metadata.AUTHOR, None, None, Metadata.VERSION, Metadata.SPEC_VERSION, None),
        (
            Metadata.AUTHOR,
            AuthorRole.VENDOR,
            None,
            Metadata.VERSION,
            Metadata.SPEC_VERSION,
            None,
        ),
    ),
    (
        ("me", AuthorRole.OTHER, "My tool", 7, Metadata.SPEC_VERSION, None),
        ("me", AuthorRole.OTHER, "My tool", 7, Metadata.SPEC_VERSION, None),
    ),
    (
        ("me", AuthorRole.OTHER, "My tool", 7, "2.0.0", True),
        (
            "me",
            AuthorRole.OTHER,
            "My tool",
            7,
            Metadata.SPEC_VERSION,
            "2.0.0 is not supported",
        ),
    ),
]

FIRST_TIME: datetime = date_parse("2024-02-06T08:54:10Z")
LAST_TIME: datetime = date_parse("2024-02-06T08:54:11Z")

STATEMENT_METADATA_ARGUMENTS = [
    (("an/id", 8, None, None), ("an/id", 8, None, None)),
    (
        (None, None, FIRST_TIME, LAST_TIME),
        (None, 1, FIRST_TIME, LAST_TIME),
    ),
]

STATEMENT_PRODUCT_DETAILS_ARGUMENTS = [
    (
        (False,),
        (3,),
    ),
    (
        (True,),
        (None,),
    ),
]

STATEMENT_STATUS_PARAMETERS = [
    (
        ProductStatus.UNDER_INVESTIGATION,
        None,
        "Action to take",
        Justification.INLINE_MITIGATIONS_ALREADY_EXIST,
        "notes",
        None,
    ),
    (
        ProductStatus.UNDER_INVESTIGATION,
        "Valid impact",
        "Action to take",
        Justification.INLINE_MITIGATIONS_ALREADY_EXIST,
        "notes",
        None,
    ),
    (
        ProductStatus.NOT_AFFECTED,
        None,
        "Action to take",
        Justification.NO_JUSTIFICATION,
        "notes",
        "either an impact statement or a justification",
    ),
    (
        ProductStatus.NOT_AFFECTED,
        None,
        "Action to take",
        Justification.INLINE_MITIGATIONS_ALREADY_EXIST,
        "notes",
        None,
    ),
    (
        ProductStatus.AFFECTED,
        None,
        None,
        None,
        "notes",
        "an action statement must be provided",
    ),
]

# score, vector, version, source
STATEMENT_VULN_PARAMETERS = [
    (
        5.5,
        "CVSS:3.1/AV:L/AC:L/PR:N/UI:R/S:U/C:N/I:N/A:H",
        "Up to (including) 2.39",
        "nvd@nist.gov",
        "https://nvd.nist.gov/vuln/detail/CVE-2022-38533",
    ),
    (
        None,
        "CVSS:3.1/AV:L/AC:L/PR:N/UI:R/S:U/C:N/I:N/A:H",
        "Up to (including) 2.39",
        "nvd@nist.gov",
        None,
    ),
    (5.5, None, "Up to (including) 2.39", "nvd@nist.gov", None),
    (5.5, "CVSS:3.1/AV:L/AC:L/PR:N/UI:R/S:U/C:N/I:N/A:H", None, "nvd@nist.gov", None),
    (
        5.5,
        "CVSS:3.1/AV:L/AC:L/PR:N/UI:R/S:U/C:N/I:N/A:H",
        "Up to (including) 2.39",
        None,
        "https://nvd.nist.gov/vuln/detail/CVE-2022-38533",
    ),
]

# ---------------------------------------------------------------------------- #
# ----------------------------- Helper functions ----------------------------- #
# ---------------------------------------------------------------------------- #


def create_metadata(
    author: str,
    author_role: AuthorRole | str,
    tooling: str | None,
    version: int,
    spec_version: str | None,
) -> Metadata:
    md: Metadata = Metadata(
        author=author,
        author_role=author_role,
        tooling=tooling,
        version=version,
        spec_version=spec_version,
    )
    return md


def create_product_id(_id: str = "Product ID") -> tuple[str, str, ProductId]:
    version: str = "23.2"
    pid: ProductId = ProductId(_id=_id, version=version)
    return _id, version, pid


def create_sub_product_id(
    _id: str = "Sub Product ID", no_status: bool = False
) -> tuple[str, str, SubProductId]:
    version: str = "23.2"
    spid: SubProductId = SubProductId(
        _id=_id,
        version=version,
        platforms=["a", "b"],
        status=None if no_status else StatementStatus(),
    )
    return _id, version, spid


def create_product(no_subcomps: bool = False) -> Product:
    p1: ProductId = create_product_id(_id="gnat-23.2-x86_64-linux")[-1]
    p2: ProductId = create_product_id(_id="gnat-23.2-x86-linux")[-1]
    subcomponents: list[SubProductId] | None = None
    if not no_subcomps:
        sc1: SubProductId = create_sub_product_id(_id="gprbuild-23.2")[-1]
        sc2: SubProductId = create_sub_product_id(_id="gnatstack-23.2")[-1]
        sc3: SubProductId = create_sub_product_id(
            _id="gnatcoll-core-23.2", no_status=True
        )[-1]
        subcomponents = [sc1, sc2, sc3]
    supplier = "AdaCore"

    pd: Product = Product(
        products=[p1, p2], supplier=supplier, subcomponents=subcomponents
    )
    return pd


def create_statement(
    _id: str | None = None,
    version: int | None = None,
    first: datetime | str | None = None,
    last: datetime | str | None = None,
) -> Statement:
    metadata: StatementMetadata = StatementMetadata(
        _id=_id,
        version=version,
        first_issued_on=first,
        last_updated_on=last,
    )
    product_status: ProductStatus = ProductStatus.UNDER_INVESTIGATION
    no_impact: ActionOrImpact = ActionOrImpact()
    action: ActionOrImpact = ActionOrImpact(statement="Action to take")
    justification: Justification = Justification.INLINE_MITIGATIONS_ALREADY_EXIST
    statement_status: StatementStatus = StatementStatus(
        status=product_status,
        impact=no_impact,
        action=action,
        justification=justification,
        notes="notes",
    )
    vuln: Vulnerability = create_vulnerability()[-1]
    product: Product = create_product()
    statement: Statement = Statement(
        metadata=metadata, status=statement_status, vulnerability=vuln, product=product
    )

    return statement


def create_vulnerability(
    _id: str = "CVE-2022-38533",
    description: str = (
        "In GNU Binutils before 2.40, there is a heap-buffer-overflow in "
        "the error function bfd_getl32 when called from the strip_main "
        "function in strip-new via a crafted file."
    ),
    score: float | None = 5.5,
    vector: str | None = "CVSS:3.1/AV:L/AC:L/PR:N/UI:R/S:U/C:N/I:N/A:H",
    version: str | None = "Up to (including) 2.39",
    source: str | None = "nvd@nist.gov",
    url: str | None = "https://nvd.nist.gov/vuln/detail/CVE-2022-38533",
) -> tuple[str, str, Vulnerability]:
    return (
        _id,
        description,
        Vulnerability(
            _id=_id,
            component="gnu binutils",
            description=description,
            score=score,
            vector=vector,
            version=version,
            source=source,
            url=url,
        ),
    )


# ---------------------------------------------------------------------------- #
# ---------------------------------- Tests ----------------------------------- #
# ---------------------------------------------------------------------------- #

# ------------------------------ Document tests ------------------------------ #


def test_document_author_role_from_value() -> None:
    role: AuthorRole = AuthorRole.from_value(None, AuthorRole.VENDOR)
    assert role == AuthorRole.VENDOR
    role = AuthorRole.from_value(None)
    assert role == AuthorRole.OTHER
    role = AuthorRole.from_value(AuthorRole.COORDINATOR.value)
    assert role == AuthorRole.COORDINATOR
    role = AuthorRole.from_value(AuthorRole.DISCOVERER)
    assert role == AuthorRole.DISCOVERER
    with pytest.raises(ValueError):
        AuthorRole.from_value("Unknown")
    with pytest.raises(ValueError):
        # Give None as default value to cover the infinite loop case. Disable
        # type checker.
        # noinspection PyTypeChecker
        AuthorRole.from_value(None, None)  # type: ignore[arg-type]


@pytest.mark.parametrize("arguments,expected", METADATA_ARGUMENTS)
def test_document(arguments: tuple, expected: tuple) -> None:
    author, author_role, tooling, version, spec_version, exc = arguments
    e_exc = expected[-1]
    if exc is None:
        metadata: Metadata = create_metadata(
            author=author,
            author_role=author_role,
            tooling=tooling,
            version=version,
            spec_version=spec_version,
        )
        st1: Statement = create_statement()
        st2: Statement = create_statement("second/id")
        statements: list[Statement] = [st1, st2]
        doc: Document = Document(
            metadata=metadata,
            statements=statements,
        )

        assert len(doc.statements) == len(statements)
        assert st1 in doc.statements
        assert st2 in doc.statements
        assert doc.metadata == metadata

        # Get an existing statement.

        assert doc.statement(st1.vulnerability._id) == st1
        assert doc.statement("A vuln") is None

        # Copy this using from_dict().

        doc2: Document = Document.from_dict(doc.as_dict())
        assert doc == doc2

        # Create the document without statements, and add them with the
        # add_statement() method.

        doc3: Document = Document(metadata=metadata)
        for statement in st1, st2:
            doc3.add_statement(new_statement=statement)

        assert doc == doc3

        # Save the document to a JSON and YAML file.
        doc4: Document
        out_file: Path

        for output_format in Document.FORMATS:
            out_file = Path.cwd() / output_format / f"vex.{output_format}"
            doc.save(path=out_file, output_format=output_format)
            # Read it, and make sure it returns the same document
            doc4 = Document.from_file(out_file)
            assert doc == doc4

        # Try with an unsupported format.
        out_file: Path = Path.cwd() / "unknown" / "vex.unknown"
        with pytest.raises(ValueError) as format_error:
            doc.save(path=out_file, output_format="unknown")
        assert "Invalid output format" in format_error.value.args[0]

        # Save a document with a "manually" updated timestamp, then reload
        # it. This is to simulate a VEX file updated manually, with a timestamp
        # change.
        timestamps = (
            ("2024/03/03", datetime(2024, 3, 3)),
            ("2024-03-04", datetime(2024, 3, 4)),
            ("5th of March 2024", datetime(2024, 3, 5)),
        )
        for timestamp_str, timestamp_datetime in timestamps:
            dict_repr: dict = doc.as_dict()
            dict_repr["statements"][0]["status"]["impact"]["timestamp"] = timestamp_str
            for output_format in Document.FORMATS:
                out_file = Path.cwd() / output_format / f"vex.{output_format}"
                with out_file.open("w") as f:
                    if output_format == Document.FORMAT_JSON:
                        json.dump(dict_repr, f)
                    else:
                        yaml.dump(
                            dict_repr, f, default_flow_style=False, sort_keys=False
                        )
                # Now re-open it, and simply make sure it does not raise an error.
                doc4 = Document.from_file(out_file)
                assert doc4.statements[0].status.impact.timestamp == timestamp_datetime

    else:
        with pytest.raises(ValueError) as ve:
            create_metadata(
                author=author,
                author_role=author_role,
                tooling=tooling,
                version=version,
                spec_version=spec_version,
            )
        assert e_exc in ve.value.args[0]


@pytest.mark.parametrize("arguments,expected", METADATA_ARGUMENTS)
def test_document_metadata(arguments: tuple, expected: tuple) -> None:
    author, author_role, tooling, version, spec_version, exc = arguments
    e_author, e_author_role, e_tooling, e_version, e_spec_version, e_exc = expected
    if exc is None:
        md = create_metadata(
            author=author,
            author_role=author_role,
            tooling=tooling,
            version=version,
            spec_version=spec_version,
        )
        assert md._id is not None
        assert md.author == e_author
        assert md.author_role == e_author_role
        assert md.created_on == md.last_updated_on
        assert md.tooling == e_tooling
        assert md.version == e_version
        assert md.spec_version == e_spec_version

        md_dict: dict = md.as_dict()
        assert md_dict["_id"] is not None
        assert md_dict["author"] == e_author
        assert md_dict["author_role"] == e_author_role.value
        assert md_dict["created_on"] == md_dict["last_updated_on"]
        assert md_dict["tooling"] == e_tooling
        assert md_dict["version"] == e_version
        assert md_dict["spec_version"] == e_spec_version

        # Test from_dict()

        md2: Metadata = Metadata.from_dict(md_dict)

        assert md == md2
    else:
        with pytest.raises(ValueError) as ve:
            create_metadata(
                author=author,
                author_role=author_role,
                tooling=tooling,
                version=version,
                spec_version=spec_version,
            )
        assert e_exc in ve.value.args[0]


def test_document_status_from_value() -> None:
    status: ProductStatus = ProductStatus.from_value(None, ProductStatus.FIXED)
    assert status == ProductStatus.FIXED
    status = ProductStatus.from_value(None)
    assert status == ProductStatus.UNDER_INVESTIGATION
    status = ProductStatus.from_value(ProductStatus.AFFECTED.value)
    assert status == ProductStatus.AFFECTED
    status = ProductStatus.from_value(ProductStatus.NOT_AFFECTED)
    assert status == ProductStatus.NOT_AFFECTED
    with pytest.raises(ValueError):
        ProductStatus.from_value("Unknown")
    with pytest.raises(ValueError):
        # Give None as default value to cover the infinite loop case. Disable
        # type checker.
        # noinspection PyTypeChecker
        ProductStatus.from_value(None, None)  # type: ignore[arg-type]


# ----------------------------- Statement tests ------------------------------ #


@pytest.mark.parametrize("arguments,expected", STATEMENT_METADATA_ARGUMENTS)
def test_statement(arguments: tuple, expected: tuple) -> None:
    _id, version, first, last = arguments
    statement: Statement = create_statement(_id, version, first, last)
    st2: Statement = Statement.from_dict(statement.as_dict())
    assert statement == st2


def test_statement_action_or_impact() -> None:
    # Check if we could use parametrize here too.
    impact: ActionOrImpact = ActionOrImpact()
    assert not impact
    impact = ActionOrImpact("Impact !")
    assert impact.statement == "Impact !"
    assert impact.timestamp is not None
    impact_timestamp: datetime = datetime.now(timezone.utc)
    impact = ActionOrImpact("Action !", timestamp=impact_timestamp)
    assert impact.statement == "Action !"
    assert impact.timestamp == impact_timestamp.replace(microsecond=0)


def test_statement_justification_from_value() -> None:
    role: Justification = Justification.from_value(
        None, Justification.COMPONENT_NOT_PRESENT
    )
    assert role == Justification.COMPONENT_NOT_PRESENT
    role = Justification.from_value(None)
    assert not role
    role = Justification.from_value(Justification.VULNERABLE_CODE_NOT_PRESENT.value)
    assert role == Justification.VULNERABLE_CODE_NOT_PRESENT
    role = Justification.from_value(Justification.VULNERABLE_CODE_NOT_IN_EXECUTE_PATH)
    assert role == Justification.VULNERABLE_CODE_NOT_IN_EXECUTE_PATH
    with pytest.raises(ValueError):
        Justification.from_value("Unknown")
    with pytest.raises(ValueError):
        # Give None as default value to cover the infinite loop case. Disable
        # type checker.
        # noinspection PyTypeChecker
        Justification.from_value(None, None)  # type: ignore[arg-type]


@pytest.mark.parametrize("arguments,expected", STATEMENT_METADATA_ARGUMENTS)
def test_statement_metadata_init(arguments: tuple, expected: tuple) -> None:
    _id, version, first, last = arguments
    e_id, e_version, e_first, e_last = expected
    metadata: StatementMetadata = StatementMetadata(
        _id=_id,
        version=version,
        first_issued_on=first,
        last_updated_on=last,
    )
    print(json.dumps(metadata.as_dict(), sort_keys=True, indent=2))
    assert metadata._id == e_id
    assert metadata.version == e_version
    if e_first is not None:
        assert metadata.first_issued_on == e_first
    else:
        # Make sure a default time has been assigned.
        assert isinstance(metadata.first_issued_on, datetime)
    if e_last is not None:
        assert metadata.last_updated_on == e_last
    else:
        # Make sure a default time has been assigned.
        assert isinstance(metadata.last_updated_on, datetime)


@pytest.mark.parametrize("arguments,expected", STATEMENT_PRODUCT_DETAILS_ARGUMENTS)
def test_statement_product(arguments: tuple, expected: tuple) -> None:
    (no_subcomps,) = arguments
    (e_subcomps,) = expected
    pd: Product = create_product(no_subcomps=no_subcomps)
    if e_subcomps is not None:
        assert pd.subcomponents
        assert len(pd.subcomponents) == e_subcomps
        for subcomp in pd.subcomponents:
            assert pd.subcomponent(subcomp._id, subcomp.version)

        assert pd.subcomponent("A vuln", "A version") is None
    else:
        assert pd.subcomponents is None
        # Call for the subcomponent() method when there are no subcomponents.
        assert pd.subcomponent(_id="an-id", version="a-version") is None
    pd2: Product = Product.from_dict(pd.as_dict())
    assert pd == pd2


def test_statement_product_id() -> None:
    _id, version, pid = create_product_id()
    assert pid._id == _id
    assert pid.version == version
    pid2: ProductId = ProductId.from_dict(pid.as_dict())
    assert pid == pid2


@pytest.mark.parametrize("arguments", STATEMENT_STATUS_PARAMETERS)
def test_statement_status(arguments: tuple) -> None:
    st, impact, action, justification, notes, exc = arguments

    if exc is None:
        statement_status: StatementStatus = StatementStatus(
            status=st,
            impact=ActionOrImpact(impact),
            action=ActionOrImpact(action),
            justification=justification,
            notes=notes,
        )
        st_status_dict: dict = statement_status.as_dict()
        assert statement_status.status == st
        # Check impact value.
        if not impact:
            assert not statement_status.impact
        else:
            assert (
                statement_status.impact and statement_status.impact.statement == impact
            )
        assert (
            "impact" in st_status_dict
            and st_status_dict["impact"]["statement"] == impact
        )
        # Check action value.
        if not action:
            assert not statement_status.action
        else:
            assert (
                statement_status.action and statement_status.action.statement == action
            )
        assert (
            "action" in st_status_dict
            and st_status_dict["action"]["statement"] == action
        )

        assert statement_status.justification == justification
        assert statement_status.notes == notes

        # Copy that into another statement

        st2: StatementStatus = StatementStatus.from_dict(statement_status.as_dict())
        assert statement_status == st2
    else:
        with pytest.raises(ValueError) as ve:
            StatementStatus(
                status=st,
                impact=ActionOrImpact(impact),
                action=ActionOrImpact(action),
                justification=justification,
                notes=notes,
            )
        assert exc in ve.value.args[0]


@pytest.mark.parametrize("arguments", STATEMENT_VULN_PARAMETERS)
def test_statement_vulnerability(arguments: tuple) -> None:
    score, vector, version, source, url = arguments
    _id, description, vuln = create_vulnerability(
        score=score,
        vector=vector,
        version=version,
        source=source,
        url=url,
    )
    vuln_dict: dict = vuln.as_dict()

    assert vuln._id == _id
    assert vuln_dict["_id"] == _id
    assert vuln.description == description
    assert vuln_dict["description"] == description
    assert vuln.score == score
    if score is not None:
        assert vuln_dict["score"] == score
    else:
        assert "score" not in vuln_dict
    assert vuln.vector == vector
    if vector is not None:
        assert vuln_dict["vector"] == vector
    else:
        assert "vector" not in vuln_dict
    assert vuln.version == version
    if version is not None:
        assert vuln_dict["version"] == version
    else:
        assert "version" not in vuln_dict
    assert vuln.source == source
    if source is not None:
        assert vuln_dict["source"] == source
    else:
        assert "source" not in vuln_dict
    if url is not None:
        assert vuln_dict["url"] == url
    else:
        assert "url" not in vuln_dict

    # Create a vulnerability from another, and check they are equal.

    vuln2: Vulnerability = Vulnerability.from_dict(vuln_dict)
    assert vuln == vuln2
