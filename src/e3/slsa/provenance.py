"""SLSA provenance package.

Implementing https://slsa.dev/spec/v1.0/provenance.

Purpose
=======
Describe how an artifact or set of artifacts was produced so that:

- Consumers of the provenance can verify that the artifact was built according
  to expectations.
- Others can rebuild the artifact, if desired.

This predicate is the *RECOMMENDED* way to satisfy the
`SLSA v1.0 provenance requirements
<https://slsa.dev/spec/v1.0/requirements#provenance-generation>`_.

.. _SLSA: https://slsa.dev

.. |ResourceDescriptor| replace:: :class:`ResourceDescriptor`
.. |ResourceURI| replace:: :class:`ResourceURI`
.. |SLSA| replace:: `SLSA`_
.. |bool| replace:: :class:`bool`
.. |bytes| replace:: :class:`bytes`
.. |datetime| replace:: :class:`~datetime.datetime`
.. |dict| replace:: :class:`dict`
.. |json.dumps| replace:: :func:`json.dumps()`
.. |json.load| replace:: :func:`json.load()`
.. |str| replace:: :class:`str`
"""  # noqa RST304

from __future__ import annotations

import base64
import json
import hashlib

from datetime import datetime, timezone
from dateutil import parser as date_parser
from pathlib import Path
from typing import Any


class Builder(object):
    """Predicate run details builder object.

    The build platform, or builder for short, represents the transitive closure
    of all the entities that are, by necessity,
    `trusted <https://slsa.dev/spec/v1.0/principles#trust-systems-verify-artifacts>`_
    to faithfully run the build and record the provenance.

    This includes not only the software but the hardware and people involved in
    running the service.

    For example, a particular instance of `Tekton <https://tekton.dev/>`_ could
    be a build platform, while Tekton itself is not. For more info, see
    `Build model <https://slsa.dev/spec/v1.0/terminology#build-model>`_.

    The |id| **MUST** reflect the trust base that consumers care about. How
    detailed to be is a judgement call. For example, GitHub Actions supports
    both GitHub-hosted runners and self-hosted runners. The GitHub-hosted runner
    might be a single identity because it’s all GitHub from the consumer’s
    perspective. Meanwhile, each self-hosted runner might have its own identity
    because not all runners are trusted by all consumers.

    Consumers MUST accept only specific signer-builder pairs. For example,
    ``GitHub`` can sign provenance for the ``GitHub Actions`` builder, and
    ``Google`` can sign provenance for the ``Google Cloud Build`` builder, but
    ``GitHub`` cannot sign for the ``Google Cloud Build`` builder.

    Design rationale
    ----------------
    The builder is distinct from the signer in order to support the case where
    one signer generates attestations for more than one builder, as in the
    ``GitHub Actions`` example above. The field is **REQUIRED**, even if it is
    implicit from the signer, to aid readability and debugging.

    It is an object to allow additional fields in the future, in case one URI is
    not sufficient.

    .. |builder.as_dict| replace:: :meth:`~Builder.as_dict`
    .. |builder.as_json| replace:: :meth:`~Builder.as_json`
    .. |id| replace:: :attr:`~Builder.id`
    .. |builder.load_dict| replace:: :meth:`~Builder.load_dict`
    .. |builder.load_json| replace:: :meth:`~Builder.load_json`
    """  # noqa RST304

    ATTR_BUILD_ID: str = "id"
    ATTR_BUILDER_DEPENDENCIES: str = "builderDependencies"
    ATTR_VERSION: str = "version"

    def __init__(
        self,
        build_id: TypeURI | str,
        builder_dependencies: list[ResourceDescriptor],
        version: dict[str, str],
    ) -> None:
        self.__id: TypeURI = (
            build_id if isinstance(build_id, TypeURI) else TypeURI(build_id)
        )
        self.__dependencies: list[ResourceDescriptor] = builder_dependencies
        self.__version: dict[str, str] = version

    def __eq__(self, other: object) -> bool:
        """Check if this builder object is equal to *other*.

        :param other: The builder object to compare this with.

        :return: A |bool| set to **True** if both builders are equal, **False**
            else.
        """  # noqa RST304
        if isinstance(other, self.__class__):
            return self.as_json() == other.as_json()
        return False

    @property
    def builder_dependencies(self) -> list[ResourceDescriptor]:
        """Builder dependencies.

        Dependencies used by the orchestrator that are not run within the
        workload and that do not affect the build, but might affect the
        provenance generation or security guarantees.
        """
        return self.__dependencies

    @property
    def id(self) -> TypeURI:
        """Build platform ID.

        URI indicating the transitive closure of the trusted build platform.
        This is intended to be the sole determiner of the SLSA Build level.

        If a build platform has multiple modes of operations that have differing
        security attributes or SLSA Build levels, each mode **MUST** have a
        different |id| and **SHOULD** have a different signer identity. This is
        to minimize the risk that a less secure mode compromises a more secure
        one.

        The |id| URI **SHOULD** resolve to documentation explaining:

        - The scope of what this ID represents.
        - The claimed SLSA Build level.
        - The accuracy and completeness guarantees of the fields in the
          provenance.
        - Any fields that are generated by the tenant-controlled build process
          and not verified by the trusted control plane, except for the
          ``subject``.
        - The interpretation of any extension fields.

        """  # noqa RST304
        return self.__id

    @property
    def version(self) -> dict[str, str]:
        """Builder version mapping.

        Map of names of components of the build platform to their version.
        """
        return self.__version

    def as_dict(self) -> dict:
        """Get the dictionary representation of this builder.

        :return: The dictionary representation of this builder. This should
            be a valid JSON object (call to |json.load| succeeds).

        .. seealso:: |json.load|
        """  # noqa RST304
        return {
            self.ATTR_BUILD_ID: str(self.id),
            self.ATTR_BUILDER_DEPENDENCIES: [
                desc.as_dict() for desc in self.builder_dependencies
            ],
            self.ATTR_VERSION: self.version,
        }

    def as_json(self) -> str:
        """Get the representation of this builder as a JSON string.

        The dictionary representing this builder (as returned by
        |builder.as_dict|) is turned into a JSON string using |json.dumps| with
        *sort_keys* set to **True**.

        .. seealso:: |builder.as_dict|, |builder.load_json|
        """  # noqa RST304
        return json.dumps(self.as_dict(), sort_keys=True)

    @classmethod
    def load_dict(cls, initializer: dict[str, Any]) -> Builder:
        """Initialize a builder from a dictionary.

        :param initializer: The dictionary to initialize this builder with.

        :return: A builder object created from the input *initializer*.

        :raise ValueError: if the build ID is not defined in *initializer*.

        .. seealso:: |builder.as_dict|
        """  # noqa RST304
        build_id: str | None = initializer.get(cls.ATTR_BUILD_ID)
        if build_id is None:
            raise ValueError("Invalid build ID (None)")

        builder: Builder = cls(
            build_id=build_id,
            builder_dependencies=[
                ResourceDescriptor.load_dict(rd)
                for rd in initializer.get(cls.ATTR_BUILDER_DEPENDENCIES, [])
            ],
            version=initializer.get(cls.ATTR_VERSION, {}),
        )

        return builder

    @classmethod
    def load_json(cls, initializer: str) -> Builder:
        """Initialize a builder from a JSON string.

        :param initializer: The JSON string to initialize this builder with.

        :return: A builder object created from the input *initializer*.

        :raise ValueError: if the build ID is not defined in *initializer*.

        .. seealso:: |builder.as_json|, |builder.load_dict|
        """  # noqa RST304
        return cls.load_dict(json.loads(initializer))


