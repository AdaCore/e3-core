from e3.anod.error import AnodError
from e3.anod.qualifier import Qualifier
from e3.anod.qualifiers_manager import (
    QualifiersManager,
    KeyValueDeclaration,
    KeySetDeclaration,
)
from e3.anod.spec import Anod
from e3.env import BaseEnv

import pytest


def test_qualifier_operations():
    qual1 = Qualifier({"key1": "v1", "key2": "v2"})
    qual2 = Qualifier({"key2": "v2.2", "key3": "v3"})
    qual3 = Qualifier({"key1": "v1.3", "key4": "v4"})

    # Test basic addition of qualifiers
    assert qual1 + qual2 == Qualifier({"key1": "v1", "key2": "v2.2", "key3": "v3"})

    # Test basic filtering-out of keys
    assert qual1 - qual2 == Qualifier({"key1": "v1"})
    assert qual1 - {"key2"} == Qualifier({"key1": "v1"})

    # Test order/priority of operators
    # + and - have the same priority thus are evaluated from left to right
    assert qual1 + qual2 - qual3 == Qualifier({"key2": "v2.2", "key3": "v3"})
    assert qual1 + (qual2 - qual3) == Qualifier(
        {"key1": "v1", "key2": "v2.2", "key3": "v3"}
    )

    # & has a lower priority than +
    assert qual1 + qual2 + qual3 & {"key1", "key2"} == Qualifier(
        {"key1": "v1.3", "key2": "v2.2"}
    )
    assert (qual1 + None) == qual1


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
            qualifiers_manager.declare_key_value_qualifier(
                name="optional_qual",
                description="This is an option qual",
                default="default_value",
            )

    simple = Simple(qualifier="", kind="build")
    assert simple.build_space_name == "simple_optional_qual-default_value"
    assert simple.component is None
    assert not simple.get_qualifier("debug")

    simple_debug = Simple(qualifier="debug", kind="build")
    assert simple_debug.build_space_name == "simple_debug_optional_qual-default_value"
    assert simple_debug.component is None
    assert simple_debug.get_qualifier("debug")

    simple_empty = Simple(qualifier="optional_qual", kind="build")
    assert simple_empty.build_space_name == "simple"

    # Disable the name generator
    class Base(Anod):
        name = "dummy"

    base = Base("", kind="build")
    assert base.get_qualifier("debug") is None

    base = Base("debug=bar", kind="build")
    assert base.get_qualifier("debug") == "bar"


