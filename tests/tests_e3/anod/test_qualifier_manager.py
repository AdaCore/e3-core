from e3.anod.error import AnodError
from e3.anod.qualifiers_manager import QualifiersManager
from e3.anod.spec import Anod

import pytest


# Cover Anod (e3.anod.spec.py)
def test_anod_name_generator():
    # Create a dummy spec.
    class Dummy(Anod):
        enable_name_generator = True

        name = "dummy"

    dummy = Dummy("", kind="build")
    assert dummy.build_space_name == "dummy"
    assert dummy.component is None

    # Create a simple spec
    class Simple(Anod):
        enable_name_generator = True

        base_name = "simple"

        def declare_qualifiers_and_components(self, qualifiers_manager):
            qualifiers_manager.declare_tag_qualifier(
                name="debug",
                description="simple description",
            )

    simple = Simple("", kind="build")
    assert simple.build_space_name == "simple"
    assert simple.component is None
    assert not simple.get_qualifier("debug")

    simple_debug = Simple("debug", kind="build")
    assert simple_debug.build_space_name == "simple_debug"
    assert simple_debug.component is None
    assert simple_debug.get_qualifier("debug")

    # Disable the name generator
    class Base(Anod):
        name = "dummy"

    base = Base("", kind="build")
    assert base.get_qualifier("debug") is None

    base = Base("debug=bar", kind="build")
    assert base.get_qualifier("debug") == "bar"


