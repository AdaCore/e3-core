from __future__ import annotations

from difflib import get_close_matches
from typing import TYPE_CHECKING
from hashlib import sha1
from e3.anod.error import AnodError
import abc
import re


if TYPE_CHECKING:
    from typing import Iterable
    from e3.anod.spec import Anod


VALID_NAME = re.compile(r"^[a-zA-Z0-9_.+-]+$")


def check_valid_name(name: str, value_kind: str, origin: str) -> str:
    """Check if a value is a valid qualifier name or component name.

    A valid name is any non empty string containg alphanumeric character, dot,
    dashes and underscores.

    :param name: the name to check
    :param value_kind: a name to describe the kind of value (used in error message)
    :param origin: a string giving the origin of the check
    :return: name if name is valid otherwise raise AnodError
    """
    if not isinstance(name, str) or not re.search(VALID_NAME, name):
        raise AnodError(f"{origin}: Invalid {value_kind} '{name}'")
    return name


class QualifierDeclaration(metaclass=abc.ABCMeta):
    """Root class for qualifiers declaration."""

    def __init__(
        self,
        origin: str,
        name: str,
        description: str,
        repr_in_hash: bool = False,
        repr_name: str | None = None,
    ) -> None:
        """Initialize a qualifier declaration.

        :param origin: a string giving the origin of the declaration
            (used in error messages)
        :param name: qualifier name
        :param description: help message
        :param repr_in_hash: if True the qualifier representation is hidden
            into a common hash
        :param repr_name: an alias for name used to compute string representation
        """
        self.origin = origin
        self.name = check_valid_name(
            name, value_kind="qualifier declaration name", origin=self.origin
        )
        self.description = description
        self.repr_in_hash = repr_in_hash
        self.repr_name = (
            check_valid_name(
                repr_name,
                value_kind="qualifier declaration alias",
                origin=self.origin,
            )
            if repr_name is not None
            else self.name
        )

    @property
    def default(self) -> str | bool | frozenset[str] | None:
        """Return default value for qualifier.

        :return: if None is returned it means the qualifier has not
            default Value. Otherwise the default value is returned.
        """
        return None  # all: no cover

    @abc.abstractmethod
    def value(
        self, value: str | bool | Iterable[str] | None
    ) -> str | bool | frozenset[str]:
        """Compute the value of qualifier given the user input."""

    @abc.abstractmethod
    def repr(
        self, value: str | bool | frozenset[str], hash_pool: list[str] | None
    ) -> str:
        """Compute a string representation of a qualifier.

        :param value: the effective value associated with the qualifier
        :param hash_pool: if not None and repr_in_hash is True, the represantion
            is added to that list. The list is used then to compute a hash and
            thus reduce the build space length.
        :return: the qualifier representation if self.repr_in_hash is False
            or hash_pool is None. if hash_pool is not None and self.repr_in_hash
            is True, the string representation is appended to hash_pool and the
            method returns the empty string.
        """