def test_qualifiers_manager_errors():
    class AnodDummy(Anod):
        name = "dummy_spec"
        enable_name_generator = True

    class AnodDummyWithQual(Anod):
        name = "dummy_spec"
        enable_name_generator = True

        def declare_qualifiers_and_components(self, qm: QualifiersManager) -> None:
            qm.declare_tag_qualifier(
                name="test",
                description="test",
            )

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
        "build(name=dummy_spec, qual={}): "
        "qualifier can only be declared in declare_qualifiers_and_components"
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
        "build(name=dummy_spec, qual={}): component/build space can only be "
        "declared in declare_qualifiers_and_components"
    )

    # Add a qualifier with an invalid name
    qualifiers_manager = QualifiersManager(anod_dummy)
    with pytest.raises(AnodError) as err:
        qualifiers_manager.declare_tag_qualifier(name="", description="foo")
    assert (
        str(err.value)
        == "build(name=dummy_spec): Invalid qualifier declaration name ''"
    )

    # Qualifier redeclaration
    qualifiers_manager = QualifiersManager(anod_dummy)
    qualifiers_manager.declare_tag_qualifier(name="foo", description="bar")

    # Qualifier with empty description
    qualifiers_manager = QualifiersManager(anod_dummy)

    # Qualifier with empty repr_alias
    qualifiers_manager = QualifiersManager(anod_dummy)
    with pytest.raises(AnodError) as err:
        qualifiers_manager.declare_tag_qualifier(
            name="foo", description="bar", repr_alias=""
        )
    assert (
        str(err.value)
        == "build(name=dummy_spec): Invalid qualifier declaration alias ''"
    )

    # The default value is not in the choices
    qualifiers_manager = QualifiersManager(anod_dummy)
    with pytest.raises(AnodError) as err:
        qualifiers_manager.declare_key_value_qualifier(
            name="qual1",
            description="qual help",
            choices=["val1", "val2"],
            default="invalid_value",
        )
    assert str(err.value) == (
        "build(name=dummy_spec): default value 'invalid_value' "
        "should be in ('val1', 'val2')."
    )

    # Add a component with an invalid name
    qualifiers_manager = QualifiersManager(anod_dummy)
    with pytest.raises(AnodError) as err:
        qualifiers_manager.declare_component(
            "foo@",
            {},
        )
    assert (
        str(err.value)
        == "build(name=dummy_spec): Invalid component declaration name 'foo@'"
    )

    # Component duplication
    qualifiers_manager = QualifiersManager(anod_dummy)
    qualifiers_manager.declare_component(
        "foo",
        {},
    )

    # Forget to use a qualifier without a default value
    qualifiers_manager = QualifiersManager(anod_dummy)
    qualifiers_manager.declare_key_value_qualifier(
        name="mandatory_qual",
        description="some manadatory qualifier",
    )
    with pytest.raises(AnodError) as err:
        qualifiers_manager.parse({})
    assert str(err.value) == (
        "build(name=dummy_spec, qual={}): Missing qualifier(s): mandatory_qual"
    )

    # Use of undeclared qualifier
    with pytest.raises(AnodError) as err:
        AnodDummy("invalid_qual", kind="build")
    assert str(err.value) == (
        "build(name=dummy_spec, qual={'invalid_qual': ''}): "
        "Invalid qualifier(s): invalid_qual\n"
        "Use `anod help dummy_spec` to get a list of valid qualifiers"
    )
    with pytest.raises(AnodError) as err:
        AnodDummyWithQual("tst", kind="build")
    assert str(err.value) == (
        "build(name=dummy_spec, qual={'tst': ''}): "
        "Invalid qualifier(s): tst\n"
        "Did you mean 'test'?\n"
        "Use `anod help dummy_spec` to get a list of valid qualifiers"
    )

    # Pass a key_value qualifier with a value not in choices
    qualifiers_manager = QualifiersManager(AnodDummy("", kind="build"))
    qualifiers_manager.declare_key_value_qualifier(
        name="qual1",
        description="some qual",
        choices=["val1", "val2"],
    )
    with pytest.raises(AnodError) as err:
        qualifiers_manager.parse({"qual1": "invalid_value1"})
    assert str(err.value) == (
        "build(name=dummy_spec): Invalid value for qualifier "
        "qual1: 'invalid_value1' not in ('val1', 'val2')"
    )

    # Try to build a component

    # Invalid use of test_only qualifier
    qualifiers_manager = QualifiersManager(anod_dummy)
    qualifiers_manager.declare_key_value_qualifier(
        name="test_qual",
        description="test_qual help",
        test_only=True,
    )
    with pytest.raises(AnodError) as err:
        qualifiers_manager.parse({"test_qual": "val1"})
    assert str(err.value) == (
        "build(name=dummy_spec, qual={'test_qual': 'val1'}): "
        "Invalid qualifier(s): test_qual\n"
        "Use `anod help dummy_spec` to get a list of valid qualifiers"
    )

    # use a not declared qualifier in component
    qualifiers_manager = QualifiersManager(anod_dummy)
    qualifiers_manager.declare_component(
        "comp1",
        {"invalid_qual1": "val1"},
    )
    with pytest.raises(AnodError) as err:
        qualifiers_manager.parse({})
    assert str(err.value) == (
        "build(name=dummy_spec, qual={}): Invalid qualifier state "
        "{'invalid_qual1': 'val1'} for build space/component comp1"
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
        qualifiers_manager.parse({})
    assert str(err.value) == (
        "build(name=dummy_spec, qual={}): state {} reused for "
        "several build spaces/components"
    )

    # Use a test_only qualifier in a component
    class TestInComp(Anod):
        enable_name_generator = True
        name = "dummy_spec"

        def declare_qualifiers_and_components(self, qm):
            qm.declare_tag_qualifier(
                name="test_qual1",
                description="desc",
                test_only=True,
            )

            qm.declare_component(
                "comp1",
                {"test_qual1": ""},
            )

    with pytest.raises(AnodError) as err:
        TestInComp(qualifier="", kind="build")
    assert str(err.value) == (
        "build(name=dummy_spec, qual={}): Invalid qualifier state "
        "{'test_qual1': ''} for build space/component comp1"
    )

    # Call value with something else that a str
    qualifiers_manager = QualifiersManager(Anod("", kind="build"))
    with pytest.raises(AnodError) as err:
        qualifiers_manager.declare_key_set_qualifier(
            name="q1",
            description="???",
            default="v1",
        )
    assert (
        str(err.value)
        == "The default of key_set qualifier must be either None or a set"
    )

    # Call value with something else that a str
    key_set = KeySetDeclaration(origin="origin", name="q1", description="???")
    key_value = KeyValueDeclaration(origin="origin", name="q1", description="???")

    with pytest.raises(AnodError) as err:
        key_set.value(1)
    assert "origin: Invalid value for qualifier q1" in str(err.value)

    with pytest.raises(AnodError) as err:
        key_value.value(1)
    assert "origin: Invalid value for qualifier q1" in str(err.value)


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
                default="",
            )

            # Add the "path_bis" qualifier
            qualifiers_manager.declare_key_value_qualifier(
                name="path_bis",
                description="A second path.",
                repr_in_hash=True,
                default="",
            )

    anod_no_component_1 = AnodNoComponent(
        "debug,version=1.2,path=/some/path,path_bis=/other/path", kind="build"
    )
    assert anod_no_component_1.build_space_name == "my_spec_debug_1.2_79765908"
    assert anod_no_component_1.component is None

    anod_no_component_2 = AnodNoComponent(
        "version=1.2,path=/some/path,path_bis=/other/path", kind="build"
    )
    assert anod_no_component_2.build_space_name == "my_spec_1.2_79765908"
    assert anod_no_component_2.component is None

    anod_no_component_3 = AnodNoComponent(
        "debug,version=1.2,path=/different/path,path_bis=/path", kind="build"
    )
    assert anod_no_component_3.build_space_name == "my_spec_debug_1.2_a2aaba2e"
    assert anod_no_component_3.component is None

    anod_no_component_4 = AnodNoComponent(qualifier="debug,version=1.2", kind="build")
    assert anod_no_component_4.build_space_name == "my_spec_debug_1.2"
    assert anod_no_component_4.component is None

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

    # test_only qualifier
    class AnodTestOnly(Anod):
        enable_name_generator = True
        base_name = "my_spec"

        def declare_qualifiers_and_components(self, qualifiers_manager):
            qualifiers_manager.declare_key_value_qualifier(
                name="foo",
                description="foo",
                test_only=True,
            )

            qualifiers_manager.declare_tag_qualifier(
                name="bar",
                description="foo",
            )

            qualifiers_manager.declare_component(
                "baz",
                {},
            )

    anod_component_4 = AnodTestOnly(qualifier="", kind="build")
    assert anod_component_4.build_space_name == "baz"
    assert anod_component_4.component == "baz"

    anod_component_5 = AnodTestOnly(qualifier="bar", kind="build")
    assert anod_component_5.build_space_name == "my_spec_bar"
    assert anod_component_5.component is None
    assert anod_component_5.get_qualifier("bar")

    anod_component_6 = AnodTestOnly(qualifier="foo=bar", kind="test")
    assert anod_component_6.build_space_name == "my_spec_foo-bar_test"
    assert anod_component_6.component is None
    assert not anod_component_6.get_qualifier("bar")

    # Unit test

    # Call parse twice
    qualifiers_manager = QualifiersManager(Anod("", kind="build"))
    qualifiers_manager.parse({})
    qualifiers_manager.parse({})