class BuildMetadata(object):
    """Build metadata representation.

    When the timestamp parameters (*started_on* or *finished_on*) are strings,
    the |TIMESTAMP_FORMAT| format is used to convert them to |datetime| classes
    using |strptime|.

    :param invocation_id: Identifier of this particular build invocation.
    :param started_on: The timestamp of this build invocation start time.
    :param finished_on: The timestamp of this build invocation finish time.

    .. |TIMESTAMP_FORMAT| replace:: :attr:`TIMESTAMP_FORMAT`
    .. |bm.as_dict| replace:: :meth:`~BuildMetadata.as_dict`
    .. |bm.as_json| replace:: :meth:`~BuildMetadata.as_json`
    .. |bm.load_dict| replace:: :meth:`~BuildMetadata.load_dict`
    .. |bm.load_json| replace:: :meth:`~BuildMetadata.load_json`
    .. |strptime| replace:: :meth:`~datetime.strptime`
    """  # noqa RST304

    ATTR_INVOCATION_ID: str = "invocationId"
    ATTR_STARTED_ON: str = "startedOn"
    ATTR_FINISHED_ON: str = "finishedOn"

    TIMESTAMP_FORMAT: str = "%Y-%m-%dT%H:%M:%SZ"
    """Timestamp format used to read/write |datetime| structures to strings."""

    def __init__(
        self,
        invocation_id: str,
        started_on: datetime,
        finished_on: datetime,
    ) -> None:
        self.__invocation_id: str = invocation_id
        self.__started_on: datetime = self.__validate_timestamp(started_on)
        self.__finished_on: datetime = self.__validate_timestamp(finished_on)

    def __eq__(self, other: object) -> bool:
        """Check if this build metadata object is equal to *other*.

        :param other: The build metadata object to compare this with.

        :return: A |bool| set to **True** if both build metadatas are equal,
            **False** else.
        """  # noqa RST304
        if isinstance(other, self.__class__):
            return self.as_json() == other.as_json()
        return False

    @property
    def finished_on(self) -> datetime:
        """The timestamp of when the build completed."""
        return self.__finished_on

    @property
    def invocation_id(self) -> str:
        """Build invocation identifier.

        Identifies this particular build invocation, which can be useful for
        finding associated logs or other ad-hoc analysis. The exact meaning and
        format is defined by |builder.id|; by default it is treated as opaque
        and case-sensitive.

        The value **SHOULD** be globally unique.

        .. |builder.id| replace:: :attr:`Builder.id`
        """  # noqa RST304
        return self.__invocation_id

    @property
    def started_on(self) -> datetime:
        """The timestamp of when the build started."""
        return self.__started_on

    # --------------------------- Public methods ---------------------------- #

    def as_dict(self) -> dict:
        """Get the dictionary representation of this build metadata.

        :return: The dictionary representation of this build metadata. This
            should be a valid JSON object (call to |json.load| succeeds).

        .. seealso:: |bm.as_json|, |json.load|, |bm.load_dict|
        """  # noqa RST304
        return {
            self.ATTR_INVOCATION_ID: self.invocation_id,
            self.ATTR_STARTED_ON: self.started_on.strftime(self.TIMESTAMP_FORMAT),
            self.ATTR_FINISHED_ON: self.finished_on.strftime(self.TIMESTAMP_FORMAT),
        }

    def as_json(self) -> str:
        """Get the representation of this build metadata as a JSON string.

        The dictionary representing this build metadata (as returned by
        |bm.as_dict|) is turned into a JSON string using |json.dumps| with
        *sort_keys* set to **True**.

        .. seealso:: |bm.as_dict|, |bm.load_json|
        """  # noqa RST304
        return json.dumps(self.as_dict(), sort_keys=True)

    @classmethod
    def load_dict(cls, initializer: dict[str, Any]) -> BuildMetadata:
        """Initialize a build metadata from a dictionary.

        :param initializer: The dictionary to initialize this build metadata
            with.

        :return: A build metadata object created from the input *initializer*.

        :raise ValueError: if the invocation ID is not defined in *initializer*,
            or if the timestamps are invalid.
        :raise TypeError: if the timestamps types are invalid.

        .. seealso:: |bm.as_dict|, |bm.load_json|
        """  # noqa RST304
        invocation_id: str | None = initializer.get(cls.ATTR_INVOCATION_ID)
        if invocation_id is None:
            raise ValueError("Invalid invocation ID (None)")

        # Transform timestamp strings to datetime objects.

        started_on: datetime = date_parser.parse(
            initializer.get(cls.ATTR_STARTED_ON, "")
        )
        finished_on: datetime = date_parser.parse(
            initializer.get(cls.ATTR_FINISHED_ON, "")
        )

        build_metadata: BuildMetadata = cls(
            invocation_id=invocation_id,
            started_on=started_on,
            finished_on=finished_on,
        )

        return build_metadata

    @classmethod
    def load_json(cls, initializer: str) -> BuildMetadata:
        """Initialize a build metadata from a JSON string.

        :param initializer: The JSON string to initialize this build metadata
            with.

        :return: A build metadata object created from the input *initializer*.

        :raise ValueError: if the build ID is not defined in *initializer*.

        .. seealso:: |builder.as_json|, |builder.load_dict|
        """  # noqa RST304
        return cls.load_dict(json.loads(initializer))

    # --------------------------- Private methods --------------------------- #

    @staticmethod
    def __validate_timestamp(timestamp: datetime) -> datetime:
        """Validate a timestamp."""
        valid_timestamp: datetime
        if isinstance(timestamp, datetime):
            # When converting to JSON representation, the microseconds
            # are lost. Just remove them.
            valid_timestamp = timestamp.astimezone(timezone.utc).replace(microsecond=0)
        else:
            raise TypeError(f"Invalid timestamp type {type(timestamp)}")

        return valid_timestamp


