import os

from e3.anod.error import SandBoxError
from e3.anod.loader import AnodSpecRepository, SpecConfig
from e3.fs import cp, sync_tree
from e3.os.process import Run

import pytest


class TestLoader:

    spec_dir = os.path.join(os.path.dirname(__file__), "data")
    spec2_dir = os.path.join(os.path.dirname(__file__), "data2")

    def test_spec_does_not_exist(self):
        with pytest.raises(SandBoxError) as err:
            AnodSpecRepository("/foo/bar")

        assert str(err.value).startswith("spec directory /foo/bar does not exist")

    def test_spec_loader1(self):
        spec_repo = AnodSpecRepository(self.spec_dir)
        s = spec_repo.load("loader1")
        assert s.name == "loader1"

    def test_spec_loader2(self):
        spec_repo = AnodSpecRepository(self.spec_dir)

        with pytest.raises(SandBoxError) as err:
            spec_repo.load("loader2")
        assert str(err.value).startswith("load: cannot find Anod subclass in")

    def test_invalid_spec(self):
        """Ensure that loading an invalid spec result in a SandboxError."""
        spec_repo = AnodSpecRepository(self.spec_dir)
        with pytest.raises(SandBoxError) as err:
            spec_repo.load("invalid_spec")

        assert "invalid spec code" in str(err.value)

    def test_spec_loader_prolog(self):
        spec_repo = AnodSpecRepository(self.spec_dir)
        anod_class = spec_repo.load("prolog_test")

        # We should be able to load a spec twice
        anod_class = spec_repo.load("prolog_test")

        anod_instance = anod_class("prolog_test", "", "build")
        assert anod_instance.prolog_test, "prolog not executed properly"

    def test_spec_loader_prolog_with_repos(self):
        sync_tree(self.spec_dir, "specs_dir")
        repositories_yaml = os.path.join("specs_dir", "config", "repositories.yaml")
        cp(repositories_yaml + ".tmpl", repositories_yaml)

        spec_repo = AnodSpecRepository("specs_dir")
        anod_class = spec_repo.load("prolog_test")
        assert anod_class.e3_version == "20.1"
        assert anod_class.has_foo is False
        assert anod_class.e3_extra_version is None

        override_conf = {
            "e3-core": {"revision": 21.0},
            "e3-extra": {"vcs": "git", "url": "unknown", "revision": "master"},
        }

        spec_config = SpecConfig()
        spec_config.foo = 2

        spec_repo2 = AnodSpecRepository(
            "specs_dir",
            spec_config=spec_config,
            extra_repositories_config=override_conf,
        )
        anod_class2 = spec_repo2.load("prolog_test")
        assert anod_class2.e3_version == "21.0"
        assert anod_class2.e3_extra_version == "master"

        assert anod_class2.has_foo is True

    def test_spec_inheritance(self):
        """Load a spec that inherit from another spec."""
        spec_repo = AnodSpecRepository(self.spec_dir)
        anod_class = spec_repo.load("child")
        anod_instance = anod_class("load", "", "build")
        assert anod_instance.parent_info == "from_parent"

    def test_multiple_spec_repository(self):
        """Ensure that spec function is context dependent."""
        spec_repo = AnodSpecRepository(self.spec_dir)
        spec2_repo = AnodSpecRepository(self.spec2_dir)
        anod_class = spec_repo.load("child")
        anod_instance = anod_class("load", "", "build")
        assert anod_instance.parent_info == "from_parent"
        anod_class2 = spec2_repo.load("child")
        anod_instance2 = anod_class2("load", "", "build")
        assert anod_instance2.parent_info == "from_parent2"

    def test_load_all(self):
        spec_repo = AnodSpecRepository(self.spec_dir)
        with pytest.raises(SandBoxError):
            spec_repo.load_all()

        spec_repo = AnodSpecRepository(self.spec2_dir)
        spec_repo.load_all()
        assert "parent" in spec_repo
        assert "child" in spec_repo
        assert "unknown" not in spec_repo

    def test_load_config(self):
        spec_repo = AnodSpecRepository(self.spec_dir)
        spec_repo.api_version = "1.4"
        anod_class = spec_repo.load("withconfig")
        anod_instance = anod_class("", "build")

        # See comments in tests/tests_e3/anod/data/withconfig.anod

        assert anod_instance.test1() == 9
        with pytest.raises(KeyError) as err:
            anod_instance.test2()
        assert "foo" in str(err.value)

        assert list(anod_instance.test3()) == ["case_foo"]

    def test_load_config_api_1_5(self):
        sync_tree(self.spec_dir, "new_spec_dir")
        Run(["e3-sandbox", "migrate", "1.5", "new_spec_dir"], output=None)
        spec_repo = AnodSpecRepository("new_spec_dir")
        spec_repo.api_version = "1.5"
        anod_class = spec_repo.load("withconfig")
        anod_instance = anod_class("", "build")
        assert anod_instance.test1() == 9
        assert anod_instance.test_suffix() == 42

    def test_sandbox_migrate_unknown_api(self):
        p = Run(["e3-sandbox", "migrate", "0.2", "foo"])
        assert "Only 1.5 is supported" in p.out

    def test_getitem_without_buildspace(self):
        """Without a build space PKG_DIR returns 'unknown'."""
        spec_repo = AnodSpecRepository(self.spec_dir)
        anod_class = spec_repo.load("parent")
        anod_instance = anod_class("", "build")
        assert anod_instance["PKG_DIR"] == "unknown"

    def test_reuse_anod(self):
        """Reject spec reusing Anod class name."""
        spec_repo = AnodSpecRepository(self.spec_dir)
        with pytest.raises(SandBoxError) as err:
            spec_repo.load("reuse_anod")
        assert "must not use Anod" in str(err)