def test_qualifiers_with_source_primitive():
    class SimpleAnod(Anod):
        enable_name_generator = True
        base_name = "simple"
        name = "simple_anod"

    simple_anod = SimpleAnod(kind="source", qualifier="")
    assert simple_anod.build_space_name == "simple_anod"


def test_add_target_info_to_build_space():
    class ParentAnod(Anod):
        enable_name_generator = True
        name = "parent"

        def declare_qualifiers_and_components(self, qualifiers_manager):
            qualifiers_manager.add_target_info()

    class ChildAnod(ParentAnod):
        name = "child"

        def declare_qualifiers_and_components(self, qualifiers_manager):
            qualifiers_manager.add_target_info(
                machine_aliases={"myboard": "m"}, os_version_aliases={"2.0": "2"}
            )

    class GrandChildAnod(ChildAnod):
        name = "grandchild"

        def declare_qualifiers_and_components(self, qualifiers_manager):
            qualifiers_manager.remove_target_info()

    env = BaseEnv()
    env.set_target(name="arm-elf", version="2.0", machine="myboard")
    anod = ParentAnod(kind="build", qualifier="", env=env)
    assert anod.build_space_name == "parent_2.0_myboard"
    anod = ChildAnod(kind="build", qualifier="", env=env)
    assert anod.build_space_name == "child_2_m"

    anod = GrandChildAnod(kind="build", qualifier="", env=env)
    assert anod.build_space_name == "grandchild"

    # Change add_target_info after parse
    with pytest.raises(AnodError) as err:
        anod.qualifiers_manager.add_target_info()
    assert str(err.value) == (
        "build(name=grandchild, qual={}): build space name computation settings can "
        "only be changed in 'declare_qualifiers_and_components'"
    )

    with pytest.raises(AnodError) as err:
        anod.qualifiers_manager.remove_target_info()
    assert str(err.value) == (
        "build(name=grandchild, qual={}): build space name computation settings can "
        "only be changed in 'declare_qualifiers_and_components'"
    )