class KeyValueDeclaration(QualifierDeclaration):
    def __init__(
        self,
        origin: str,
        name: str,
        description: str,
        repr_in_hash: bool = False,
        repr_name: str | None = None,
        repr_omit_key: bool = False,
        default: str | None = None,
        choices: list[str] | None = None,
    ) -> None:
        """Initialize a key-value qualifier declaration.

        :param origin: a string giving the origin of the declaration
            (used in error messages)
        :param name: see QualifierDeclaration.__init__
        :param description: see QualifierDeclaration.__init__
        :param repr_in_hash: see QualifierDeclaration.__init__
        :param repr_name: see QualifierDeclaration.__init__
        :param repr_omit_key: if True discard qualifier name in string representation
        :param default: default value for the qualifier
        :param choices: list of valid value for the qualifier
        """
        super().__init__(
            origin=origin,
            name=name,
            description=description,
            repr_in_hash=repr_in_hash,
            repr_name=repr_name,
        )
        self.repr_omit_key = repr_omit_key

        # Check that default value is valid
        if default is not None and choices is not None and default not in choices:
            choices_str = ", ".join((f"'{choice}'" for choice in choices))
            raise AnodError(
                f"{self.origin}: default value '{default}' "
                f"should be in ({choices_str})."
            )

        self.choices = choices
        self._default = default

    @property
    def default(self) -> str | bool | frozenset[str] | None:
        """See QualifierDeclaration.default."""
        return self._default

    def value(
        self, value: str | bool | Iterable[str] | None
    ) -> str | bool | frozenset[str]:
        """See QualifierDeclaration.value."""
        # Temporary until full switch to dict
        if isinstance(value, bool):
            value = ""

        if not isinstance(value, str):
            raise AnodError(
                f"{self.origin}: Invalid value for qualifier {self.name}: "
                f"requires a str value, got {type(value)}({value})"
            )

        if self.choices is not None and value not in self.choices:
            choices_str = ", ".join((f"'{choice}'" for choice in self.choices))
            raise AnodError(
                f"{self.origin}: Invalid value for qualifier {self.name}: '{value}' "
                f"not in ({choices_str})"
            )
        return value

    def repr(
        self, value: str | bool | frozenset[str], hash_pool: list[str] | None
    ) -> str:
        """See QualifierDeclaration.repr."""
        if not value:
            # An empty value for a key_value qualifier should lead to an empty
            # representation
            str_repr = ""
        elif (
            value == self.default
            and self.choices is not None
            and "" not in self.choices
        ):
            # In the case the value of qualifier is a finite set and
            # that "" is not in that set, if value is the default value then
            # just return an empty representation.
            str_repr = ""
        else:
            # Otherwise compute components of the representation.
            list_repr = []
            if not self.repr_omit_key:
                list_repr.append(self.repr_name)

            # value as been checked early on
            list_repr.append(str(value))

            # And join them with a dash.
            str_repr = "-".join(list_repr)

        if hash_pool is not None and self.repr_in_hash:
            if str_repr:
                hash_pool.append(str_repr)
            return ""
        else:
            return str_repr


class TagDeclaration(QualifierDeclaration):
    """Tag qualifier declaration."""

    @property
    def default(self) -> str | bool | frozenset[str] | None:
        """See QualifierDeclaration.value."""
        return False

    def value(
        self, value: str | bool | Iterable[str] | None
    ) -> str | bool | frozenset[str]:
        """See QualifierDeclaration.value."""
        # As soon as a tag qualifier is passed, its value is True
        if isinstance(value, str):
            return True
        elif value is None:
            return True
        elif isinstance(value, bool):
            return value
        else:
            raise AnodError(
                f"{self.origin}: Invalid value for qualifier {self.name}: "
                f"requires a str, bool or None value, got {type(value)}({value})"
            )

    def repr(
        self, value: str | bool | frozenset[str], hash_pool: list[str] | None
    ) -> str:
        """See QualifierDeclaration.repr."""
        if hash_pool is not None and self.repr_in_hash:
            if value:
                hash_pool.append(self.repr_name)
            return ""
        elif value:
            return self.repr_name
        else:
            return ""