def test_qualifiers_manager_errors():
    class AnodDummy(Anod):
        enable_name_generator = True
        base_name = "dummy"

    anod_dummy = AnodDummy("", kind="build")

    # Add a qualifier after parse
    qualifiers_manager = QualifiersManager(anod_dummy)
    qualifiers_manager.parse(anod_dummy.parsed_qualifier)
    with pytest.raises(AnodError) as err:
        qualifiers_manager.declare_tag_qualifier(
            name="foo",
            description="bar",
        )
    assert str(err.value) == (
        "The qualifier declaration is finished. It is not possible to declare a new "
        "qualifier after a component has been declared or a name generated"
    )

    # Declare a new component after parse
    qualifiers_manager = QualifiersManager(anod_dummy)
    qualifiers_manager.parse(anod_dummy.parsed_qualifier)
    with pytest.raises(AnodError) as err:
        qualifiers_manager.declare_component(
            "foo",
            {},
        )
    assert str(err.value) == (
        "The component declaration is finished. It is not possible to declare a"
        " new component after a name has been generated"
    )

    # Add a qualifier with an invalid name
    qualifiers_manager = QualifiersManager(anod_dummy)
    with pytest.raises(AnodError) as err:
        qualifiers_manager.declare_tag_qualifier(name="", description="foo")
    assert str(err.value) == "The qualifier name cannot be empty"

    # Qualifier redeclaration
    qualifiers_manager = QualifiersManager(anod_dummy)
    qualifiers_manager.declare_tag_qualifier(name="foo", description="bar")
    with pytest.raises(AnodError) as err:
        qualifiers_manager.declare_tag_qualifier(name="foo", description="baz")
    assert str(err.value) == "The foo qualifier has already been declared"

    # Qualifier with empty description
    qualifiers_manager = QualifiersManager(anod_dummy)
    with pytest.raises(AnodError) as err:
        qualifiers_manager.declare_tag_qualifier(
            name="foo", description="", repr_alias=""
        )
    assert str(err.value) == "The foo qualifier description cannot be empty"

    # Qualifier with empty repr_alias
    qualifiers_manager = QualifiersManager(anod_dummy)
    with pytest.raises(AnodError) as err:
        qualifiers_manager.declare_tag_qualifier(
            name="foo", description="bar", repr_alias=""
        )
    assert str(err.value) == "The foo qualifier repr_alias cannot be empty"

    # The default value is not in the choices
    qualifiers_manager = QualifiersManager(anod_dummy)
    with pytest.raises(AnodError) as err:
        qualifiers_manager.declare_key_value_qualifier(
            name="foo",
            description="bar",
            choices=["baz"],
            default="dummy",
        )
    assert str(err.value) == (
        'The foo qualifier default value "dummy" not in ' "['baz']"
    )

    # Add a component with an invalid name
    qualifiers_manager = QualifiersManager(anod_dummy)
    with pytest.raises(AnodError) as err:
        qualifiers_manager.declare_component(
            "foo@",
            {},
        )
    assert str(err.value) == 'The component name "foo@" contains an invalid character'

    # Component duplication
    qualifiers_manager = QualifiersManager(anod_dummy)
    qualifiers_manager.declare_component(
        "foo",
        {},
    )
    with pytest.raises(AnodError) as err:
        qualifiers_manager.declare_component(
            "foo",
            {},
        )
    assert str(err.value) == 'The "foo" component names is already used'

    # Try to build a component and a build_space before calling parse
    qualifiers_manager = QualifiersManager(anod_dummy)
    with pytest.raises(AnodError) as err:
        qualifiers_manager.component
    assert str(err.value) == (
        "It is not possible to build a component before the end of the declaration "
        "phase"
    )
    with pytest.raises(AnodError) as err:
        qualifiers_manager.build_space_name
    assert str(err.value) == (
        "It is not possible to build a build_space name before the end of the "
        "declaration phase"
    )

    # Forget to use a qualifier without a default value
    qualifiers_manager = QualifiersManager(anod_dummy)
    qualifiers_manager.declare_key_value_qualifier(
        name="foo",
        description="bar",
    )
    with pytest.raises(AnodError) as err:
        qualifiers_manager.parse({})
    assert str(err.value) == (
        "The foo qualifier was declared without a default value but not passed"
    )

    # Use of undeclared qualifier
    with pytest.raises(AnodError) as err:
        AnodDummy("foo", kind="build")
    assert str(err.value) == ('The qualifier "foo" is used but has not been declared')

    # Pass a key_value qualifier with no value
    qualifiers_manager = QualifiersManager(Anod("", kind="build"))
    qualifiers_manager.declare_key_value_qualifier(
        name="foo",
        description="foo",
    )
    with pytest.raises(AnodError) as err:
        qualifiers_manager.parse({"foo": ""})
    assert str(err.value) == 'The key-value qualifier "foo" must be passed with a value'

    # Pass a key_value qualifier with a value not in choices
    qualifiers_manager = QualifiersManager(Anod("", kind="build"))
    qualifiers_manager.declare_key_value_qualifier(
        name="foo",
        description="foo",
        choices=["bar", "baz"],
    )
    with pytest.raises(AnodError) as err:
        qualifiers_manager.parse({"foo": "foo"})
    assert (
        str(err.value) == "The foo qualifier value must be in ['bar', 'baz']. Got foo"
    )

    # Pass a tag qualifier with a value
    qualifiers_manager = QualifiersManager(anod_dummy)
    qualifiers_manager.declare_tag_qualifier(
        name="foo",
        description="foo",
    )
    with pytest.raises(AnodError) as err:
        qualifiers_manager.parse({"foo": "bar"})
    assert str(err.value) == (
        'The foo qualifier is a tag and does not expect any values. Got "bar"'
    )

    # Try to build a component

    # Invalid use of test_only qualifier
    qualifiers_manager = QualifiersManager(anod_dummy)
    qualifiers_manager.declare_key_value_qualifier(
        name="foo",
        description="bar",
        test_only=True,
    )
    with pytest.raises(AnodError) as err:
        qualifiers_manager.parse({"foo": "bar"})
    assert str(err.value) == (
        "The qualifier foo is test_only but the current anod kind is build"
    )

    # use a not declared qualifier in component
    qualifiers_manager = QualifiersManager(anod_dummy)
    qualifiers_manager.declare_component(
        "foo",
        {"bar": "baz"},
    )
    with pytest.raises(AnodError) as err:
        qualifiers_manager.parse({})
    assert str(err.value) == (
        'In component "foo": The qualifier "bar" is used but has not been declared'
    )

    # Incomplete use of a qualifier without default value
    qualifiers_manager = QualifiersManager(anod_dummy)
    qualifiers_manager.declare_key_value_qualifier(
        name="foo",
        description="foo",
    )
    qualifiers_manager.declare_component(
        "bar",
        {"foo": ""},
    )
    with pytest.raises(AnodError) as err:
        qualifiers_manager.parse({"foo": "baz"})
    assert str(err.value) == (
        'In component "bar": The key-value qualifier "foo" must be passed with a value'
    )

    # Reuse a qualifier configuration in a component
    qualifiers_manager = QualifiersManager(anod_dummy)
    qualifiers_manager.declare_component(
        "bar",
        {},
    )
    qualifiers_manager.declare_component(
        "baz",
        {},
    )
    with pytest.raises(AnodError) as err:
        qualifiers_manager.parse({"foo": "baz"})
    assert str(err.value) == (
        "The qualifier configuration of baz is already " "used by bar"
    ) or str(err.value) == (
        "The qualifier configuration of bar is already " "used by baz"
    )

    # invalid call to inner method
    qualifiers_manager = QualifiersManager(anod_dummy)
    with pytest.raises(AnodError) as err:
        qualifiers_manager._QualifiersManager__qualifier_config_repr({})
    assert str(err.value) == (
        "The function 'key' cannot be used before the end of the declaration phase"
    )

    with pytest.raises(AnodError) as err:
        qualifiers_manager._QualifiersManager__check_qualifier_consistency({})
    assert str(err.value) == (
        "The qualifier consistency cannot be checked before the end of the "
        "declaration phase"
    )

    with pytest.raises(AnodError) as err:
        qualifiers_manager._QualifiersManager__get_parsed_qualifiers()
    assert str(err.value) == (
        "It is not possible to get the parsed passed qualifiers before the end "
        "of the declaration phase"
    )

    with pytest.raises(AnodError) as err:
        qualifiers_manager._QualifiersManager__force_default_values({})
    assert str(err.value) == (
        "The default values cannot be added before the end of the declaration phase"
    )

    # Check when the qualifier type is wrong
    qualifiers_manager = QualifiersManager(anod_dummy)
    qualifiers_manager.declare_tag_qualifier(
        name="foo",
        description="bar",
    )
    qualifiers_manager.qualifier_decls["foo"]["type"] = "baz"
    qualifiers_manager._QualifiersManager__end_declaration_phase()
    with pytest.raises(AnodError) as err:
        qualifiers_manager._QualifiersManager__check_qualifier_consistency({})
    assert str(err.value) == (
        'An expected qualifier type was encountered during parsing Got "baz"'
    )
    with pytest.raises(AnodError) as err:
        qualifiers_manager._QualifiersManager__check_qualifier_consistency(
            {"foo": "foo"}
        )
    assert str(err.value) == (
        'An expected qualifier type was encountered during parsing Got "baz"'
    )
    with pytest.raises(AnodError) as err:
        qualifiers_manager._QualifiersManager__generate_qualifier_part(
            "foo", {"foo": "foo"}
        )
    assert str(err.value) == (
        'An expected qualifier type was encountered during parsing Got "baz"'
    )
    with pytest.raises(AnodError) as err:
        qualifiers_manager._QualifiersManager__force_default_values({})
    assert str(err.value) == (
        'An expected qualifier type was encountered during parsing Got "baz"'
    )

    # Call end declaration phase but don't parse it
    qualifiers_manager = QualifiersManager(anod_dummy)
    qualifiers_manager._QualifiersManager__end_declaration_phase()
    with pytest.raises(AnodError) as err:
        qualifiers_manager._QualifiersManager__get_parsed_qualifiers()
    assert str(err.value) == (
        "The parse method must be called first to generate qualifiers values"
    )


