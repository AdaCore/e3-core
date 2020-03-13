import e3.anod.action as action
import e3.anod.spec
import e3.collection.dag
import e3.env


def test_initall():
    """Very simple test to check that all objects can be initialized."""
    root = action.Root()
    assert root.uid == "root"
    assert str(root) == "root node"

    class MySource:
        name = "my_source"

    class Spec(e3.anod.spec.Anod):
        uid = "my_source_uid"
        name = "my_source_spec"

    get_source = action.GetSource(builder=MySource())
    assert get_source.uid == "source_get.my_source"
    assert str(get_source) == "get source my_source"

    download_source = action.DownloadSource(builder=MySource())
    assert download_source.uid == "download.my_source"
    assert str(download_source) == "download source my_source"

    install_source = action.InstallSource(
        uid="install.my_source",
        spec=Spec(qualifier="", kind="source"),
        source=MySource(),
    )
    assert str(install_source) == "install source my_source"

    create_sources = action.CreateSources(
        anod_instance=Spec(qualifier="", kind="source")
    )
    assert str(create_sources) == "create all sources for my_source_spec.anod"

    create_source = action.CreateSource(
        anod_instance=Spec(qualifier="", kind="source"), source_name="my_source"
    )
    assert str(create_source) == "create source my_source"

    checkout = action.Checkout(repo_name="e3-core", repo_data={})
    assert str(checkout) == "checkout e3-core"

    build_spec = Spec(qualifier="", kind="build")
    build_spec.name = "my_spec"
    build_spec.env = e3.env.Env()

    build = action.Build(anod_instance=build_spec)
    assert str(build).startswith("build my_spec for ")

    test_spec = Spec(qualifier="", kind="test")
    test_spec.name = "my_spec"
    test_spec.env = e3.env.Env()

    test = action.Test(anod_instance=test_spec)
    assert str(test).startswith("test my_spec for ")

    install_spec = Spec(qualifier="", kind="build")
    install_spec.name = "my_spec"
    install_spec.env = e3.env.Env()

    install = action.Install(anod_instance=build_spec)
    assert str(install).startswith("build my_spec for ")

    download_spec = Spec(qualifier="", kind="build")
    download_spec.name = "my_spec"
    download_spec.env = e3.env.Env()

    download = action.DownloadBinary(data=build_spec)
    assert str(download).startswith("download binary of ")

    upload_spec = Spec(qualifier="", kind="build")
    upload_spec.name = "my_spec"
    upload_spec.env = e3.env.Env()

    upload_bin = action.UploadBinaryComponent(data=build_spec)
    assert str(upload_bin).startswith("upload binary package of")

    upload_source = action.UploadSourceComponent(data=build_spec)
    assert str(upload_source).startswith("upload source metadata of ")

    a_decision = action.CreateSourceOrDownload(
        root=root, left=create_source, right=download_source
    )

    assert a_decision.get_decision() is None

    a_decision.set_decision(action.Decision.RIGHT, "plan_line.txt:1")
    assert a_decision.get_decision() == "download.my_source"

    a_decision.set_decision(action.Decision.BOTH, "plan_line.txt:2")
    assert a_decision.get_decision() is None

    boi_decision = action.BuildOrDownload(root=install, left=build, right=download)
    assert boi_decision.get_decision() is None
    boi_decision.set_decision(action.Decision.LEFT, "plan_line.txt:3")
    assert boi_decision.get_decision() == build.uid


def test_trigger():
    """Test Decision triggers."""

    class Spec(e3.anod.spec.Anod):
        uid = "my_source_uid"
        name = "my_source_spec"

    dag = e3.collection.dag.DAG()

    root = action.Root()

    build_spec = Spec(qualifier="", kind="build")
    build_spec.name = "my_spec"
    build_spec.env = e3.env.Env()
    build = action.Build(anod_instance=build_spec)

    build_spec2 = Spec(qualifier="", kind="build")
    build_spec2.name = "my_spec2"
    build_spec2.env = e3.env.Env()
    build2 = action.Build(anod_instance=build_spec2)

    download2 = action.DownloadBinary(build_spec2)

    install_spec2 = Spec(qualifier="", kind="install")
    install_spec2.name = "my_spec2"
    install_spec2.env = e3.env.Env()
    install2 = action.Install(install_spec2)

    dag.add_vertex(root)
    dag.add_vertex(install2)

    # Add a trigger on 'build'
    decision = action.BuildOrDownload(root=install2, left=build2, right=download2)
    decision.add_trigger(build, action.Decision.LEFT, "my_plan_line")

    decision.apply_triggers(dag)

    assert decision.get_expected_decision() is None
    # 'build' not in dag --> expected decision is None

    dag.add_vertex(build.uid, build)
    decision.apply_triggers(dag)
    assert decision.get_expected_decision() == build2.uid

    # Now change the decision, applying the trigger again should show the
    # conflict
    decision.expected_choice = action.Decision.RIGHT
    decision.apply_triggers(dag)
    assert decision.get_expected_decision() is None  # Decision.BOTH

    # Set back to the expected choice and ask for another one
    decision.expected_choice = build2.uid
    decision.set_decision(action.Decision.RIGHT, "my_other_plan_line")
    assert decision.get_decision() is None  # Decision.BOTH

    # Also change the expected choice to RIGHT
    decision.expected_choice = action.Decision.RIGHT
    assert decision.get_expected_decision() == download2.uid