class KeySetDeclaration(QualifierDeclaration):
    # The separator use to distinguish all the element of the list
    LIST_SEPARATOR = ";"

    def __init__(
        self,
        origin: str,
        name: str,
        description: str,
        repr_in_hash: bool = False,
        repr_name: str | None = None,
        repr_omit_key: bool = False,
        default: set[str] | None = None,
        choices: list[str] | None = None,
    ) -> None:
        """Initialize a key-set qualifier declaration.

        :param origin: a string giving the origin of the declaration
            (used in error messages)
        :param name: see QualifierDeclaration.__init__
        :param description: see QualifierDeclaration.__init__
        :param repr_in_hash: see QualifierDeclaration.__init__
        :param repr_name: see QualifierDeclaration.__init__
        :param repr_omit_key: if True discard qualifier name in string representation
        :param default: default value for the qualifier
        :param choices: list of valid value for the qualifier
        """
        super().__init__(
            origin=origin,
            name=name,
            description=description,
            repr_in_hash=repr_in_hash,
            repr_name=repr_name,
        )
        self.repr_omit_key = repr_omit_key

        # Check if the default is valid
        if default is not None and choices is not None:
            wrong_values = default - set(choices)
            if wrong_values:
                choices_str = ", ".join((f"'{choice}'" for choice in choices))
                wrong_values_str = ", ".join(
                    (f"'{value}'" for value in sorted(wrong_values))
                )
                raise AnodError(
                    f"{self.origin}: In '{self.name}', default value(s) "
                    f"({wrong_values_str}) should be in ({choices_str})"
                )

        self.choices = choices
        self._default: frozenset[str] | None = (
            frozenset(default) if default is not None else None
        )

    @property
    def default(self) -> str | bool | frozenset[str] | None:
        """See QualifierDeclaration.default."""
        return self._default

    def value(
        self, value: str | bool | Iterable[str] | None
    ) -> str | bool | frozenset[str]:
        """See QualifierDeclaration.value."""
        if isinstance(value, bool):
            raise AnodError(
                f"{self.origin}: Invalid value for qualifier {self.name}: "
                f"requires a str or Iterable[str], got bool"
            )
        elif value is None:
            raise AnodError(
                f"{self.origin}: Invalid value for qualifier {self.name}: "
                f"requires a str or Iterable[str], got None"
            )
        elif isinstance(value, str):
            # Make sure '' value is the empty set
            value_set = (
                frozenset(value.split(self.LIST_SEPARATOR)) if value else frozenset({})
            )
        else:
            try:
                result = all((isinstance(el, str) for el in value))
                if not result:
                    raise AnodError(
                        f"{self.origin}: Invalid value for qualifier {self.name}: "
                        f"one of the element in the Iterable is not a str: "
                        f"got {type(value)}({value})"
                    )
            except TypeError as e:

                raise AnodError(
                    f"{self.origin}: Invalid value for qualifier {self.name}: "
                    f"requires a str or Iterable[str], "
                    f"got {type(value)}({value})"
                ) from e

            value_set = frozenset(value)

        # Check if the values are in choices
        if self.choices:
            wrong_values = value_set - set(self.choices)

            if wrong_values:
                choices_str = ", ".join((f"'{choice}'" for choice in self.choices))
                wrong_values_str = ", ".join(
                    (f"'{value}'" for value in sorted(wrong_values))
                )
                raise AnodError(
                    f"{self.origin}: Invalid value(s) for qualifier {self.name}: "
                    f"({wrong_values_str}) not in ({choices_str})"
                )

        return value_set

    def repr(
        self, value: str | bool | frozenset[str], hash_pool: list[str] | None
    ) -> str:
        """See QualifierDeclaration.repr."""
        assert isinstance(value, frozenset)
        if not value:
            # An empty value for key_set qualifier should lead to an empty
            # representation
            str_repr = ""
        else:
            # Otherwise compute components of the representation.
            list_repr = []
            if not self.repr_omit_key:
                list_repr.append(self.repr_name)
            list_repr.extend((str(v) for v in sorted(value)))

            # And join them with a dash.
            str_repr = "-".join(list_repr)

        if hash_pool is not None and self.repr_in_hash:
            if str_repr:
                hash_pool.append(str_repr)
            return ""
        else:
            return str_repr