class Statement(object):
    """SLSA statement object.

    The Statement is the middle layer of the attestation, binding it to a
    particular subject and unambiguously identifying the types of the
    |Predicate|.

    :param statement_type: The URI identifier for the schema of the Statement.
    :param subject: Set of software artifacts that the attestation applies to.
    :param predicate_type: URI identifying the type of *predicate*.
    :param predicate: Additional parameters of the |Predicate|.

    .. |Predicate| replace:: :class:`Predicate`
    .. |predicateType| replace:: :attr:`~Predicate.predicatType`
    .. |st.as_dict| replace:: :meth:`~Statement.as_dict`
    .. |st.as_json| replace:: :meth:`~Statement.as_json`
    .. |st.load_dict| replace:: :meth:`~Statement.load_dict`
    .. |st.load_json| replace:: :meth:`~Statement.load_json`
    """  # noqa RST304

    ATTR_PREDICATE: str = "predicate"
    ATTR_PREDICATE_TYPE: str = "predicateType"
    ATTR_SUBJECT: str = "subject"
    ATTR_TYPE: str = "_type"

    SCHEMA_TYPE_VALUE: str = "https://in-toto.io/Statement/v1"
    PREDICATE_TYPE_VALUE: str = "https://slsa.dev/provenance/v1"

    def __init__(
        self,
        statement_type: TypeURI | str,
        subject: list[ResourceDescriptor],
        predicate_type: TypeURI | str = PREDICATE_TYPE_VALUE,
        predicate: Predicate | None = None,
    ) -> None:
        self.__type: TypeURI = (
            TypeURI(statement_type)
            if isinstance(statement_type, str)
            else statement_type
        )
        self.__subject: list[ResourceDescriptor] = subject
        self.__predicate_type: TypeURI = (
            TypeURI(predicate_type)
            if isinstance(predicate_type, str)
            else predicate_type
        )
        self.__predicate: Predicate | None = predicate

    def __eq__(self, other: object) -> bool:
        """Check if this statement is equal to *other*.

        :param other: The statement object to compare this with.

        :return: A |bool| set to **True** if both statements are equal,
            **False** else.
        """  # noqa RST304
        if isinstance(other, self.__class__):
            return self.as_json() == other.as_json()
        return False

    @property
    def type(self) -> TypeURI:
        """Identifier for the schema of the Statement.

        Always https://in-toto.io/Statement/v1 for this version of the spec.
        """
        return self.__type

    @property
    def predicate(self) -> Predicate | None:
        """Additional parameters of the |Predicate|.

        Unset is treated the same as set-but-empty. **MAY** be omitted if
        |predicateType| fully describes the predicate.
        """  # noqa RST304
        return self.__predicate

    @property
    def predicate_type(self) -> TypeURI:
        """URI identifying the type of the |Predicate|."""  # noqa RST304
        return self.__predicate_type

    @property
    def subject(self) -> list[ResourceDescriptor]:
        """Set of software artifacts that the attestation applies to.

        Each element represents a single software artifact. Each element
        **MUST** have digest set.

        The name field may be used as an identifier to distinguish this artifact
        from others within the subject. Similarly, other |ResourceDescriptor|
        fields may be used as required by the context. The semantics are up to
        the producer and consumer and they **MAY** use them when evaluating
        policy.

        If the name is not meaningful, leave the field unset or use ``_``. For
        example, a SLSA Provenance attestation might use the name to specify
        output filename, expecting the consumer to only consider entries with a
        particular name. Alternatively, a vulnerability scan attestation might
        leave name unset because the results apply regardless of what the
        artifact is named.

        If set, name and uri **SHOULD** be unique within subject.

        .. warning:: Subject artifacts are matched purely by digest, regardless
                     of content type. If this matters to you, please comment on
                     `GitHub Issue #28
                     <https://github.com/in-toto/attestation/issues/28>`_
        """  # noqa RST304
        return self.__subject

    def as_dict(self) -> dict:
        """Get the dictionary representation of this statement.

        :return: The dictionary representation of this statement. This should
            be a valid JSON object (call to |json.load| succeeds).

        .. seealso:: |json.load|
        """  # noqa RST304
        return {
            self.ATTR_TYPE: str(self.type),
            self.ATTR_SUBJECT: [subject.as_dict() for subject in self.subject],
            self.ATTR_PREDICATE_TYPE: str(self.predicate_type),
            self.ATTR_PREDICATE: self.predicate.as_dict() if self.predicate else None,
        }

    def as_json(self) -> str:
        """Get the representation of this statement as a JSON string.

        The dictionary representing this statement (as returned by
        |st.as_dict|) is turned into a JSON string using |json.dumps| with
        *sort_keys* set to **True**.

        .. seealso:: |st.as_dict|, |st.load_json|
        """  # noqa RST304
        return json.dumps(self.as_dict(), sort_keys=True)

    @classmethod
    def load_dict(cls, initializer: dict[str, Any]) -> Statement:
        """Initialize a statement from a dictionary.

        :param initializer: The dictionary to initialize this statement with.

        :return: A statement object created from the input *initializer*.

        :raise ValueError: if the statement type is not defined in
            *initializer*.

        .. seealso:: |st.as_dict|, |st.load_json|
        """  # noqa RST304
        statement_type: str | None = initializer.get(cls.ATTR_TYPE)
        if statement_type is None:
            raise ValueError("Invalid statement type (None)")

        predicate: dict = initializer.get(cls.ATTR_PREDICATE, {})

        statement: Statement = cls(
            statement_type=statement_type,
            subject=[
                ResourceDescriptor.load_dict(rd)
                for rd in initializer.get(cls.ATTR_SUBJECT, [])
            ],
            predicate_type=initializer.get(
                cls.ATTR_PREDICATE_TYPE, cls.PREDICATE_TYPE_VALUE
            ),
            predicate=Predicate.load_dict(predicate) if predicate else None,
        )

        return statement

    @classmethod
    def load_json(cls, initializer: str) -> Statement:
        """Initialize a statement from a JSON string.

        :param initializer: The JSON string to initialize this statement with.

        :return: A statement object created from the input *initializer*.

        :raise ValueError: if the statement type is not defined in
            *initializer*.

        .. seealso:: |st.as_json|, |st.load_dict|
        """  # noqa RST304
        return cls.load_dict(json.loads(initializer))