def test_key_value_qualifier():
    class Spec(Anod):
        name = "spec"
        enable_name_generator = True

        def declare_qualifiers_and_components(self, qualifiers_manager):
            super().declare_qualifiers_and_components(qualifiers_manager)

            qualifiers_manager.declare_key_value_qualifier(
                name="q1",
                description="???",
                default="default",
                choices=["default", "val"],
            )

    spec1 = Spec(qualifier="q1=default", kind="build")
    spec2 = Spec(qualifier="q1=val", kind="build")

    assert spec1.build_space_name == "spec"
    assert spec2.build_space_name == "spec_q1-val"

    # Declare a key value after the end of the declaration phase
    with pytest.raises(AnodError) as err:
        spec1.qualifiers_manager.declare_key_value_qualifier(
            name="name",
            description="???",
        )
    assert str(err.value) == (
        "build(name=spec, qual={'q1': 'default'}): qualifier can "
        "only be declared in  declare_qualifiers_and_components"
    )


def test_tag_qualifier():
    class Spec(Anod):
        name = "spec"
        enable_name_generator = True

        def declare_qualifiers_and_components(self, qualifiers_manager):
            super().declare_qualifiers_and_components(qualifiers_manager)

            qualifiers_manager.declare_tag_qualifier(
                name="q1",
                description="???",
            )
            qualifiers_manager.declare_tag_qualifier(
                name="q2",
                description="???",
                repr_in_hash=True,
            )

    spec1 = Spec(qualifier="", kind="build")
    spec2 = Spec(qualifier="q2", kind="build")

    assert spec1.build_space_name == "spec"
    assert spec2.build_space_name == "spec_f237cb03"

    # Explicitly test value
    from e3.anod.qualifiers_manager import TagDeclaration

    tag = TagDeclaration(
        origin="origin",
        name="tag",
        description="???",
    )

    assert tag.value("") is True