class QualifiersManager:
    """Parse the qualifiers and build an unique name.

    This class is used to manage the qualifiers, declare the components and generate
    the components and build_space names.

    The qualifiers must all be declared using the declare_tag_qualifier or
    declare_key_value_qualifier method to be usable in the spec. The declaration is a
    way for the spec (i.e. the QualifiersManager) to know which are the authorized
    qualifiers and how to use them (default values...).

    'key_value' qualifiers are qualifiers associated with a value. For example,
    'version' is likely to have a value (the actual version number) and thus would be
    declared as a 'key_value' qualifier.

    A 'tag' qualifier has no value. More precisely, its value is True when the
    qualifier is passed to spec and False otherwise.

    The component must also be declared using the declare_component method.
    The 'component' is the name of the Cathod entry related to the spec
    (None if it has no entry). A component is bound to a particular configuration of
    qualifiers (set of pair qualifier/value). If the current qualifier configuration
    has been bound to a component then this name is used for both the build_space name
    and the component name. Otherwise, the component name is None (there is no
    component to be uploaded in Cathod)

    This class is also used to generate the build_space name. The build_space name is
    computed using all the declared qualifiers and their values (at runtime).
    This allow the build_space names to be different for each different builds
    (assuming that different build <=> different set of qualifier values).
    """

    def __init__(
        self,
        anod_instance: Anod,
    ) -> None:
        """Initialize a QualifiersManager instance.

        :param anod_instance: the current anod instance.
        """
        self.anod_instance = anod_instance
        self.origin = f"{anod_instance.kind}(name={anod_instance.name})"

        # Hold all the declared qualifiers. The keys are the qualifier names and the
        # values the qualifier properties.
        self.qualifier_decls: dict[str, QualifierDeclaration] = {}

        # Hold all the declared components as stated by the user. They still need
        # to be checked and prepared (add the default values...) before being actually
        # usable. The keys are the components names and the values are the dictionary
        # representing the corresponding qualifier configuration.
        self.component_decls: dict[str, tuple[dict[str, str], bool]] = {}

        # Hold the declared components. The keys are the qualifier configurations
        # (tuples) and the value are the component names.
        # It is construct by end_declaration_phase using raw_component_decls.
        self.component_names: dict[
            tuple[tuple[str, str | bool | frozenset[str]], ...], str
        ] = {}
        self.build_space_names: dict[
            tuple[tuple[str, str | bool | frozenset[str]], ...], str
        ] = {}

        # Hold the final qualifier values for anod_instance.
        self.qualifier_values: dict[str, str | bool | frozenset[str]] = {}

        # When the first name has been generated it is no longer possible to add
        # neither new qualifiers nor new components.
        self.is_declaration_phase_finished: bool = False

        # The base name to be used by the name generator
        self.base_name: str = self.anod_instance.base_name

        # By default component and build_space_name are None
        self.component: str | None = None
        self.build_space_name: str = ""

        # The call back function to handle aliases of os_versions and machines
        self.machine_aliases: dict[str, str] = {}
        self.os_version_aliases: dict[str, str] = {}
        self.add_target_info_to_bs = False

    def add_target_info(
        self,
        machine_aliases: dict[str, str] | None = None,
        os_version_aliases: dict[str, str] | None = None,
    ) -> None:
        """Enable target os information in build space name computation.

        Note that target information is added only if in a cross context.

        :param machine_aliases: aliases for server name. Can be used to shorten
            build space name
        :param os_version_aliases: aliases for OS versions. Can be used to shorten
            build space name
        """
        if self.is_declaration_phase_finished:
            raise AnodError(
                f"{self.origin}: build space name computation settings can only "
                "be changed in 'declare_qualifiers_and_components'"
            )

        self.add_target_info_to_bs = True
        if os_version_aliases:
            self.os_version_aliases.update(os_version_aliases)
        if machine_aliases:
            self.machine_aliases.update(machine_aliases)

    def remove_target_info(self) -> None:
        """Disable target os information in build space name computation."""
        if self.is_declaration_phase_finished:
            raise AnodError(
                f"{self.origin}: build space name computation settings can only "
                "be changed in 'declare_qualifiers_and_components'"
            )

        self.add_target_info_to_bs = False

    def declare_tag_qualifier(
        self,
        name: str,
        description: str,
        test_only: bool = False,
        repr_alias: str | None = None,
        repr_in_hash: bool = False,
    ) -> None:
        """Declare a new tag qualifier.

        Declare a tag qualifier to allow it use in the spec. It will have an impact on
        the build_space and component names.

        A tag qualifier is a qualifier with an implicit value. Their value is True if
        the qualifier is passed at runtime and False else.

        This method cannot be called after the end of the declaration phase.

        :param name: The name of the qualifier. It used to identify it and pass it to
            the spec.
        :param description: A description of the qualifier purposes. It is used to
            make the help/error clearer.
        :param test_only: By default the qualifier are used by all anod actions
            (install, build, test...). If test_only is True, then this qualifier is
            only available for test.
        :param repr_alias: An alias for the qualifier name used by the name generation.
            By default, the repr_alias is the qualifier name itself.
        :param repr_in_hash: False by default. If True, the qualifier is included in
         the hash at the end of the generated name. The result is less readable but
         shorter.
        """
        if self.is_declaration_phase_finished:
            raise AnodError(
                f"{self.origin}: qualifier can only be declared in "
                "declare_qualifiers_and_components"
            )

        if not test_only or self.anod_instance.kind == "test":
            self.qualifier_decls[name] = TagDeclaration(
                origin=self.origin,
                name=name,
                description=description,
                repr_name=repr_alias,
                repr_in_hash=repr_in_hash,
            )

    def declare_key_value_qualifier(
        self,
        name: str,
        description: str,
        test_only: bool = False,
        default: str | None = None,
        choices: list[str] | None = None,
        repr_alias: str | None = None,
        repr_in_hash: bool = False,
        repr_omit_key: bool = False,
    ) -> None:
        """Declare a new key value qualifier.

        Declare a key value qualifier to allow it use in the spec. It will have an
        impact on the build_space and component names.

        A key value qualifier is a 'standard' qualifier. They require the user to
        provide their value.

        This method cannot be called after the end of the declaration phase.

        :param name: The name of the qualifier. It used to identify it and pass it to
            the spec.
        :param description: A description of the qualifier purposes. It is used to
            make the help/error clearer.
        :param test_only: By default the qualifier are used by all anod actions
            (install, build, test...). If test_only is True, then this qualifier is
            only available for test.
        :param default: The default value given to the qualifier if no value was
            provided by the user. If no default value is set, then the user must
            provide a qualifier value at runtime.
        :param choices: The list of all authorized values for the qualifier.
        :param repr_alias: An alias for the qualifier name used by the name generation.
            By default, the repr_alias is the qualifier name itself.
        :param repr_in_hash: False by default. If True, the qualifier is included in
            the hash at the end of the generated name. The result is less readable but
            shorter.
        :param repr_omit_key: If True, then the name generation don't display the
            qualifier name/alias. It only use its value.
        """
        if self.is_declaration_phase_finished:
            raise AnodError(
                f"{self.origin}: qualifier can only be declared in "
                " declare_qualifiers_and_components"
            )
        if not test_only or self.anod_instance.kind == "test":
            self.qualifier_decls[name] = KeyValueDeclaration(
                origin=self.origin,
                name=name,
                description=description,
                repr_name=repr_alias,
                repr_in_hash=repr_in_hash,
                default=default,
                choices=choices,
                repr_omit_key=repr_omit_key,
            )

    def declare_key_set_qualifier(
        self,
        name: str,
        description: str,
        test_only: bool = False,
        default: set[str] | None = None,
        choices: list[str] | None = None,
        repr_alias: str | None = None,
        repr_in_hash: bool = False,
        repr_omit_key: bool = False,
    ) -> None:
        """Declare a new key set qualifier.

        Declare a key set qualifier to allow it use in the spec. It will have an
        impact on the build_space and component names.

        A key set qualifier is a 'list' qualifier. They require the user to
        provide their values as a semi-colon separated list.

        This method cannot be called after the end of the declaration phase.

        :param name: The name of the qualifier. It used to identify it and pass it to
            the spec.
        :param description: A description of the qualifier purposes. It is used to
            make the help/error clearer.
        :param test_only: By default the qualifier are used by all anod actions
            (install, build, test...). If test_only is True, then this qualifier is
            only available for test.
        :param default: The default value given to the qualifier if no value was
            provided by the user. If no default value is set, then the user must
            provide a qualifier value at runtime.
        :param choices: The list of all authorized values for the qualifier.
        :param repr_alias: An alias for the qualifier name used by the name generation.
            By default, the repr_alias is the qualifier name itself.
        :param repr_in_hash: False by default. If True, the qualifier is included in
            the hash at the end of the generated name. The result is less readable but
            shorter.
        :param repr_omit_key: If True, then the name generation don't display the
            qualifier name/alias. It only use its value.
        """
        if self.is_declaration_phase_finished:
            raise AnodError(
                f"{self.origin}: qualifier can only be declared in "
                " declare_qualifiers_and_components"
            )

        # Make sure {} is read as the empty set
        if default == {}:
            default = set({})

        # Make sure the default is None or a set as key_set qualifier are not used the
        # same way as the more standard key_value qualifier
        if default is not None and not isinstance(default, set):
            raise AnodError(
                "The default of key_set qualifier must be either None or a set"
            )

        if not test_only or self.anod_instance.kind == "test":
            self.qualifier_decls[name] = KeySetDeclaration(
                origin=self.origin,
                name=name,
                description=description,
                repr_name=repr_alias,
                repr_in_hash=repr_in_hash,
                default=default,
                choices=choices,
                repr_omit_key=repr_omit_key,
            )

    def declare_component(
        self,
        name: str,
        required_qualifier_configuration: dict[str, str],
    ) -> None:
        """Declare a new component.

        A component is bound to a qualifier configuration (i.e. a dictionary mapping
        the qualifiers to their values as provided by the user at runtime). The
        provided component name is used if the qualifier meet the provided qualifier
        values.

        This method cannot be called after the end of the declaration phase.

        :param name: A string representing the component name.
        :param required_qualifier_configuration: The dictionary of qualifiers
            value corresponding to the build linked to the component.
        """
        if self.anod_instance.kind != "test":
            # Components have meaning only for build and install
            return self.declare_build_space_name(
                name=name,
                required_qualifier_configuration=required_qualifier_configuration,
                has_component=True,
            )

    def declare_build_space_name(
        self,
        name: str,
        required_qualifier_configuration: dict[str, str],
        has_component: bool = False,
    ) -> None:
        """Declare a new component.

        A component is bound to a qualifier configuration (i.e. a dictionary mapping
        the qualifiers to their values as provided by the user at runtime). The
        provided component name is used if the qualifier meet the provided qualifier
        values.

        This method cannot be called after the end of the declaration phase.

        :param name: A string representing the component name.
        :param required_qualifier_configuration: The dictionary of qualifiers
            value corresponding to the build linked to the component.
        """
        if self.is_declaration_phase_finished:
            raise AnodError(
                f"{self.origin}: component/build space can only be declared in "
                "declare_qualifiers_and_components"
            )

        self.component_decls[
            check_valid_name(
                name, value_kind="component declaration name", origin=self.origin
            )
        ] = (
            required_qualifier_configuration,
            has_component,
        )

    def compute_qualifier_values(
        self,
        qualifier_dict: dict[str, str],
    ) -> dict[str, str | bool | frozenset[str]]:
        """Given a user qualifier dict compute and validate final values.

        :param qualifier_dict: User qualifiers
        :return: the computed qualifier values (applying default and validity checks).
        """
        # Initialize the result with the default values
        result = {
            qual.name: qual.default
            for qual in self.qualifier_decls.values()
            if qual.default is not None
        }

        # Check that all qualifiers passed by the user are declared. Note that if we
        # have in qualifier_dict an entry with key is the null string we ignore it.
        # This case can occurs when the qualifier string contains additionals commas.
        invalid_keys = {k for k in qualifier_dict if k} - set(
            self.qualifier_decls.keys()
        )
        if invalid_keys:
            invalid_keys_str = ", ".join(invalid_keys)
            error_msg = f"{self.origin}: Invalid qualifier(s): {invalid_keys_str}\n"

            if self.qualifier_decls:
                probable_qualifiers = [
                    repr(
                        get_close_matches(
                            key, self.qualifier_decls.keys(), n=1, cutoff=0
                        )[0]
                    )
                    for key in invalid_keys
                ]
                if len(probable_qualifiers) == 1:
                    error_msg += f"Did you mean {probable_qualifiers[0]}?\n"
                else:
                    error_msg += (
                        f"Did you mean {', '.join(probable_qualifiers[:-1])} or "
                        f"{probable_qualifiers[-1]}?\n"
                    )

            error_msg += (
                f"Use `anod help {self.anod_instance.name}` to get a list of valid "
                "qualifiers"
            )

            raise AnodError(error_msg)

        # Update default dict with user values
        result.update(
            {
                name: self.qualifier_decls[name].value(value)
                for name, value in qualifier_dict.items()
                if name
            }
        )

        # Check that all values are defined
        missing_keys = set(self.qualifier_decls.keys()) - set(result.keys())
        if missing_keys:
            missing_keys_str = ", ".join(missing_keys)
            raise AnodError(f"{self.origin}: Missing qualifier(s): {missing_keys_str}")

        return result

    def serialize_qualifier_values(
        self, qualifier_values: dict[str, str | bool | frozenset[str]]
    ) -> tuple[tuple[str, str | bool | frozenset[str]], ...]:
        """Return a hashable and deterministic representation of qualifier values.

        :param qualifier_values: qualifier values as returned by
            compute_qualifier_values
        :return: a tuple of couple (key, value) sorted by key
        """
        return tuple(sorted(qualifier_values.items()))

    def parse(self, user_qualifiers: dict[str, str]) -> None:
        """Parse the provided qualifiers.

        This function first makes sure that all the user_qualifiers
        follow the rules:
        * Have been declared.
        * Set a value if they don't have a default one.
        * Have a value which respect the choices attribute.

        After the first call to this method, it is no longer possible to declare new
        component nor qualifier. This ensure the consistency of the generated names.

        After the call to parse, the qualifier_values are available using
        __getparsed_qualifiers.

        :param user_qualifiers: a dictionary containing the passed qualifier
            values.
        """
        # End the declaration phase to guaranty the consistency of the result
        self.is_declaration_phase_finished = True
        self.origin = (
            f"{self.anod_instance.kind}"
            f"(name={self.anod_instance.name}, qual={user_qualifiers})"
        )
        # Compute and validate final qualifier values
        self.qualifier_values = self.compute_qualifier_values(user_qualifiers)
        self.serialized_qualifier_values = self.serialize_qualifier_values(
            self.qualifier_values
        )

        # Compute component and build space names
        for component_name, component_decl in self.component_decls.items():
            qualifiers, has_component = component_decl
            try:
                qualifier_values = self.serialize_qualifier_values(
                    self.compute_qualifier_values(qualifiers)
                )
            except AnodError as e:
                raise AnodError(
                    f"{self.origin}: Invalid qualifier state {qualifiers} "
                    f"for build space/component {component_name}"
                ) from e

            if qualifier_values in self.component_names:
                raise AnodError(
                    f"{self.origin}: state {qualifiers} reused for "
                    "several build spaces/components"
                )

            if has_component:
                self.component_names[qualifier_values] = component_name
            self.build_space_names[qualifier_values] = component_name

        # Compute the final build space name
        self.compute_build_space_name()

        # Compute the final component name
        self.component = self.component_names.get(self.serialized_qualifier_values)

    def compute_build_space_name(self) -> None:
        """Compute the final build_space_name.

        Aggregate the build_space name. It is made of four parts:
        base + qualifier_suffix + hash + test

         * base: The component_prefix or, by default, the spec name.
         * qualifier_suffix: The concatenation of the contribution of
            all qualifiers.
         * hash: The hash of the aggregation of all qualifiers marked with
            'repr_in_hash'.
         * test: '-test' if the current anod primitive is test.

        If the generated component is not None, then use it for consistency reason.
        """
        # Check if we have manual build space
        manual_build_space_name = self.build_space_names.get(
            self.serialized_qualifier_values
        )
        if manual_build_space_name is not None:
            self.build_space_name = manual_build_space_name
            return

        # This is an automatic build space name
        hash_pool: list[str] = []
        bs = [self.base_name]
        bs += [
            self.qualifier_decls[el[0]].repr(el[1], hash_pool=hash_pool)
            for el in self.serialized_qualifier_values
        ]
        if hash_pool:
            hash_obj = sha1()  # nosec
            hash_obj.update("_".join(hash_pool).encode("utf-8"))
            bs.append(hash_obj.hexdigest()[:8])

        if self.add_target_info_to_bs and self.anod_instance.env.is_cross:
            # We can run test on many different cross OS version
            # from the same host machine, make sure that we have a
            # different build space each time
            os_version = self.anod_instance.env.target.os.version
            if os_version and os_version != "unknown":
                bs.append(self.os_version_aliases.get(os_version, os_version))
            # We also can test on different machines, so add it as well
            machine = self.anod_instance.env.target.machine
            if machine and machine != "unknown":
                # and make sure the machine name is compatible with
                # file paths: only keep letters, numbers and dashes
                machine_str = "".join([c for c in machine if c.isalnum() or c == "-"])
                bs.append(self.machine_aliases.get(machine, machine_str))

        if self.anod_instance.kind == "test":
            bs.append("test")

        self.build_space_name = "_".join([el for el in bs if el])

    def __getitem__(self, key: str) -> str | bool | frozenset[str]:
        """Return the parsed value of the requested qualifier.

        :return: The qualifier value after the parsing.
        """
        return self.qualifier_values[key]