class ResourceDescriptor(object):
    """Resource descriptor object.

    A size-efficient description of any software artifact or resource (mutable
    or immutable).

    Though all fields are optional, a |ResourceDescriptor| **MUST** specify one
    of |uri|, |digest| or |content| at a minimum.

    Further, a context that uses the |ResourceDescriptor| can require one
    or more fields. For example, a predicate **MAY** require the name and digest
    fields.

    :param uri: see |uri|
    :param digest: see |digest|
    :param name: see |name|
    :param download_location: see |download_location|
    :param media_type: see |media_type|
    :param content: see |content|
    :param resource_annotations: see |annotations|

    .. note:: Those requirements cannot override the minimum requirement of one
              of |uri|, |digest|, or |content| specified here.

    .. |annotations| replace:: :attr:`~ResourceDescriptor.annotations`
    .. |rd.as_dict| replace:: :meth:`~ResourceDescriptor.as_dict`
    .. |rd.as_json| replace:: :meth:`~ResourceDescriptor.as_json`
    .. |content| replace:: :attr:`~ResourceDescriptor.content`
    .. |digest| replace:: :attr:`~ResourceDescriptor.digest`
    .. |download_location| replace::
        :attr:`~ResourceDescriptor.download_location`
    .. |is_valid| replace:: :attr:`~ResourceDescriptor.is_valid`
    .. |rd.load_dict| replace:: :meth:`~ResourceDescriptor.load_dict`
    .. |rd.load_json| replace:: :meth:`~ResourceDescriptor.load_json`
    .. |media_type| replace:: :attr:`~ResourceDescriptor.media_type`
    .. |name| replace:: :attr:`~ResourceDescriptor.name`
    .. |uri| replace:: :attr:`~ResourceDescriptor.uri`
    """  # noqa RST304

    ATTR_ANNOTATIONS: str = "annotations"
    ATTR_CONTENT: str = "content"
    ATTR_DIGEST: str = "digest"
    ATTR_DOWNLOAD_LOCATION: str = "downloadLocation"
    ATTR_MEDIA_TYPE: str = "mediaType"
    ATTR_NAME: str = "name"
    ATTR_URI: str = "uri"

    # Order of attributes is taken out of the schema at
    # https://slsa.dev/spec/v1.0/provenance
    ATTRIBUTES: tuple = (
        ATTR_URI,
        ATTR_DIGEST,
        ATTR_NAME,
        ATTR_DOWNLOAD_LOCATION,
        ATTR_MEDIA_TYPE,
        ATTR_CONTENT,
        ATTR_ANNOTATIONS,
    )
    """JSON attributes returned by the |rd.as_dict| method (if the given attribute
    defines a value).
    """  # noqa RST304

    def __init__(
        self,
        uri: ResourceURI | str | None = None,
        digest: dict[str, str] | None = None,
        name: str | None = None,
        download_location: ResourceURI | str | None = None,
        media_type: str | None = None,
        content: bytes | None = None,
        resource_annotations: dict[str, Any] | None = None,
    ) -> None:
        self.__annotations: dict[str, Any] = resource_annotations or {}
        self.__content: bytes | None = content
        self.__digest: dict[str, str] = digest if digest is not None else {}
        self.__download_location: ResourceURI | None = None
        self.__media_type: str | None = media_type
        self.__name: str | None = name
        self.__uri: ResourceURI | None = None

        # Use the attribute setters for potential conversion.
        if download_location:
            self.download_location = download_location  # type: ignore[assignment]
        if uri:
            self.uri = uri  # type: ignore[assignment]

    def __eq__(self, other: object) -> bool:
        """Check if this resource descriptor is equal to *other*.

        :param other: The resource descriptor object to compare this with.

        :return: A |bool| set to **True** if both resource descriptors are
            equal, **False** else.
        """  # noqa RST304
        if isinstance(other, self.__class__):
            return self.as_json() == other.as_json()
        return False

    @property
    def annotations(self) -> dict[str, Any]:
        """Resource descriptor additional information.

        This field MAY be used to provide additional information or metadata
        about the resource or artifact that may be useful to the consumer when
        evaluating the attestation against a policy.

        For maximum flexibility annotations may be any mapping from a field name
        to any JSON value (string, number, object, array, boolean or null).

        The producer and consumer **SHOULD** agree on the semantics, and
        acceptable fields and values in the annotations map.

        Producers **SHOULD** follow the same naming conventions for annotation
        fields as for extension fields.
        """
        return self.__annotations

    @annotations.setter
    def annotations(self, value: dict[str, Any]) -> None:
        if isinstance(value, dict):
            self.__annotations = value
        else:
            raise TypeError(f"Invalid resource descriptor annotations type: {value}")

    @property
    def content(self) -> bytes | None:
        """The contents of the resource or artifact.

        This field is **REQUIRED** unless either |uri| or |digest| is set.

        The producer **MAY** use this field in scenarios where including the
        contents of the resource/artifact directly in the attestation is deemed
        more efficient for consumers than providing a pointer to another
        location.

        To maintain size efficiency, the size of content **SHOULD** be less than
        1KB.

        The semantics are up to the producer and consumer. The |uri| or
        |media_type| **MAY** be used by the producer as hints for how consumers
        should parse content.

        :raise TypeError: When setting this field to something else than a
            |bytes| or ``None``.
        """  # noqa RST304
        return self.__content

    @content.setter
    def content(self, value: bytes | None) -> None:
        if isinstance(value, bytes) or value is None:
            self.__content = value
        else:
            raise TypeError(f"Invalid resource descriptor content type: {value}")

    @property
    def digest(self) -> dict[str, str]:
        """A set of digests for this resource descriptor.

        A set of cryptographic digests of the contents of the resource or
        artifact.

        This field is **REQUIRED** unless either |uri|, or |content| is set.

        When known, the producer **SHOULD** set this field to denote an
        immutable artifact or resource.

        The producer and consumer **SHOULD** agree on acceptable algorithms.

        :raise TypeError: When setting this field to something else than a
            |dict|.
        """  # noqa RST304
        return self.__digest

    @digest.setter
    def digest(self, value: dict[str, str]) -> None:
        if isinstance(value, dict):
            self.__digest = value
        else:
            raise TypeError(f"Invalid resource descriptor digest type: {value}")

    @property
    def download_location(self) -> ResourceURI | None:
        """Artifact download location.

        The location of the described resource or artifact, if different from
        the |uri|.

        To enable automated downloads by consumers, the specified location
        **SHOULD** be resolvable.

        :raise TypeError: When setting this field to something else than a
            |ResourceURI| or ``None``.
        """  # noqa RST304
        return self.__download_location

    @download_location.setter
    def download_location(self, value: ResourceURI | str | None) -> None:
        if isinstance(value, ResourceURI) or value is None:
            self.__download_location = value
        elif isinstance(value, str):
            self.__download_location = ResourceURI(value)
        else:
            raise TypeError(
                f"Invalid resource descriptor download location type: {value}"
            )

    @property
    def is_valid(self) -> bool:
        """Check if this resource descriptor is valid.

        To be valid, a resource descriptor should define at least one of the
        following:

        - |content|
        - |digest|
        - |uri|

        :return: A |bool| set to **True** if at least one of the above-mentioned
            field is defined, **False** else.
        """  # noqa RST304
        if self.uri or self.content or self.digest:
            return True
        return False

    @property
    def name(self) -> str | None:
        """Machine-readable identifier for distinguishing between descriptors.

        The semantics are up to the producer and consumer. The |name| name
        **SHOULD** be stable, such as a filename, to allow consumers to reliably
        use the |name| as part of their policy.
        """  # noqa RST304
        return self.__name

    @name.setter
    def name(self, value: str | None) -> None:
        if isinstance(value, str) or value is None:
            self.__name = value
        else:
            raise TypeError(f"Invalid resource descriptor name: {value}")

    @property
    def media_type(self) -> str | None:
        """This resource descriptor media type.

        The `MIME Type
        <https://developer.mozilla.org/en-US/docs/Web/HTTP/Basics_of_HTTP/MIME_types>`_
        (i.e., media type) of the described resource or artifact.

        For resources or artifacts that do not have a standardized MIME type,
        producers **SHOULD** follow `RFC 6838 (Sections 3.2-3.4)
        <https://www.rfc-editor.org/rfc/rfc6838.html#section-3.2>`_ conventions
        of prefixing types with ``x.``, ``prs.``, or ``vnd.`` to avoid
        collisions with other producers.
        """
        return self.__media_type

    @media_type.setter
    def media_type(self, value: str | None) -> None:
        if isinstance(value, str) or value is None:
            self.__media_type = value
        else:
            raise TypeError(f"Invalid resource descriptor media type: {value}")

    @property
    def uri(self) -> ResourceURI | None:
        """A URI used to identify the resource or artifact globally.

        This field is **REQUIRED** unless either digest or content is set.
        """
        return self.__uri

    @uri.setter
    def uri(self, value: ResourceURI | str | None) -> None:
        if isinstance(value, ResourceURI) or value is None:
            self.__uri = value
        elif isinstance(value, str):
            self.__uri = ResourceURI(value)
        else:
            raise TypeError(f"Invalid resource descriptor uri type: {value}")

    def add_digest(self, algorithm: str, digest: str) -> None:
        """Add a new digest to the digest set.

        :param algorithm: The algorithm the new digest has been computed with.
        :param digest: The new digest to add to the digest set.

        :raise KeyError: if *algorithm* already defines a digest in the current
            digest set.
        """
        if algorithm not in self.__digest:
            self.__digest[algorithm] = digest
        else:
            raise KeyError(
                f"Digest algorithm {algorithm} is already set to "
                "{self.__digest[algorithm]}"
            )

    def as_dict(self) -> dict:
        """Get the dictionary representation of this resource descriptor.

        :return: The dictionary representation of this resource descriptor.
            This should be a valid JSON object.

        :raise ValueError: If this resource descriptor is not valid (see
            |is_valid|).

        .. seealso:: |rd.as_json|, |is_valid|, |rd.load_dict|
        """  # noqa RST304
        if not self.is_valid:
            raise ValueError(
                "Invalid resource descriptor. Either uri, content or digest "
                "should be defined."
            )

        return {
            self.ATTR_URI: str(self.uri) if self.uri is not None else None,
            self.ATTR_DIGEST: self.digest,
            self.ATTR_NAME: self.name,
            self.ATTR_DOWNLOAD_LOCATION: (
                str(self.download_location)
                if self.download_location is not None
                else None
            ),
            self.ATTR_MEDIA_TYPE: self.media_type,
            self.ATTR_CONTENT: (
                None
                if self.content is None
                else base64.b64encode(self.content).decode("utf-8")
            ),
            self.ATTR_ANNOTATIONS: self.annotations,
        }

    def as_json(self) -> str:
        """Get the representation of this resource descriptor as a JSON string.

        The dictionary representing this resource descriptor (as returned by
        |rd.as_dict|) is turned into a JSON string using |json.dumps| with
        *sort_keys* set to **True**.

        .. seealso:: |rd.as_dict|, |rd.load_json|
        """  # noqa RST304
        return json.dumps(self.as_dict(), sort_keys=True)

    @staticmethod
    def dir_hash(path: Path, algorithm: str) -> str:
        r"""Directory hash.

        The `directory Hash1
        <https://cs.opensource.google/go/x/mod/+/refs/tags/v0.5.0:sumdb/dirhash/hash.go>`_
        function, omitting the ``h1:`` prefix and output in lowercase
        hexadecimal instead of base64.

        This algorithm was designed for go modules but can be used to digest the
        contents of an arbitrary archive or file tree.

        Equivalent to extracting the archive to an empty directory and running
        the following command in that directory::

            find . -type f | cut -c3- | LC_ALL=C sort | xargs -r sha256sum \\
                           | sha256sum | cut -f1 -d' '

        For example, the module dirhash
        ``h1:Khu2En+0gcYPZ2kuIihfswbzxv/mIHXgzPZ018Oty48=`` would be encoded as
        ``{"dirHash1":
        "2a1bb6127fb481c60f67692e22285fb306f3c6ffe62075e0ccf674d7c3adcb8f"}``.
        """
        # First check that there is a valid algorithm for dir_hash.
        if algorithm not in hashlib.algorithms_guaranteed:
            raise ValueError(
                f"Unsupported digest algorithm {algorithm} for dir_hash().\n"
                f"Available algorithms are: {hashlib.algorithms_guaranteed}"
            )

        need_length: bool = algorithm.startswith("shake_")
        folder_hash = getattr(hashlib, algorithm)()

        # List files in path, and read them 4096 bytes per 4096 bytes to
        # compute a global has.
        for filepath in sorted(path.rglob("*")):
            if filepath.is_file():
                file_hash = getattr(hashlib, algorithm)()
                with filepath.open("rb") as f:
                    for chunk in iter(lambda: f.read(4096), b""):
                        file_hash.update(chunk)

                rel_path: str = f"{filepath.relative_to(path).as_posix()}"
                hash_str: str
                if need_length:
                    hash_str = f"{file_hash.hexdigest(64)}  {rel_path}\n"
                else:
                    hash_str = f"{file_hash.hexdigest()}  {rel_path}\n"

                folder_hash.update(hash_str.encode("utf-8"))

        # Compute the final hash.
        final_hash: str
        if need_length:
            final_hash = f"{folder_hash.hexdigest(64)}"
        else:
            final_hash = f"{folder_hash.hexdigest()}"

        return final_hash

    @classmethod
    def load_dict(cls, initializer: dict[str, Any]) -> ResourceDescriptor:
        """Initialize a resource descriptor from a dictionary.

        :param initializer: The dictionary to initialize this resource
            descriptor with.

        :return: A resource descriptor object created from the input
            *initializer*.

        :raise ValueError: If this resource descriptor is not valid once
            initialized with the dictionary content (see |is_valid|).

        .. seealso:: |rd.as_dict|, |is_valid|
        """  # noqa RST304
        content: str = initializer.get(cls.ATTR_CONTENT, "")
        resource_descriptor: ResourceDescriptor = cls(
            uri=initializer.get(cls.ATTR_URI),
            digest=initializer.get(cls.ATTR_DIGEST),
            name=initializer.get(cls.ATTR_NAME),
            download_location=initializer.get(cls.ATTR_DOWNLOAD_LOCATION),
            media_type=initializer.get(cls.ATTR_MEDIA_TYPE),
            content=base64.b64decode(content.encode("utf-8")) if content else None,
            resource_annotations=initializer.get(cls.ATTR_ANNOTATIONS),
        )

        if not resource_descriptor.is_valid:
            raise ValueError(
                "Invalid resource descriptor. Either uri, content or digest "
                "should be defined."
            )

        return resource_descriptor

    @classmethod
    def load_json(cls, initializer: str) -> ResourceDescriptor:
        """Initialize a resource descriptor from a JSON string.

        :param initializer: The JSON string to initialize this resource
            descriptor with.

        :return: A resource descriptor object created from the input
            *initializer*.

        :raise ValueError: If this resource descriptor is not valid once
            initialized with the dictionary content (see |is_valid|).

        .. seealso:: |rd.load_dict|, |is_valid|
        """  # noqa RST304
        return cls.load_dict(json.loads(initializer))


