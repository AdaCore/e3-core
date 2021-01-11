import os

from typing import Dict

import e3.electrolyt.plan as plan
from e3.anod.context import AnodContext, SchedulingError
from e3.anod.error import AnodError
from e3.anod.loader import AnodSpecRepository
from e3.env import BaseEnv

import pytest


class TestContext:

    spec_dir = os.path.join(os.path.dirname(__file__), "context_data")

    def create_context(self, reject_duplicates: bool = True) -> AnodContext:
        """Create a spec repository and anod context.

        :param reject_duplicates: whether to reject duplicates in plan
        """

        def repo_conf(name: str) -> Dict[str, str]:
            return {"vcs": "git", "url": name, "branch": "master"}

        # Create a context for a x86-linux machine
        asr = AnodSpecRepository(self.spec_dir)
        asr.repos["spec1-git"] = repo_conf("spec1")
        asr.repos["spec8-git"] = repo_conf("spec8")
        asr.repos["spec2-git"] = repo_conf("spec2")
        asr.repos["a-git"] = repo_conf("a")
        env = BaseEnv()
        env.set_build("x86-linux", "rhes6", "mylinux")
        ac = AnodContext(asr, default_env=env, reject_duplicates=reject_duplicates)
        return ac

    def test_context_init(self):
        # Create a context using:
        # 1. the local default configuration
        # 2. forcing a x86-linux configuration
        asr = AnodSpecRepository(self.spec_dir)
        ac = AnodContext(asr)
        assert ac.default_env.build == BaseEnv().build
        assert ac.default_env.host == BaseEnv().host
        assert ac.default_env.target == BaseEnv().target
        self.create_context()

    def test_load(self):
        # Load a simple build specification that declares a single source
        ac = self.create_context()
        ac.load("spec1", env=ac.default_env, qualifier="", kind="build")

        # Load it a second time should use the cache data
        ac.load("spec1", env=None, qualifier="", kind="build")

        # One source should have been registered
        assert (
            len(ac.sources) == 1 and "spec1-src" in ac.sources
        ), "spec1-src source from spec1.anod has not been registered"

        # One spec instance should have been registered in the cache
        assert len(ac.cache) == 1, "caching of anod instances broken"

    def test_add_anod_action(self):
        # Load spec1 with build primitive
        ac = self.create_context()

        # the result should not be schedulable as there is no build
        # primitive defined in spec1
        with pytest.raises(SchedulingError):
            print(ac.add_anod_action("spec1", env=ac.default_env, primitive="build"))

    def test_add_anod_action_source(self):
        """Test source packaging."""
        ac = self.create_context()

        ac.add_anod_action("spec1", env=ac.default_env, primitive="source")
        result = ac.schedule(ac.always_create_source_resolver)
        assert len(result) == 5, result.as_dot()
        assert set(result.vertex_data.keys()) == {
            "root",
            "mylinux.x86-linux.spec1.source.spec1-src",
            "mylinux.x86-linux.spec1.source.sources",
            "checkout.spec1-git",
            "mylinux.x86-linux.spec1.upload_src.spec1-src",
        }

    def test_add_anod_action2(self):
        # Simple spec with sources associated to the build primitive
        ac = self.create_context()
        ac.add_anod_action("spec2", env=ac.default_env, primitive="build")
        assert len(ac.tree) == 9, ac.tree.as_dot()

        result = ac.schedule(ac.always_download_source_resolver)
        assert len(result) == 5, result.as_dot()
        assert set(result.vertex_data.keys()) == {
            "root",
            "mylinux.x86-linux.spec2.build",
            "source_get.spec2-src",
            "mylinux.x86-linux.spec2.source_install.spec2-src",
            "download.spec2-src",
        }

    def test_add_anod_action2_force_install(self):
        """Check that forcing an install with no package is rejected."""
        ac = self.create_context()
        try:
            ac.add_anod_action(
                "spec2",
                env=ac.default_env,
                primitive="install",
                plan_args={},
                plan_line="install_plan.txt:2",
            )
        except SchedulingError as err:
            assert (
                "error in plan at install_plan.txt:2: install should "
                "be replaced by build" in str(err)
            )

    def test_add_anod_action2_no_source_resolver(self):
        def no_resolver(action, decision):
            return AnodContext.decision_error(action, decision)

        ac = self.create_context()
        ac.add_anod_action("spec2", env=ac.default_env, primitive="build")
        assert len(ac.tree) == 9, ac.tree.as_dot()

        with pytest.raises(SchedulingError) as err:
            ac.schedule(no_resolver)
        assert (
            "This plan resolver cannot decide whether what to do"
            " for resolving source_get.spec2-src." in str(err)
        )

    def test_add_anod_action3(self):
        # Simple spec with both install and build primitive and a package
        # declared
        ac = self.create_context()
        ac.add_anod_action("spec3", env=ac.default_env, primitive="build")
        assert len(ac.tree) == 6, ac.tree.as_dot()
        result = ac.schedule(ac.always_download_source_resolver)
        assert len(result) == 4, result.as_dot()
        assert set(result.vertex_data.keys()) == {
            "root",
            "mylinux.x86-linux.spec3.build",
            "mylinux.x86-linux.spec3.install",
            "mylinux.x86-linux.spec3.upload_bin",
        }

    def test_add_anod_action4(self):
        # Simple spec with:
        #   install primitive, package, component
        #   build primitive
        ac = self.create_context()
        ac.add_anod_action("spec4", env=ac.default_env, primitive="build")
        assert len(ac.tree) == 6, ac.tree.as_dot()
        result = ac.schedule(ac.always_download_source_resolver)
        assert len(result) == 4, result.as_dot()
        assert set(result.vertex_data.keys()) == {
            "root",
            "mylinux.x86-linux.spec4.build",
            "mylinux.x86-linux.spec4.install",
            "mylinux.x86-linux.spec4.upload_bin",
        }

    def test_add_anod_action4_2(self):
        # Same previous example but calling install primitive instead of build
        ac = self.create_context()
        ac.add_anod_action("spec4", env=ac.default_env, primitive="install")
        assert len(ac.tree) == 5, ac.tree.as_dot()
        result = ac.schedule(ac.always_download_source_resolver)
        assert len(result) == 3, result.as_dot()
        assert set(result.vertex_data.keys()) == {
            "root",
            "mylinux.x86-linux.spec4.download_bin",
            "mylinux.x86-linux.spec4.install",
        }

    def test_add_anod_action4_3(self):
        # Same as previous example but calling test primitive
        ac = self.create_context()
        ac.add_anod_action("spec4", env=ac.default_env, primitive="test")
        assert len(ac.tree) == 2, ac.tree.as_dot()
        result = ac.schedule(ac.always_download_source_resolver)
        assert len(result) == 2, result.as_dot()
        assert set(result.vertex_data.keys()) == {
            "root",
            "mylinux.x86-linux.spec4.test",
        }

    def test_add_anod_action5(self):
        # Case in which a source component should be uploaded (i.e: no binary
        # package declared)
        ac = self.create_context()
        ac.add_anod_action("spec5", env=ac.default_env, primitive="build")
        assert len(ac.tree) == 3, ac.tree.as_dot()
        result = ac.schedule(ac.always_download_source_resolver)
        assert len(result) == 3, result.as_dot()
        assert set(result.vertex_data.keys()) == {
            "root",
            "mylinux.x86-linux.spec5.build",
            "mylinux.x86-linux.spec5.upload_bin",
        }

    def test_add_anod_action6(self):
        # Calling install on a spec without install primitive result in a build
        # ??? should we allow that ???
        ac = self.create_context()
        ac.add_anod_action("spec6", env=ac.default_env, primitive="install")
        assert len(ac.tree) == 2, ac.tree.as_dot()
        result = ac.schedule(ac.always_download_source_resolver)
        assert len(result) == 2, result.as_dot()
        assert set(result.vertex_data.keys()) == {
            "root",
            "mylinux.x86-linux.spec6.build",
        }

    def test_add_anod_action6_2(self):
        # Same as previous example. Just ensure that if the spec is called
        # twice with different qualifiers that have no effect on build space
        # name then the result is only one install. (and thus qualifier value
        # for that node won't be deterministic.
        # ??? Should we raise issues on such cases ???
        ac = self.create_context()
        ac.add_anod_action("spec6", env=ac.default_env, primitive="install")
        ac.add_anod_action(
            "spec6", env=ac.default_env, primitive="install", qualifier="myqualif"
        )
        assert len(ac.tree) == 2, ac.tree.as_dot()
        result = ac.schedule(ac.always_download_source_resolver)
        assert len(result) == 2, result.as_dot()
        assert set(result.vertex_data.keys()) == {
            "root",
            "mylinux.x86-linux.spec6.build",
        }

    def test_add_anod_action7(self):
        # Ensure that build_deps = None is accepted
        ac = self.create_context()
        ac.add_anod_action("spec7", env=ac.default_env, primitive="build")
        result = ac.schedule(ac.always_download_source_resolver)
        assert len(result) == 2, result.as_dot()
        assert set(result.vertex_data.keys()) == {
            "root",
            "mylinux.x86-linux.spec7.build",
        }

    def test_add_anod_action8(self):
        """Simple spec with source that does not exist."""
        ac = self.create_context()
        with pytest.raises(AnodError):
            ac.add_anod_action("spec8", env=ac.default_env, primitive="build")

    def test_add_anod_action9(self):
        """Test source dependency."""
        ac = self.create_context()
        ac.add_anod_action("spec9", env=ac.default_env, primitive="build")
        result = ac.schedule(ac.always_download_source_resolver)
        assert "download.spec2-src" in list(result.vertex_data.keys())

    def test_add_anod_action10(self):
        """Verify that requiring both build and install fails."""
        ac = self.create_context()
        ac.add_anod_action("spec3", env=ac.default_env, primitive="install")
        ac.add_anod_action("spec3", env=ac.default_env, primitive="build")

        with pytest.raises(SchedulingError):
            ac.schedule(ac.always_download_source_resolver)

    def test_add_anod_action11_build_tree_dep(self):
        """Check build dependencies."""
        ac = self.create_context()
        ac.add_anod_action(
            "spec10",
            env=ac.default_env,
            qualifier="build_tree",
            primitive="build",
            plan_line="myplan:1",
        )

        # we have a dep on spec3 build_pkg, we require an explicit call to
        # build
        with pytest.raises(SchedulingError) as err:
            ac.schedule(ac.always_download_source_resolver)

        assert "has a build_tree dependency on spec3" in str(err)
        assert 'anod_build("spec3", qualifier="foo", build="x86-linux")' in str(err)

        ac.add_anod_action(
            "spec3",
            env=ac.default_env,
            qualifier="foo",
            primitive="install",
            plan_line="myplan:2",
        )
        with pytest.raises(SchedulingError) as err:
            ac.schedule(ac.always_download_source_resolver)

        assert "explicit DownloadBinary decision made by myplan:2" in str(err)

    def test_add_anod_action11_build_tree_dep_with_env(self):
        """Check build dependencies."""
        ac = self.create_context()
        ac.add_anod_action(
            "spec10",
            env=ac.default_env,
            qualifier="build_tree_with_env",
            primitive="build",
            plan_line="myplan:1",
        )

        # we have a dep on spec3 build_pkg, we require an explicit call to
        # build
        with pytest.raises(SchedulingError) as err:
            ac.schedule(ac.always_download_source_resolver)

        assert "has a build_tree dependency on spec3" in str(err.value)
        assert (
            'anod_build("spec3", qualifier="foo",'
            ' build="x86_64-linux", host="x86-linux",'
            ' target="arm-elf")' in str(err.value)
        )

    def test_add_anod_action11_install_dep(self):
        """Check build dependencies."""
        ac = self.create_context()
        ac.add_anod_action(
            "spec10", env=ac.default_env, primitive="build", plan_line="myplan:1"
        )

        # we have a dep on spec3 build_pkg, we require an explicit call to
        # build
        with pytest.raises(SchedulingError) as err:
            ac.schedule(ac.always_download_source_resolver)

        assert (
            'Please either add anod_build("spec3", build="x86-linux") '
            'or anod_install("spec3", build="x86-linux")'
            " in the plan" in str(err)
        )

        ac.add_anod_action(
            "spec3", env=ac.default_env, primitive="install", plan_line="myplan:2"
        )

        # This call should not raise an exception
        ac.schedule(ac.always_download_source_resolver)

    def test_add_anod_action12(self):
        """Check handling of duplicated source package."""
        ac = self.create_context()
        ac.add_anod_action("spec12", env=ac.default_env, primitive="build")
        result = ac.schedule(ac.always_download_source_resolver)
        keys = set(result.vertex_data.keys())
        assert "download.spec1-src" in keys
        assert "download.unmanaged-src" in keys

    def test_add_anod_action13(self):
        """Check handling of install without build."""
        ac = self.create_context()
        ac.add_anod_action("spec13", env=ac.default_env, primitive="install")
        result = ac.schedule(ac.always_download_source_resolver)
        keys = set(result.vertex_data.keys())
        assert len(keys) == 3, keys
        assert "mylinux.x86-linux.spec13.download_bin" in keys
        assert "mylinux.x86-linux.spec13.install" in keys

    def test_source_fails_when_missing_source_primitive(self):
        """Source action should fail when the source primitive is undefined.

        Check that a SchedulingError is thrown if the source primitive is absent and a
        source packaging action is required.
        """
        ac = self.create_context()

        # `anod source` should fail on a spec without a source primitive
        with pytest.raises(
            SchedulingError,
            match=r"spec missing_source_primitive does not support primitive source",
        ):
            ac.add_anod_action(
                "missing_source_primitive", env=ac.default_env, primitive="source"
            )

    def test_add_anod_action_unmanaged_source(self):
        """Check no source creation for thirdparties."""
        ac = self.create_context()
        ac.add_anod_action(
            "spec-unmanaged-source", env=ac.default_env, primitive="source"
        )
        result = ac.schedule(ac.always_download_source_resolver)
        keys = set(result.vertex_data.keys())
        assert len(keys) == 2, keys
        assert "mylinux.x86-linux.spec-unmanaged-source.source.wheel.whl" not in keys

    def test_add_anod_action_managed_source(self):
        """Check no source creation for thirdparties."""
        ac = self.create_context()
        ac.add_anod_action(
            "spec-managed-source", env=ac.default_env, primitive="source"
        )
        result = ac.schedule(ac.always_download_source_resolver)
        keys = set(result.vertex_data.keys())
        assert len(keys) == 5, keys
        assert "checkout.a-git" in keys
        assert "mylinux.x86-linux.spec-managed-source.source.a-src" in keys

    def test_dag_2_plan(self):
        """Check that we can extract values from plan in final dag.

        Some paramaters passed in the plan are lost in the final
        scheduled dag, when plan lines are transformed into
        anod actions. It is possible to retrieve them by looking
        at the tags.
        """
        # Create a new plan context
        ac = self.create_context()
        current_env = BaseEnv()
        cm = plan.PlanContext(server=current_env)

        # Declare available actions and their signature
        def anod_action(
            module,
            build=None,
            default_build=False,
            host=None,
            target=None,
            board=None,
            weathers=None,
            product_version=None,
            when_missing=None,
            manual_action=False,
            qualifier=None,
            jobs=None,
            releases=None,
            process_suffix=None,
            update_vcs=False,
            recursive=None,
            query_range=None,
            force_repackage=False,
        ):
            pass

        for a in ("anod_build", "anod_install", "anod_source", "anod_test"):
            cm.register_action(a, anod_action)

        # Also register unsupported actions to verify that this does not
        # crash the plan parser
        cm.register_action("anod_foo", anod_action)
        cm.register_action("foo", lambda: None)

        # Create a simple plan
        content = [
            "def myserver():",
            '    anod_build("spec12", weathers="foo")',
            '    anod_build("spec10", weathers="foo")',
            '    anod_build("spec11", weathers="bar")',
            '    anod_foo("spec666")',
            "    foo()",
        ]
        with open("plan.txt", "w") as f:
            f.write("\n".join(content))
        myplan = plan.Plan({}, plan_ext=".txt")
        myplan.load("plan.txt")

        # Execute the plan and create anod actions
        for action in cm.execute(myplan, "myserver"):
            ac.add_plan_action(action)

        # Create a reverse tag to have a working get_context
        # when looking for parameters such as weathers we want to
        # get the plan line that has triggered the action, e.g.
        # for spec3.build that has been triggered by spec10.build
        # we want to propagate the weathers set in the line
        #     anod_build("spec10", weathers="foo")
        # in the Build action for spec3
        reverse_dag = ac.tree.reverse_graph()

        for uid, action in ac.tree:
            if uid.endswith("spec12.build"):
                assert ac.tree.get_tag(uid)
                cdist, cuid, ctag = reverse_dag.get_context(uid)[0]
                assert cuid == uid
                assert ctag["plan_args"]["weathers"] == "foo"
                assert ctag["plan_line"] == "plan.txt:2"
            elif uid.endswith("spec3.build"):
                assert not ac.tree.get_tag(uid)
                cdist, cuid, ctag = reverse_dag.get_context(uid)[0]
                assert cuid != uid
                assert cuid.endswith("spec10.build")
                assert ctag["plan_args"]["weathers"] == "foo"
                assert ctag["plan_line"] == "plan.txt:3"
            elif uid.endswith("spec11.build"):
                assert ac.tree.get_tag(uid), ac.tree.tags
                cdist, cuid, ctag = reverse_dag.get_context(uid)[0]
                assert cuid == uid
                assert ctag["plan_args"]["weathers"] == "bar"
                assert ctag["plan_line"] == "plan.txt:4"

                # Also verify that the instance deps is properly loaded
                assert set(action.anod_instance.deps.keys()) == {"spec1"}
                assert action.anod_instance.deps["spec1"].__class__.__name__ == "Spec1"

        # Also test that we are still able to extract the values
        # after having scheduled the action graph.

        # Create an explict build action to make sure that the plan can be
        # scheduled
        ac.add_anod_action(
            name="spec3",
            env=current_env,
            primitive="build",
            plan_line="plan.txt:5",
            plan_args={"weathers": "my_spec3_weather"},
        )

        sched_dag = ac.schedule(ac.always_download_source_resolver)
        sched_rev = sched_dag.reverse_graph()

        for uid, action in sched_dag:
            if uid.endswith("spec12.build"):
                assert sched_dag.get_tag(uid)

                # Also verify that the instance deps is properly loaded
                assert set(action.anod_instance.deps.keys()) == {"spec1", "spec11"}
                assert (
                    action.anod_instance.deps["spec11"].__class__.__name__ == "Spec11"
                )
                assert action.anod_instance.deps["spec1"].__class__.__name__ == "Spec1"

            elif uid.endswith("spec3.build"):
                assert sched_dag.get_tag(uid)
                assert (
                    sched_rev.get_context(uid)[0][2]["plan_args"]["weathers"]
                    == "my_spec3_weather"
                )

    def test_dag_2_plan_sources(self):
        """Check that we can extract values from plan in final dag.

        Use a scheduler to always create source and ask for a source
        package creation.
        """
        # Create a new plan context
        ac = self.create_context()
        current_env = BaseEnv()
        cm = plan.PlanContext(server=current_env)

        # Declare available actions and their signature
        def anod_action(
            module,
            build=None,
            default_build=False,
            host=None,
            target=None,
            board=None,
            weathers=None,
            product_version=None,
            when_missing=None,
            manual_action=False,
            qualifier=None,
            jobs=None,
            releases=None,
            process_suffix=None,
            update_vcs=False,
            recursive=None,
            query_range=None,
            force_repackage=False,
        ):
            pass

        cm.register_action("anod_source", anod_action)

        # Create a simple plan
        content = ["def myserver():", '    anod_source("spec1", weathers="foo")']
        with open("plan.txt", "w") as f:
            f.write("\n".join(content))
        myplan = plan.Plan({})
        myplan.load("plan.txt")

        # Execute the plan and create anod actions
        for action in cm.execute(myplan, "myserver"):
            ac.add_plan_action(action)

        for uid, _ in ac.tree:
            if uid.endswith("sources"):
                assert ac.tree.get_tag(uid)
            elif uid.endswith(".source.spec1-src"):
                assert ac.tree.get_tag(uid)
                assert (
                    ac.tree.get_context(
                        vertex_id=uid, reverse_order=True, max_distance=1
                    )[0][2]["plan_args"]["weathers"]
                    == "foo"
                )

    @pytest.mark.parametrize("reject_duplicates", [True, False])
    def test_duplicated_lines(self, reject_duplicates):
        """Check that duplicated lines in plan are properly rejected."""
        ac = self.create_context(reject_duplicates=reject_duplicates)
        current_env = BaseEnv()
        cm = plan.PlanContext(server=current_env)

        # Declare available actions and their signature
        def anod_action(
            module,
            build=None,
            default_build=False,
            host=None,
            target=None,
            board=None,
            weathers=None,
            product_version=None,
            when_missing=None,
            manual_action=False,
            qualifier=None,
            jobs=None,
            releases=None,
            process_suffix=None,
            update_vcs=False,
            recursive=None,
            query_range=None,
            force_repackage=False,
        ):
            pass

        cm.register_action("anod_build", anod_action)
        # Create a simple plan
        content = [
            "def myserver():",
            '    anod_build("spec3", weathers="A")',
            '    anod_build("spec3", weathers="B")',
        ]
        with open("plan.plan", "w") as f:
            f.write("\n".join(content))
        myplan = plan.Plan({})
        myplan.load("plan.plan")

        if not reject_duplicates:
            # Execute the plan and create anod actions
            # Execute the plan and create anod actions
            for action in cm.execute(myplan, "myserver"):
                ac.add_plan_action(action)

            for uid, _ in ac.tree:
                if uid.endswith("build"):
                    assert ac.tree.get_tag(uid)["plan_args"]["weathers"] == "B"
        else:

            with pytest.raises(SchedulingError):
                for action in cm.execute(myplan, "myserver"):
                    ac.add_plan_action(action)

    def test_plan_call_args(self):
        """Retrieve call args values."""
        current_env = BaseEnv()
        cm = plan.PlanContext(server=current_env)

        # Declare available actions and their signature
        def plan_action(platform):
            pass

        cm.register_action("plan_action", plan_action)
        # Create a simple plan
        content = ["def myserver():", '    plan_action("any")']
        with open("plan.txt", "w") as f:
            f.write("\n".join(content))
        myplan = plan.Plan({})
        myplan.load("plan.txt")

        for action in cm.execute(myplan, "myserver"):
            assert action.plan_call_args == {"platform": "any"}
            assert action.plan_args["platform"] == BaseEnv().platform

    def test_add_anod_action_duplicate_dep(self):
        """Verify that duplicate dep with same local_name are rejected."""
        ac = self.create_context()
        with pytest.raises(AnodError) as err:
            ac.add_anod_action("duplicate_dep", env=ac.default_env, primitive="build")

        assert (
            "The spec duplicate_dep has two dependencies with the same "
            "local_name attribute (spec3)" in str(err)
        )

    def test_add_anod_action_missing_src_pkg_dep(self, caplog):
        ac = self.create_context()
        ac.add_anod_action("missing_src_pkg_dep", env=ac.default_env, primitive="build")
        assert (
            "source a-src coming from missing_src_pkg_dep_src"
            " but there is no source_pkg dependency for"
            " missing_src_pkg_dep_src in build_deps" in caplog.text
        )
