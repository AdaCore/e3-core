from __future__ import annotations

from typing import TYPE_CHECKING, cast
from hashlib import sha1

from e3.anod.error import AnodError

import string

if TYPE_CHECKING:
    from typing import (
        Literal,
        TypedDict,
    )
    from e3.anod.spec import Anod

    # Declare types
    TAG_QUALIFIER_TYPE = Literal["tag"]
    KEY_VALUE_QUALIFIER_TYPE = Literal["key-value"]

    class QualifierDeclaration(TypedDict):
        # Fields common to all qualifiers
        description: str
        test_only: bool
        repr_in_hash: bool
        repr_alias: str

    class QualifierTagDeclaration(QualifierDeclaration):
        type: Literal["tag"]

    class QualifierKeyValueDeclaration(QualifierDeclaration):
        type: Literal["key-value"]

        # Fields specific to key-value qualifiers
        default: str | None
        choices: list[str] | None
        repr_omit_key: bool


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

    # Declare the qualifier types
    __TAG_QUALIFIER: TAG_QUALIFIER_TYPE = "tag"
    __KEY_VALUE_QUALIFIER: KEY_VALUE_QUALIFIER_TYPE = "key-value"

    def __init__(
        self,
        anod_instance: Anod,
    ) -> None:
        """Initialize a QualifiersManager instance.

        :param anod_instance: the current anod instance.
        """
        self.anod_instance = anod_instance

        # Hold all the declared qualifiers. The keys are the qualifier names and the
        # values the qualifier properties.
        self.qualifier_decls: dict[
            str,
            QualifierTagDeclaration | QualifierKeyValueDeclaration,
        ] = {}

        # Hold all the declared components as stated by the user. They still needs
        # to be checked and prepared (add the default values...) before being actually
        # usable. The keys are the components names and the values are the dictionary
        # representing the corresponding qualifier configuration.
        self.raw_component_decls: dict[str, dict[str, str]] = {}

        # Hold the declared components. The keys are the qualifier configurations
        # (tuples) and the value are the component names.
        # It is construct by end_declaration_phase using raw_component_decls.
        self.component_names: None | dict[
            tuple[tuple[str, str | bool], ...], str
        ] = None

        # Hold the current (i.e. parsed) qualifier's values.
        self.qualifier_values: None | dict[str, str | bool] = None

        # When the first name has been generated it is no longer possible to add
        # neither new qualifiers nor new components.
        self.is_declaration_phase_finished: bool = False

        # Hold all the qualifiers suffixes to be added in the final hash
        self.hash_pool = ""

        # The base name to be used by the name generator
        self.base_name: str = self.anod_instance.base_name

    def __init_qualifier(
        self,
        name: str,
        description: str,
        qualifier_type: TAG_QUALIFIER_TYPE | KEY_VALUE_QUALIFIER_TYPE,
        test_only: bool = False,
        default: str | None = None,
        choices: list[str] | None = None,
        repr_alias: str | None = None,
        repr_in_hash: bool = False,
        repr_omit_key: bool = False,
    ) -> QualifierTagDeclaration | QualifierKeyValueDeclaration:
        """Initialize a new qualifier.

        This function is for internal use only and initialize a qualifier.

        Return a valid qualifier whose type depends on the type parameter.

        :param name: The name of the qualifier. It used to identify it and pass it to
            the spec.
        :param description: A description of the qualifier purposes. It is used to
            make the help/error clearer.
        :param qualifier_type: The type of the qualifier. Either tag or key value.
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
        :return: A valid qualifier.
        """
        if self.is_declaration_phase_finished:
            raise AnodError(
                "The qualifier declaration is finished. It is not possible to declare a"
                " new qualifier after a component has been declared or a name generated"
            )

        # Check all the inputs.

        # Check name:
        name = name.strip()
        if not name:
            raise AnodError("The qualifier name cannot be empty")
        elif name in self.qualifier_decls:
            raise AnodError(f"The {name} qualifier has already been declared")

        # Check description:
        description = description.strip()
        if not description:
            raise AnodError(f"The {name} qualifier description cannot be empty")

        # Check repr_alias:
        alias: str = name if repr_alias is None else repr_alias.strip()
        if not alias:
            raise AnodError(f"The {name} qualifier repr_alias cannot be empty")

        if qualifier_type == self.__KEY_VALUE_QUALIFIER:
            new_key_value_qualifier: QualifierKeyValueDeclaration = {
                "description": description,
                "test_only": test_only,
                "repr_alias": alias,
                "repr_in_hash": repr_in_hash,
                "type": self.__KEY_VALUE_QUALIFIER,
                "default": default,
                "choices": choices,
                "repr_omit_key": repr_omit_key,
            }

            # Make sure the default value is valid (is in choices)
            if (
                new_key_value_qualifier["default"] is not None
                and new_key_value_qualifier["choices"] is not None
                and new_key_value_qualifier["default"]
                not in new_key_value_qualifier["choices"]
            ):
                raise AnodError(
                    f"The {name} qualifier default value "
                    f'"{new_key_value_qualifier["default"]}" not in '
                    f'{new_key_value_qualifier["choices"]}'
                )

            return new_key_value_qualifier
        else:
            new_tag_qualifier: QualifierTagDeclaration = {
                "description": description,
                "test_only": test_only,
                "repr_alias": alias,
                "repr_in_hash": repr_in_hash,
                "type": self.__TAG_QUALIFIER,
            }

        return new_tag_qualifier

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
        new_tag_qualifier = self.__init_qualifier(
            name=name,
            description=description,
            qualifier_type=self.__TAG_QUALIFIER,
            test_only=test_only,
            repr_alias=repr_alias,
            repr_in_hash=repr_in_hash,
        )

        self.qualifier_decls[name] = new_tag_qualifier

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
        new_key_value_qualifier = self.__init_qualifier(
            name=name,
            description=description,
            qualifier_type=self.__KEY_VALUE_QUALIFIER,
            test_only=test_only,
            repr_alias=repr_alias,
            repr_in_hash=repr_in_hash,
            default=default,
            choices=choices,
            repr_omit_key=repr_omit_key,
        )

        self.qualifier_decls[name] = new_key_value_qualifier

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
        if self.is_declaration_phase_finished:
            raise AnodError(
                "The component declaration is finished. It is not possible to declare a"
                " new component after a name has been generated"
            )

        # Check name
        valid_char = string.ascii_letters + string.digits + "-_."
        if any(c not in valid_char for c in name):
            raise AnodError(
                f'The component name "{name}" contains an invalid character'
            )

        # Make sure the name has not been used yet
        if name in self.raw_component_decls:
            raise AnodError(f'The "{name}" component names is already used')

        self.raw_component_decls[name] = required_qualifier_configuration

    def __force_default_values(
        self,
        qualifier_dict: dict[str, str],
        ignore_test_only: bool = False,
    ) -> dict[str, str | bool]:
        """Force the default value of the qualifiers.

        If a key_value qualifier with a default value is not in the qualifier_dict
        dictionary. Then, the qualifier will be added to qualifier_dict with its
        default value as value.

        The tag qualifier values are set to True is the qualifier is present and False
        else.

        This function cannot be called before the end of the declaration phase.

        :param qualifier_dict: The dictionary of qualifiers for which the default
            values are required.
        :param ignore_test_only: If set to True, the qualifier marked as test_only are
            completely ignored
        """
        if not self.is_declaration_phase_finished:
            raise AnodError(
                "The default values cannot be added before the end of the declaration "
                "phase"
            )

        qualifier_dict_with_default: dict[str, str | bool] = cast(
            "dict[str, str | bool]", qualifier_dict.copy()
        )

        # Add the required default values
        for qualifier_name, qualifier in self.qualifier_decls.items():
            # Ignore test_only qualifier if needed
            if qualifier["test_only"] and ignore_test_only:
                continue

            if qualifier["type"] == self.__KEY_VALUE_QUALIFIER:
                if qualifier_name not in qualifier_dict:
                    # The qualifier must have a default. This is checked by
                    # __check_qualifier_consistency
                    assert qualifier["default"] is not None
                    qualifier_dict_with_default[qualifier_name] = qualifier["default"]
            elif qualifier["type"] == self.__TAG_QUALIFIER:
                qualifier_dict_with_default[qualifier_name] = (
                    qualifier_name in qualifier_dict
                )
            else:
                raise AnodError(
                    "An expected qualifier type was encountered during parsing "
                    f'Got "{qualifier["type"]}"'
                )

        return qualifier_dict_with_default

    def __check_qualifier_consistency(
        self,
        qualifier_configuration: dict[str, str],
        ignore_test_only: bool = False,
    ) -> None:
        """Check that the qualifiers are compliant with their declarations.

        Ensure that all the qualifiers follow the rules:
         * Have been declared.
         * Set a value if they don't have a default one.
         * Have a value which respect the choices attribute.

        :param qualifier_configuration: A dictionary of qualifiers to be checked.
            The key are the qualifiers names and the values the qualifier values.
        :param ignore_test_only: If set to True, the qualifier marked as test_only are
            completely ignored
        """
        # The declaration phase must be finished to ensure the consistency of the result
        if not self.is_declaration_phase_finished:
            raise AnodError(
                "The qualifier consistency cannot be checked before the end of the "
                "declaration phase"
            )

        for qualifier_name, qualifier_value in qualifier_configuration.items():
            # The qualifier has been declared
            if qualifier_name not in self.qualifier_decls:
                self.__error(
                    f'The qualifier "{qualifier_name}" is used but has '
                    "not been declared"
                )

            qualifier = self.qualifier_decls[qualifier_name]

            # Ignore the test_only qualifier if needed
            if ignore_test_only and qualifier["test_only"]:
                continue

            # If the qualifier is test_only and the current anod kind is not test,
            # raise an error.
            if qualifier["test_only"] and self.anod_instance.kind != "test":
                self.__error(
                    f"The qualifier {qualifier_name} is test_only but the current anod "
                    f"kind is {self.anod_instance.kind}"
                )

            if qualifier["type"] == self.__KEY_VALUE_QUALIFIER:
                # A key-value qualifier cannot be passed without a value.
                if not qualifier_value:
                    self.__error(
                        f'The key-value qualifier "{qualifier_name}" must be passed '
                        "with a value"
                    )

                # If choices exist then the qualifier value is constrained.
                if qualifier["choices"] is not None:
                    if qualifier_value not in qualifier["choices"]:
                        self.__error(
                            f"The {qualifier_name} qualifier value must be in "
                            f'{qualifier["choices"]}. Got {qualifier_value}'
                        )
            elif qualifier["type"] == self.__TAG_QUALIFIER:
                # The tag qualifier cannot be passed with a value
                if qualifier_value:
                    self.__error(
                        f"The {qualifier_name} qualifier is a tag and does not expect "
                        f'any values. Got "{qualifier_value}"'
                    )
            else:
                raise AnodError(
                    "An expected qualifier type was encountered during parsing "
                    f'Got "{qualifier["type"]}"'
                )

        # Make sure all the declared qualifiers are stated
        for qualifier_name, qualifier in self.qualifier_decls.items():
            # Ignore test_only qualifier if needed
            if qualifier["test_only"] and (
                ignore_test_only or self.anod_instance.kind != "test"
            ):
                continue

            if qualifier["type"] == self.__KEY_VALUE_QUALIFIER:
                if qualifier_name not in qualifier_configuration:
                    # The qualifier must have a default otherwise it would not have
                    # any values.
                    if qualifier["default"] is None:
                        self.__error(
                            f"The {qualifier_name} qualifier was declared without a "
                            "default value but not passed"
                        )
            elif qualifier["type"] != self.__TAG_QUALIFIER:
                raise AnodError(
                    "An expected qualifier type was encountered during parsing "
                    f'Got "{qualifier["type"]}"'
                )

    def __qualifier_config_repr(
        self, qualifier_configuration: dict[str, str | bool]
    ) -> tuple[tuple[str, str | bool], ...]:
        """Transform a parsed qualifier dict into a hashable object.

        Ensure the returned key is unique and thus add the default
        value of the qualifiers. This theoretically adds no information but
        makes sure that implicit and explicit default values are handled the same way.

        Cannot be called before the end of the declaration phase.

        :param qualifier_configuration: A dictionary of qualifier. The keys are the
            qualifier names and the values are the corresponding qualifier values.
        :return: A tuple containing the same information as qualifier_configuration.
        """
        if not self.is_declaration_phase_finished:
            raise AnodError(
                "The function 'key' cannot be used before the end of the declaration "
                "phase"
            )

        return tuple(
            (k, qualifier_configuration[k]) for k in sorted(qualifier_configuration)
        )

    def __end_declaration_phase(self) -> None:
        """End the declaration of qualifiers and components.

        After the call to this function, it will no longer be possible to declare
        either new qualifiers nor new components.

        Check that all the declared components (the ones stored in raw_component_decls)
        are consistent with the declared qualifiers. Then, build the final list of
        components (component_names).
        """
        if self.is_declaration_phase_finished:
            # The declaration has already been ended
            pass
        else:
            # State that the declaration phase is finished
            self.is_declaration_phase_finished = True

            # Initialize component_names
            self.component_names = {}

            # Build component_names
            for component, qualifier_dict in self.raw_component_decls.items():
                # Add some context informations to the errors raised by
                # __check_qualifier_consistency to ease the debugging process.
                try:
                    self.__check_qualifier_consistency(
                        qualifier_dict,
                        ignore_test_only=True,
                    )
                except AnodError as e:
                    raise AnodError(f'In component "{component}": {str(e)}') from e

                # Make sure no test_only qualifier is used in a component definition
                for q in qualifier_dict:
                    if self.qualifier_decls[q]["test_only"]:
                        raise AnodError(
                            f'In component "{component}": The qualifier "{q}" is'
                            " test_only and cannot be used to define a component"
                        )

                qualifier_dict_with_default_values = self.__force_default_values(
                    qualifier_dict,
                    ignore_test_only=True,
                )

                qualifier_configuration = self.__qualifier_config_repr(
                    qualifier_dict_with_default_values
                )

                # Make sure the configuration has not been used yet
                if qualifier_configuration in self.component_names:
                    raise AnodError(
                        f"The qualifier configuration of {component} is already "
                        f"used by {self.component_names[qualifier_configuration]}"
                    )

                self.component_names[qualifier_configuration] = component

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
        self.__end_declaration_phase()

        # Check that the received user_qualifiers are valid according to the
        # declared qualifiers.
        self.__check_qualifier_consistency(user_qualifiers)

        # Add the default values
        self.qualifier_values = self.__force_default_values(
            user_qualifiers, ignore_test_only=self.anod_instance.kind != "test"
        )

    def __get_parsed_qualifiers(self) -> dict[str, str | bool]:
        """Return the parsed qualifier dictionary.

        Return the qualifier_values attribute. The keys of the dictionary are the
        qualifier names and the values are the qualifier values.

        This function cannot be called before the end of the declaration phase
        (i.e. before the call to parse)

        :return: A dictionary containing all the qualifier values once the parse
            procedure has been applied.
        """
        if not self.is_declaration_phase_finished:
            raise AnodError(
                "It is not possible to get the parsed passed qualifiers before the end "
                "of the declaration phase"
            )

        if self.qualifier_values is None:
            raise AnodError(
                "The parse method must be called first to generate qualifiers values"
            )

        return self.qualifier_values

    def __generate_qualifier_part(
        self,
        qualifier_name: str,
        parsed_qualifiers: dict[str, str | bool],
    ) -> str | None:
        """Return a string representing the qualifier for the name suffix.

        :return: A string or None:
            * str: The part of the name suffix due to the qualifier.
            * None: The qualifier is part of the final hash, its alias and values
            have been added to the has_pool attribute.
        """
        # Assuming that the qualifier has been declared.
        # In practice, this is checked by build_space_name before it call this function.
        qualifier = self.qualifier_decls[qualifier_name]

        # If the qualifier is test_only and the anod kind is not test then the
        # qualifier is ignored.
        if qualifier["test_only"] and self.anod_instance.kind != "test":
            return ""

        qualifier_value = parsed_qualifiers[qualifier_name]

        # Hold the part of the suffix induced by the qualifier.
        generated_suffix = ""

        alias = qualifier["repr_alias"]

        # Handle the hash.
        if qualifier["repr_in_hash"]:
            generated_suffix = f"_{alias}-{parsed_qualifiers[qualifier_name]}"
            self.hash_pool += generated_suffix
            return None

        # Handle tag qualifiers.
        if qualifier["type"] == self.__TAG_QUALIFIER:
            # The qualifier value is a boolean. True if the qualifier is used and
            # False else.
            if qualifier_value:
                return "_" + alias
            else:
                return ""
        elif qualifier["type"] == self.__KEY_VALUE_QUALIFIER:
            # Hint for mypy. It is a string for sure since the qualifier is key_value
            assert isinstance(qualifier_value, str)

            # Key-Value qualifiers has one more parameter:
            # * repr_omit_key

            if qualifier["repr_omit_key"]:
                return "_" + qualifier_value
            else:
                return "_" + qualifier_name + "-" + qualifier_value
        else:
            raise AnodError(
                "An expected qualifier type was encountered during parsing "
                f'Got "{qualifier["type"]}"'
            )

    @property
    def component(self) -> str | None:
        """Return the component name.

        If the current qualifier configuration correspond to a component name,
        then return this name, else return None.

        This function cannot be called before the end of the declaration phase
        (i.e. before the call to parse)

        :return: The component name.
        """
        if not self.is_declaration_phase_finished:
            raise AnodError(
                "It is not possible to build a component before the end of the "
                "declaration phase"
            )

        # Remove the test_only qualifier as they are not used for the component
        qualifier_configuration = {
            q: v
            for q, v in self.__get_parsed_qualifiers().items()
            if not self.qualifier_decls[q]["test_only"]
        }

        # This ensured by __end_declaration_phase
        assert self.component_names is not None
        return self.component_names.get(
            self.__qualifier_config_repr(qualifier_configuration)
        )

    @property
    def build_space_name(self) -> str:
        """Return the build_space name.

        Aggregate the build_space name. It is made of four parts:
        base + qualifier_suffix + hash + test

         * base: The component_prefix or, by default, the spec name.
         * qualifier_suffix: The concatenation of the contribution of
            all qualifiers.
         * hash: The hash of the aggregation of all qualifiers marked with
            'repr_in_hash'.
         * test: '_test' if the current anod primitive is test.

        If the generated component is not None, then use it for consistency reason.

        This function cannot be called before the end of the declaration phase
        (i.e. before the call to parse)

        :return: The build_space name.
        """
        if not self.is_declaration_phase_finished:
            raise AnodError(
                "It is not possible to build a build_space name before the end of the "
                "declaration phase"
            )

        component_name = self.component

        if component_name is not None and self.anod_instance.kind != "test":
            # A component name has been defined and must be used.
            return component_name

        parsed_qualifiers = self.__get_parsed_qualifiers()

        qualifier_suffix = ""
        hash_suffix = ""
        kind_suffix = "_test" if self.anod_instance.kind == "test" else ""

        qualifier_names_list = list(self.qualifier_decls)

        # Reset the hash_pool to let __generate_qualifier_part populates it
        self.hash_pool = ""

        # Aggregate qualifier_suffix
        # Ensure reproducibility sorting the qualifiers
        for qualifier_name in sorted(qualifier_names_list):
            suffix = self.__generate_qualifier_part(qualifier_name, parsed_qualifiers)

            if suffix is not None:
                # The qualifier part was not sent to the hash part
                qualifier_suffix += suffix

        # Compute hash_suffix
        if self.hash_pool:
            hash_suffix = f"_{sha1(self.hash_pool.encode()).hexdigest()[:8]}"

        return self.base_name + qualifier_suffix + hash_suffix + kind_suffix

    def __error(self, msg: str) -> None:
        """Raise an error and print the helper."""
        print(self.__get_helper())
        raise AnodError(msg)

    def __get_helper(self) -> str:
        """Return an helper for the current state of Qualifiers.

        :return: a string containing the helper.
        """
        helper_list = []
        if self.qualifier_decls == {}:
            return f"{self.anod_instance.name} does not accept any qualifiers."

        helper_list.append(
            f"{self.anod_instance.name} accept the following qualifiers:"
        )

        qualifier_part = []
        for qualifier_name, qualifier in self.qualifier_decls.items():
            test_only = "(test only) " if qualifier["test_only"] else ""
            key_value = (
                "=<value>" if qualifier["type"] == self.__KEY_VALUE_QUALIFIER else ""
            )

            qualifier_part.append(
                f'* {qualifier_name}{key_value} {test_only}: {qualifier["description"]}'
            )

            if qualifier["type"] == self.__KEY_VALUE_QUALIFIER:
                # Add informations about the default
                if qualifier["default"] is not None:
                    qualifier_part.append(f'   * default: {qualifier["default"]}')

                # Add informations about the choices
                if qualifier["choices"] is not None:
                    qualifier_part.append(f'   * choices: {qualifier["choices"]}')

        for line in qualifier_part:
            helper_list.append("    " + line)

        return "\n".join(helper_list)

    def __getitem__(self, key: str) -> str | bool:
        """Return the parsed value of the requested qualifier.

        :return: The qualifier value after the parsing.
        """
        return self.__get_parsed_qualifiers()[key]