class Predicate(object):
    """Predicate object.

    .. |p.as_dict| replace:: :meth:`as_dict`
    .. |p.as_json| replace:: :meth:`as_json`
    .. |p.load_dict| replace:: :meth:`load_dict`
    .. |p.load_json| replace:: :meth:`load_json`
    """  # noqa RST304

    ATTR_BUILD_DEFINITION: str = "buildDefinition"
    ATTR_RUN_DETAILS: str = "runDetails"

    class BuildDefinition(object):
        """The BuildDefinition describes all the inputs to the build.

        It **SHOULD** contain all the information necessary and sufficient to
        initialize the build and begin execution.

        The |externalParameters| and |internalParameters| are the top-level
        inputs to the template, meaning inputs not derived from another input.
        Each is an arbitrary JSON object, though it is **RECOMMENDED** to keep
        the structure simple with string values to aid verification.

        The same field name **SHOULD NOT** be used for both |externalParameters|
        and |internalParameters|.

        The parameters **SHOULD** only contain the actual values passed in
        through the interface to the build platform.

        Metadata about those parameter values, particularly digests of
        artifacts referenced by those parameters, **SHOULD** instead go in
        |resolvedDependencies|.

        The documentation for |buildType| **SHOULD** explain how to convert
        from a parameter to the dependency uri. For example::

            "externalParameters": {
                "repository": "https://github.com/octocat/hello-world",
                "ref": "refs/heads/main"
            },
            "resolvedDependencies": [{
                "uri": "git+https://github.com/octocat/hello-world@refs/heads/main",
                "digest": {"gitCommit": "7fd1a60b01f91b314f59955a4e4d4e80d8edf11d"}
            }]


        Guidelines
        ----------

        - Maximize the amount of information that is implicit from the meaning
          of |buildType|. In particular, any value that is boilerplate and the
          same for every build **SHOULD** be implicit.
        - Reduce parameters by moving configuration to input artifacts whenever
          possible. For example, instead of passing in compiler flags via an
          external parameter that has to be verified separately, require the
          flags to live next to the source code or build configuration so that
          verifying the latter automatically verifies the compiler flags.
        - In some cases, additional external parameters might exist that do not
          impact the behavior of the build, such as a deadline or priority.
          These extra parameters **SHOULD** be excluded from the provenance
          after careful analysis that they indeed pose no security impact.
        - If possible, architect the build platform to use this definition as
          its sole top-level input, in order to guarantee that the information
          is sufficient to run the build.
        - When build configuration is evaluated client-side before being sent
          to the server, such as transforming version-controlled YAML into
          ephemeral JSON, some solution is needed to make verification
          practical. Consumers need a way to know what configuration is
          expected and the usual way to do that is to map it back to version
          control, but that is not possible if the server cannot verify the
          configuration’s origins. Possible solutions:

            - (**RECOMMENDED**) Rearchitect the build platform to read
              configuration directly from version control, recording the
              server-verified URI in |externalParameters| and the digest in
              |resolvedDependencies|.
            - Record the digest in the provenance and use a separate provenance
              attestation to link that digest back to version control. In this
              solution, the client-side evaluation is considered a separate
              *build* that **SHOULD** be independently secured using |SLSA|,
              though securing it can be difficult since it usually runs on an
              untrusted workstation.

        - The purpose of |resolvedDependencies| is to facilitate recursive
          analysis of the software supply chain. Where practical, it is
          valuable to record the URI and digest of artifacts that, if
          compromised, could impact the build. At |SLSA| Build L3, completeness
          is considered *best effort*.

        .. |buildType| replace:: :attr:`build_type`
        .. |bd.as_dict| replace:: :meth:`as_dict`
        .. |bd.as_json| replace:: :meth:`as_json`
        .. |externalParameters| replace:: :attr:`external_parameters`
        .. |internalParameters| replace:: :attr:`internal_parameters`
        .. |bd.load_dict| replace:: :meth:`load_dict`
        .. |bd.load_json| replace:: :meth:`load_json`
        .. |resolvedDependencies| replace:: :attr:`resolved_dependencies`
        """  # noqa RST304

        ATTR_BUILD_TYPE: str = "buildType"
        ATTR_EXTERNAL_PARAMETERS: str = "externalParameters"
        ATTR_INTERNAL_PARAMETERS: str = "internalParameters"
        ATTR_RESOLVED_DEPENDENCIES: str = "resolvedDependencies"

        def __init__(
            self,
            build_type: TypeURI | str,
            external_parameters: object,
            internal_parameters: object,
            resolved_dependencies: list[ResourceDescriptor],
        ) -> None:
            self.__build_type: TypeURI = (
                TypeURI(build_type) if isinstance(build_type, str) else build_type
            )
            self.__external_parameters: object = external_parameters
            self.__internal_parameters: object = internal_parameters
            self.__resolved_dependencies: list[ResourceDescriptor] = (
                resolved_dependencies
            )

        def __eq__(self, other: object) -> bool:
            """Check if this build definition is equal to *other*.

            :param other: The build definition object to compare this with.

            :return: A |bool| set to **True** if both build definitions are
                equal, **False** else.
            """  # noqa RST304
            if isinstance(other, self.__class__):
                return self.as_json() == other.as_json()
            return False

        @property
        def build_type(self) -> TypeURI | None:
            """Predicate build type.

            Identifies the template for how to perform the build and interpret
            the parameters and dependencies.

            The URI **SHOULD** resolve to a human-readable specification that
            includes:

            - overall description of the build type
            - schema for externalParameters and internalParameters
            - unambiguous instructions for how to initiate the build given this
              BuildDefinition, and a complete example.

            Example
            -------
            ::

                https://slsa-framework.github.io/github-actions-buildtypes/workflow/v1
            """
            return self.__build_type

        @property
        def external_parameters(self) -> object | None:
            """The parameters that are under external control.

            Such as those set by a user or tenant of the build platform.
            They **MUST** be complete at SLSA Build L3, meaning that there is no
            additional mechanism for an external party to influence the build.
            (At lower SLSA Build levels, the completeness **MAY** be best
            effort.)

            The build platform **SHOULD** be designed to minimize the size and
            complexity of ``externalParameters``, in order to reduce fragility
            and ease verification.

            Consumers **SHOULD** have an expectation of what **good** looks
            like;  the more information that they need to check, the harder that
            task becomes.

            Verifiers **SHOULD** reject unrecognized or unexpected fields within
            ``externalParameters``.
            """
            return self.__external_parameters

        @property
        def internal_parameters(self) -> object | None:
            """Internal parameters.

            The parameters that are under the control of the entity represented
            by ``builder.id``.

            The primary intention of this field is for debugging, incident
            response, and vulnerability management.

            The values here **MAY** be necessary for reproducing the build.

            There is no need to verify these parameters because the build
            platform is already trusted, and in many cases it is not practical
            to do so.
            """
            return self.__internal_parameters

        @property
        def resolved_dependencies(self) -> list[ResourceDescriptor]:
            """Unordered collection of artifacts needed at build time.

            Completeness is best effort, at least through SLSA Build L3.

            For example, if the build script fetches and executes
            ``example.com/foo.sh``, which in turn fetches
            ``example.com/bar.tar.gz``, then both ``foo.sh`` and ``bar.tar.gz``
            **SHOULD** be listed here.
            """
            return self.__resolved_dependencies

        def as_dict(self) -> dict:
            """Get the dictionary representation of this build definition.

            :return: The dictionary representation of this build definition.
                This should be a valid JSON object (call to |json.load|
                succeeds).

            .. seealso:: |bd.as_json|, |json.load|, |bd.load_dict|
            """  # noqa RST304
            return {
                self.ATTR_BUILD_TYPE: str(self.build_type) if self.build_type else None,
                self.ATTR_EXTERNAL_PARAMETERS: self.external_parameters,
                self.ATTR_INTERNAL_PARAMETERS: self.internal_parameters,
                self.ATTR_RESOLVED_DEPENDENCIES: [
                    rd.as_dict() for rd in self.resolved_dependencies
                ],
            }

        def as_json(self) -> str:
            """Get the representation of this build definition as a JSON string.

            The dictionary representing this build defintion (as returned by
            |bd.as_dict|) is turned into a JSON string using |json.dumps| with
            *sort_keys* set to **True**.

            .. seealso:: |bd.as_dict|, |bd.load_json|
            """  # noqa RST304
            return json.dumps(self.as_dict(), sort_keys=True)

        @classmethod
        def load_dict(cls, initializer: dict[str, Any]) -> Predicate.BuildDefinition:
            """Initialize a build definition from a dictionary.

            :param initializer: The dictionary to initialize this build
                definition with.

            :return: A build definition object created from the input
                *initializer*.

            .. seealso:: |bd.as_dict|, |bd.load_json|
            """  # noqa RST304
            build_definition: Predicate.BuildDefinition = cls(
                build_type=initializer.get(cls.ATTR_BUILD_TYPE, ""),
                external_parameters=initializer.get(cls.ATTR_EXTERNAL_PARAMETERS),
                internal_parameters=initializer.get(cls.ATTR_INTERNAL_PARAMETERS),
                resolved_dependencies=[
                    ResourceDescriptor.load_dict(rd)
                    for rd in initializer.get(cls.ATTR_RESOLVED_DEPENDENCIES, [])
                ],
            )

            return build_definition

        @classmethod
        def load_json(cls, initializer: str) -> Predicate.BuildDefinition:
            """Initialize a build definition from a JSON string.

            :param initializer: The JSON string to initialize this build
                definition with.

            :return: A build definition object created from the input
                *initializer*.

            .. seealso:: |bd.as_json|, |bd.load_dict|
            """  # noqa RST304
            return cls.load_dict(json.loads(initializer))

    class RunDetails(object):
        """Details specific to this particular execution of the build.

        :param builder: Run details builder description.
        :param metadata: The metadata for this run details object.
        :param by_products: Run details additional artifacts.

        .. |rund.as_dict| replace:: :meth:`as_dict`
        .. |rund.as_json| replace:: :meth:`as_json`
        .. |rund.load_dict| replace:: :meth:`load_dict`
        .. |rund.load_json| replace:: :meth:`load_json`
        """  # noqa RST304

        ATTR_BUILDER: str = "builder"
        ATTR_METADATA: str = "metadata"
        ATTR_BY_PRODUCTS: str = "byproducts"

        def __init__(
            self,
            builder: Builder,
            metadata: BuildMetadata,
            by_products: list[ResourceDescriptor],
        ) -> None:
            self.__builder: Builder = builder
            self.__metadata: BuildMetadata = metadata
            self.__by_products: list[ResourceDescriptor] = by_products

        def __eq__(self, other: object) -> bool:
            """Check if this run details object is equal to *other*.

            :param other: The run details object to compare this with.

            :return: A |bool| set to **True** if both run details are equal,
                **False** else.
            """  # noqa RST304
            if isinstance(other, self.__class__):
                return self.as_json() == other.as_json()
            return False

        @property
        def builder(self) -> Builder:
            """Run details builder.

            Identifies the build platform that executed the invocation, which
            is trusted to have correctly performed the operation and populated
            this provenance.
            """
            return self.__builder

        @property
        def by_products(self) -> list[ResourceDescriptor]:
            """Run details additional artifacts.

            Additional artifacts generated during the build that are not
            considered the **output** of the build but that might be needed
            during debugging or incident response.

            For example, this might reference logs generated during the build
            and/or a digest of the fully evaluated build configuration.

            In most cases, this **SHOULD NOT** contain all intermediate files
            generated during the build.

            Instead, this **SHOULD** only contain files that are likely to be
            useful later and that cannot be easily reproduced.
            """
            return self.__by_products

        @property
        def metadata(self) -> BuildMetadata:
            """Run details build metadata.

            Metadata about this particular execution of the build.
            """
            return self.__metadata

        def as_dict(self) -> dict:
            """Get the dictionary representation of this run details.

            :return: The dictionary representation of this run details. This
                should be a valid JSON object (call to |json.load| succeeds).

            .. seealso:: |rund.as_json|, |json.load|, |rund.load_dict|
            """  # noqa RST304
            return {
                self.ATTR_BUILDER: self.builder.as_dict(),
                self.ATTR_METADATA: self.metadata.as_dict(),
                self.ATTR_BY_PRODUCTS: [rd.as_dict() for rd in self.by_products],
            }

        def as_json(self) -> str:
            """Get the representation of this run details as a JSON string.

            The dictionary representing this run details (as returned by
            |rund.as_dict|) is turned into a JSON string using |json.dumps| with
            *sort_keys* set to **True**.

            .. seealso:: |rund.as_dict|, |rund.load_json|
            """  # noqa RST304
            return json.dumps(self.as_dict(), sort_keys=True)

        @classmethod
        def load_dict(cls, initializer: dict[str, Any]) -> Predicate.RunDetails:
            """Initialize a run details from a dictionary.

            :param initializer: The dictionary to initialize this run details
                with.

            :return: A run details object created from the input *initializer*.

            .. seealso:: |rund.as_dict|, |rund.load_json|
            """  # noqa RST304
            builder: dict | None = initializer.get(cls.ATTR_BUILDER)
            metadata: dict | None = initializer.get(cls.ATTR_METADATA)
            by_products: list[dict] = initializer.get(cls.ATTR_BY_PRODUCTS, [])

            # builder and metadata should be required.

            if builder is None:
                raise ValueError("Missing builder definition.")

            if metadata is None:
                raise ValueError("Missing metadata definition.")

            run_details: Predicate.RunDetails = cls(
                builder=Builder.load_dict(builder),
                metadata=BuildMetadata.load_dict(metadata),
                by_products=[ResourceDescriptor.load_dict(rd) for rd in by_products],
            )

            return run_details

        @classmethod
        def load_json(cls, initializer: str) -> Predicate.RunDetails:
            """Initialize a run details from a JSON string.

            :param initializer: The JSON string to initialize this run details
                with.

            :return: A run details object created from the input *initializer*.

            .. seealso:: |rund.as_json|, |rund.load_dict|
            """  # noqa RST304
            return cls.load_dict(json.loads(initializer))

    def __init__(
        self,
        build_definition: Predicate.BuildDefinition,
        run_details: Predicate.RunDetails,
    ) -> None:
        self.__build_definition: Predicate.BuildDefinition = build_definition
        self.__run_details: Predicate.RunDetails = run_details

    def __eq__(self, other: object) -> bool:
        """Check if this predicate is equal to *other*.

        :param other: The predicate object to compare this with.

        :return: A |bool| set to **True** if both predicates are equal,
            **False** else.
        """  # noqa RST304
        if isinstance(other, self.__class__):
            return self.as_json() == other.as_json()
        return False

    @property
    def build_definition(self) -> Predicate.BuildDefinition:
        """The input to the build.

        The accuracy and completeness are implied by runDetails.builder.id.
        """
        return self.__build_definition

    @property
    def run_details(self) -> Predicate.RunDetails:
        """Details specific to this particular execution of the build."""
        return self.__run_details

    def as_dict(self) -> dict:
        """Get the dictionary representation of this predicate.

        :return: The dictionary representation of this statement. This should
            be a valid JSON object (call to |json.load| succeeds).

        .. seealso:: |p.as_json|, |json.load|, |p.load_dict|
        """  # noqa RST304
        return {
            self.ATTR_BUILD_DEFINITION: self.build_definition.as_dict(),
            self.ATTR_RUN_DETAILS: self.run_details.as_dict(),
        }

    def as_json(self) -> str:
        """Get the representation of this predicate as a JSON string.

        The dictionary representing this predicate (as returned by
        |p.as_dict|) is turned into a JSON string using |json.dumps| with
        *sort_keys* set to **True**.

        .. seealso:: |p.as_dict|, |p.load_json|
        """  # noqa RST304
        return json.dumps(self.as_dict(), sort_keys=True)

    @classmethod
    def load_dict(cls, initializer: dict[str, Any]) -> Predicate:
        """Initialize a predicate from a dictionary.

        :param initializer: The dictionary to initialize this predicat with.

        :return: A predicate object created from the input *initializer*.

        .. seealso:: |p.as_dict|, |p.load_json|
        """  # noqa RST304
        build_definition: dict | None = initializer.get(cls.ATTR_BUILD_DEFINITION)
        run_details: dict | None = initializer.get(cls.ATTR_RUN_DETAILS)

        # All fields should be mandatory.

        if build_definition is None:
            raise ValueError("Missing build definition.")

        if run_details is None:
            raise ValueError("Missing run details definition.")

        predicate: Predicate = cls(
            build_definition=Predicate.BuildDefinition.load_dict(build_definition),
            run_details=Predicate.RunDetails.load_dict(run_details),
        )

        return predicate

    @classmethod
    def load_json(cls, initializer: str) -> Predicate:
        """Initialize a predicate from a JSON string.

        :param initializer: The JSON string to initialize this predicate with.

        :return: A predictae object created from the input *initializer*.

        .. seealso:: |p.as_json|, |p.load_dict|
        """  # noqa RST304
        return cls.load_dict(json.loads(initializer))