def test_qualifiers_manager():
    class Simple(Anod):
        enable_name_generator = True
        base_name = "simple"

        def declare_qualifiers_and_components(self, qualifiers_manager):
            qualifiers_manager.declare_tag_qualifier(
                name="debug",
                description="debug",
            )
            qualifiers_manager.declare_key_value_qualifier(
                name="foo",
                description="foo",
                default="dval",
            )

    simple = Simple("", kind="build")
    assert simple.build_space_name == "simple_foo-dval"
    assert simple.component is None

    other_simple = Simple("foo=bar", kind="build")
    assert other_simple.build_space_name == "simple_foo-bar"
    assert other_simple.component is None

    class AnodNoComponent(Anod):
        enable_name_generator = True
        base_name = "my_spec"

        def declare_qualifiers_and_components(self, qualifiers_manager):
            # Add the "debug" qualifier
            qualifiers_manager.declare_tag_qualifier(
                name="debug",
                description="State if the build must be done in debug mode.",
            )

            # Add the "version" qualifier
            qualifiers_manager.declare_key_value_qualifier(
                name="version",
                description="State the version of the component to be build",
                choices=["1.2"],
                repr_omit_key=True,
            )

            # Add the "path" qualifier
            qualifiers_manager.declare_key_value_qualifier(
                name="path",
                description="The first path.",
                repr_in_hash=True,
            )

            # Add the "path_bis" qualifier
            qualifiers_manager.declare_key_value_qualifier(
                name="path_bis",
                description="A second path.",
                repr_in_hash=True,
            )

    anod_no_component_1 = AnodNoComponent(
        "debug,version=1.2,path=/some/path,path_bis=/other/path", kind="build"
    )
    assert (
        anod_no_component_1.build_space_name
        == "my_spec_debug_1.2_ca656cbada5f82b1063b10f1e1adaeb11c98e6fe"
    )
    assert anod_no_component_1.component is None

    anod_no_component_2 = AnodNoComponent(
        "version=1.2,path=/some/path,path_bis=/other/path", kind="build"
    )
    assert (
        anod_no_component_2.build_space_name
        == "my_spec_1.2_ca656cbada5f82b1063b10f1e1adaeb11c98e6fe"
    )
    assert anod_no_component_2.component is None

    anod_no_component_3 = AnodNoComponent(
        "debug,version=1.2,path=/different/path,path_bis=/path", kind="build"
    )
    assert (
        anod_no_component_3.build_space_name
        == "my_spec_debug_1.2_7a7d1e2193d81f68693fe880de86a1c54bfcbb2c"
    )
    assert anod_no_component_3.component is None

    class AnodComponent(Anod):
        enable_name_generator = True
        base_name = "my_spec"

        def declare_qualifiers_and_components(self, qualifiers_manager):
            qualifiers_manager.declare_tag_qualifier(
                name="debug",
                description="State if the build must be done in debug mode.",
            )

            qualifiers_manager.declare_key_value_qualifier(
                name="version",
                description="State the version of the component to be build",
                default="1.2",
                repr_omit_key=True,
            )

            qualifiers_manager.declare_component(
                "my_spec",
                {
                    "version": "1.3",
                },
            )

            qualifiers_manager.declare_component(
                "my_spec_debug",
                {
                    "version": "1.3",
                    "debug": "",
                },
            )

    anod_component_1 = AnodComponent("debug,version=1.3", kind="build")
    assert anod_component_1.build_space_name == "my_spec_debug"
    assert anod_component_1.component == "my_spec_debug"

    anod_component_2 = AnodComponent("", kind="build")
    assert anod_component_2.build_space_name == "my_spec_1.2"
    assert anod_component_2.component is None

    anod_component_3 = AnodComponent("version=1.3", kind="build")
    assert anod_component_3.build_space_name == "my_spec"
    assert anod_component_3.component == "my_spec"

    # raise an error using version with no value
    with pytest.raises(AnodError) as err:
        anod_component_3 = AnodComponent("version=", kind="build")
    assert str(err.value) == (
        'The key-value qualifier "version" must be passed with a value'
    )

    # Unit test

    # Call parse twice
    qualifiers_manager = QualifiersManager(Anod("", kind="build"))
    qualifiers_manager.parse({})
    qualifiers_manager.parse({})