def test_key_set_qualifier():
    class Spec(Anod):
        name = "spec"
        enable_name_generator = True

        def declare_qualifiers_and_components(self, qualifiers_manager):
            super().declare_qualifiers_and_components(qualifiers_manager)

            qualifiers_manager.declare_key_set_qualifier(
                name="q1",
                description="???",
            )

            qualifiers_manager.declare_key_set_qualifier(
                name="q2",
                description="???",
                default={"1", "2"},
                choices=["1", "2", "3"],
            )

            qualifiers_manager.declare_key_set_qualifier(
                name="q3",
                description="???",
                repr_omit_key=True,
                default={"1"},
            )

            qualifiers_manager.declare_key_set_qualifier(
                name="q4",
                description="???",
                default={"1"},
                repr_in_hash=True,
                choices=["1", "2"],
            )

            qualifiers_manager.declare_key_set_qualifier(
                name="q5",
                description="???",
                default={},
                repr_in_hash=True,
                choices=["1", "2"],
            )

    spec1 = Spec(qualifier="q1=a;b,q2=3;2,q4=2", kind="build")
    spec2 = Spec(qualifier="q1=a", kind="build")
    spec3 = Spec(qualifier="q1=", kind="build")

    assert spec1.build_space_name == "spec_q1-a-b_q2-2-3_1_29c6909d"
    assert spec2.build_space_name == "spec_q1-a_q2-1-2_1_733c1a4a"
    assert spec3.build_space_name == "spec_q2-1-2_1_733c1a4a"

    # Use wrong value
    with pytest.raises(AnodError) as err:
        Spec(qualifier="q1=a,q2=1;2;5;3;4", kind="build")
    assert str(err.value) == (
        "build(name=spec): Invalid value(s) for qualifier q2: "
        "('4', '5') not in ('1', '2', '3')"
    )

    class BadSpec(Spec):
        def declare_qualifiers_and_components(self, qualifiers_manager):
            super().declare_qualifiers_and_components(qualifiers_manager)

            qualifiers_manager.declare_key_set_qualifier(
                "q3",
                description="???",
                default={"5"},
                choices=["1", "2"],
            )

    with pytest.raises(AnodError) as err:
        BadSpec(qualifier="q1=a", kind="build")
    assert str(err.value) == (
        "build(name=spec): In 'q3', default value(s) ('5') should be in ('1', '2')"
    )

    # Declare a key value after the end of the declaration phase
    with pytest.raises(AnodError) as err:
        spec1.qualifiers_manager.declare_key_set_qualifier(
            name="name",
            description="???",
        )
    assert str(err.value) == (
        "build(name=spec, qual={'q1': 'a;b', 'q2': '3;2', 'q4': '2'}): qualifier can "
        "only be declared in  declare_qualifiers_and_components"
    )

    class SpecTest(Anod):
        name = "spec"
        enable_name_generator = True

        def declare_qualifiers_and_components(self, qualifiers_manager):
            super().declare_qualifiers_and_components(qualifiers_manager)

            qualifiers_manager.declare_key_set_qualifier(
                name="q1",
                description="???",
                test_only=True,
            )

    spec1 = SpecTest(qualifier="", kind="build")
    spec2 = SpecTest(qualifier="q1=1;2;3", kind="test")

    assert spec1.build_space_name == "spec"
    assert spec2.build_space_name == "spec_q1-1-2-3_test"


def test_declare_build_space():
    class Spec(Anod):
        name = "spec"
        enable_name_generator = True

        def declare_qualifiers_and_components(self, qualifiers_manager):
            qualifiers_manager.declare_tag_qualifier(
                name="q1",
                description="???",
            )

            qualifiers_manager.declare_build_space_name(
                "my_spec",
                {"q1": ""},
            )

    spec1 = Spec(qualifier="", kind="build")
    spec2 = Spec(qualifier="q1", kind="build")

    assert spec1.build_space_name == "spec"
    assert spec2.build_space_name == "my_spec"