class TypeURI(object):
    """Uniform Resource Identifier as specified in RFC 3986.

    Used as a collision-resistant type identifier.

    Format
    ------
    A TypeURI is represented as a case-sensitive string and **MUST** be case
    normalized as per section 6.2.2.1 of RFC 3986, meaning that the scheme and
    authority **MUST** be in lowercase.

    **SHOULD** resolve to a human-readable description, but **MAY** be
    unresolvable. **SHOULD** include a version number to allow for revisions.

    TypeURIs are not registered. The natural namespacing of URIs is sufficient
    to prevent collisions.

    Example
    -------
    ::

        https://in-toto.io/Statement/v1
    """

    def __init__(self, uri: str):
        # Validate this uri.
        from urllib.parse import ParseResult, urlparse

        try:
            parsed: ParseResult = urlparse(uri)
            if not all([parsed.scheme, parsed.netloc]):
                raise ValueError(f"Invalid URI {uri}.")
        except ValueError:
            raise
        except AttributeError as ae:
            raise ValueError(f"Invalid URI {uri} : {ae}.") from ae
        self.__uri = uri

    def __eq__(self, other: object) -> bool:
        """Check if this type uri is equal to *other*."""
        if isinstance(other, TypeURI):
            return self.uri == other.uri
        elif isinstance(other, str):
            return self.uri == other
        return False

    def __str__(self) -> str:
        """Return the string representation of this TypeURI."""
        return self.uri

    @property
    def uri(self) -> str:
        """Actual URI of this TypeURI.

        :return: The actual URI of this TypeURI.
        """
        return self.__uri


class ResourceURI(TypeURI):
    """Uniform Resource Identifier as specified in RFC 3986.

     Used to identify and locate any resource, service, or software artifact.

    Format
    ------
    A ResourceURI is represented as a case-sensitive string and **MUST** be case
    normalized as per section 6.2.2.1 of RFC 3986, meaning that the scheme and
    authority **MUST** be in lowercase.

    **SHOULD** resolve to the artifact, but **MAY** be unresolvable.

    It is **RECOMMENDED** to use
    `Package URL <https://github.com/package-url/purl-spec/>`_ (``pkg:``) or
    `SPDX Download Location
    <https://spdx.github.io/spdx-spec/v2.3/package-information/#77-package-download-location-field>`_
    (e.g. ``git+https:``).

    Example
    -------
    ::

        pkg:deb/debian/stunnel@5.50-3?arch=amd64
    """

    def __init__(self, uri: str):
        super(ResourceURI, self).__init__(uri)
