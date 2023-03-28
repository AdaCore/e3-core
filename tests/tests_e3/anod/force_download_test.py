from e3.env import BaseEnv
from e3.anod.context import AnodContext, SchedulingError
from e3.anod.loader import AnodSpecRepository
import os
import pytest


class TestSourceClosure:
    spec_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "force_download")
    )

    def test_force_download_after_install(self):
        """Test two deps on the same spec with installation and download.

        Here we have two specs having an "installation" and a "download"
        depdendency on the same spec (spec_build). When the two are set
        together the scheduler find the proper solution: download.
        """
        env = BaseEnv()
        env.set_build("x86_64-linux", "rhes8", "mylinux")
        asr = AnodSpecRepository(self.spec_dir)
        ac = AnodContext(asr, default_env=env)
        ac.add_anod_action("spec_install_dep", env=ac.default_env, primitive="build")
        with pytest.raises(SchedulingError) as err:
            ac.schedule(ac.always_create_source_resolver)
        assert "This plan resolver cannot decide" in str(err)

        ac.add_anod_action("spec_download_dep", env=ac.default_env, primitive="build")
        result = ac.schedule(ac.always_create_source_resolver)

        assert set(result.vertex_data.keys()) == {
            "root",
            "x86_64-linux.spec_install_dep.build",
            "x86_64-linux.spec_download_dep.build",
            "x86_64-linux.spec_build.install",
            "x86_64-linux.spec_build.download_bin",
        }

    def test_force_download_before_install(self):
        """Test two deps on the same spec with installation and download.

        Same as test_force_download_after_install but in a different
        order. The end result should be the same.
        """
        env = BaseEnv()
        env.set_build("x86_64-linux", "rhes8", "mylinux")
        asr = AnodSpecRepository(self.spec_dir)
        ac = AnodContext(asr, default_env=env)
        ac.add_anod_action("spec_download_dep", env=ac.default_env, primitive="build")
        result = ac.schedule(ac.always_create_source_resolver)

        assert set(result.vertex_data.keys()) == {
            "root",
            "x86_64-linux.spec_download_dep.build",
            "x86_64-linux.spec_build.install",
            "x86_64-linux.spec_build.download_bin",
        }
        ac.add_anod_action("spec_install_dep", env=ac.default_env, primitive="build")
        ac.schedule(ac.always_create_source_resolver)
        result = ac.schedule(ac.always_create_source_resolver)

        assert set(result.vertex_data.keys()) == {
            "root",
            "x86_64-linux.spec_install_dep.build",
            "x86_64-linux.spec_download_dep.build",
            "x86_64-linux.spec_build.install",
            "x86_64-linux.spec_build.download_bin",
        }

    def test_force_download_after_build(self):
        """Test two deps on the same spec with build and download.

        Here we have two specs having an "build_tree" and a "download"
        depdendency on the same spec (spec_build). When the two are set
        together the scheduler cannot find a solution.
        """
        env = BaseEnv()
        env.set_build("x86_64-linux", "rhes8", "mylinux")
        asr = AnodSpecRepository(self.spec_dir)
        ac = AnodContext(asr, default_env=env)
        ac.add_anod_action("spec_build_dep", env=ac.default_env, primitive="build")

        # Verify that, when scheduling this plan, the scheduler ask for
        # having an explicit build
        with pytest.raises(SchedulingError) as err:
            ac.schedule(ac.always_create_source_resolver)
        assert "A spec in the plan has a build_tree dependency on spec_build" in str(
            err
        )

        # Verify that after adding a download dep, the scheduler now
        # warns that he cannot resolve the plan
        ac.add_anod_action("spec_download_dep", env=ac.default_env, primitive="build")
        with pytest.raises(SchedulingError) as err:
            ac.schedule(ac.always_create_source_resolver)
        assert "explicit DownloadBinary decision made" in str(err)

    def test_force_download_before_build(self):
        """Test two deps on the same spec with build and download.

        Same as test_force_download_after_build but in a different order.
        The expected result is the same: an error should be raised.
        """
        env = BaseEnv()
        env.set_build("x86_64-linux", "rhes8", "mylinux")
        asr = AnodSpecRepository(self.spec_dir)
        ac = AnodContext(asr, default_env=env)
        ac.add_anod_action("spec_download_dep", env=ac.default_env, primitive="build")
        ac.add_anod_action("spec_build_dep", env=ac.default_env, primitive="build")
        with pytest.raises(SchedulingError) as err:
            ac.schedule(ac.always_create_source_resolver)
        assert "explicit DownloadBinary decision made" in str(err)

    def test_force_download_without_download_primitive(self):
        """Test that the force download do not require the download primitive.

        Having a download() primitive or not should not impact this feature.
        """
        env = BaseEnv()
        env.set_build("x86_64-linux", "rhes8", "mylinux")
        asr = AnodSpecRepository(self.spec_dir)
        ac = AnodContext(asr, default_env=env)
        ac.add_anod_action(
            "spec_download_dep_for_nodownloadprimitive",
            env=ac.default_env,
            primitive="build",
        )
        result = ac.schedule(ac.always_create_source_resolver)

        assert set(result.vertex_data.keys()) == {
            "root",
            "x86_64-linux.spec_download_dep_for_nodownloadprimitive.build",
            "x86_64-linux.spec_nodownloadprimitive.install",
            "x86_64-linux.spec_nodownloadprimitive.download_bin",
        }

    def test_force_download_without_require_condition(self):
        """Test that the force download can be done thanks to require=xxx.

        A require condition can be added to the build primitive to disable the
        build primitive for some qualifiers.
        """
        env = BaseEnv()
        env.set_build("x86_64-linux", "rhes8", "mylinux")
        asr = AnodSpecRepository(self.spec_dir)

        # We start with a dependency on spec_nobuild where build primitive
        # require condition is True
        ac = AnodContext(asr, default_env=env)
        ac.add_anod_action(
            "spec_nobuild_dep",
            env=ac.default_env,
            primitive="build",
        )

        # If both build and install are allowed the resolver will
        # complain and ask for an explicit choice
        with pytest.raises(SchedulingError) as err:
            ac.schedule(ac.always_create_source_resolver)
        assert "what to do for resolving" in str(err)

        # Now with a dependency making require return False, and so
        # disable the build primitive, the resolver will not have any
        # conflict: the only allowed action will be download.
        ac2 = AnodContext(asr, default_env=env)
        ac2.add_anod_action(
            "spec_nobuild_stable_dep",
            env=ac.default_env,
            primitive="build",
        )
        result = ac2.schedule(ac.always_create_source_resolver)

        assert set(result.vertex_data.keys()) == {
            "root",
            "x86_64-linux.spec_nobuild.download_bin",
            "x86_64-linux.spec_nobuild_stable_dep.build",
            "x86_64-linux.spec_nobuild.install",
        }
