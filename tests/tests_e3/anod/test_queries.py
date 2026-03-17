"""Tests for e3.anod queries."""

import os
from pathlib import Path

from e3.anod.context import AnodContext
from e3.anod.loader import AnodSpecRepository
from e3.anod.queries import SourceClosure, get_build_node

# Expected source closure sizes for different test specs
EMPTY_CLOSURE_SIZE = 0
SPEC2_SOURCE_CLOSURE_SIZE = 2
SPEC2_PUBLISHED_SOURCES = 1
SPEC3_SOURCE_CLOSURE_SIZE = 4
SPEC3_PUBLISHED_SOURCES = 1
SPEC3_UNPUBLISHED_SOURCES = 3
SPEC4_SOURCE_CLOSURE_SIZE = 4
SPEC4_PUBLISHED_SOURCES = 2
SPEC4_UNPUBLISHED_SOURCES = 2


class TestSourceClosure:
    spec_dir = os.path.abspath(Path(__file__).parent / "source_closure_specs")

    def get_source_closure(
        self, name, expand_packages=True, other_builds=None
    ) -> SourceClosure:
        asr = AnodSpecRepository(self.spec_dir)
        ac = AnodContext(asr)
        anod_instance = ac.add_anod_action(
            name, env=ac.default_env, primitive="build"
        ).data
        anod_instance = get_build_node(anod_instance, ac, anod_instance)
        if other_builds is not None:
            for b in other_builds:
                ac.add_anod_action(b, env=ac.default_env, primitive="build")
        return SourceClosure(
            anod_instance=anod_instance, context=ac, expand_packages=expand_packages
        )

    def test_empty_source_closure(self) -> None:
        """Simple test with null source closure."""
        sc = self.get_source_closure("spec1")
        sources = sc.get_source_list()
        assert len(sources) == EMPTY_CLOSURE_SIZE

    def test_simple_source_closure(self) -> None:
        """Simple test with one public and one private source."""
        sc = self.get_source_closure("spec2", other_builds=["spec1"])
        for key in sc.source_list:
            sc.resolve_source(source_name=key.src_name, data=key.src_name)

        sources = sc.get_source_list()
        published_sources = [src for src, publish in sources if publish]
        unpublished_sources = [src for src, publish in sources if not publish]

        assert len(sources) == SPEC2_SOURCE_CLOSURE_SIZE
        assert (
            len(published_sources) == SPEC2_PUBLISHED_SOURCES
            and published_sources[0] == "spec2-src"
        )
        assert (
            len(unpublished_sources) == SPEC2_PUBLISHED_SOURCES
            and unpublished_sources[0] == "spec2-internal-src"
        )

    def test_recursive_source_closure(self) -> None:
        sc = self.get_source_closure("spec3")

        for key in sc.source_list:
            sc.resolve_source(source_name=key.src_name, data=key.src_name)

        sources = sc.get_source_list()
        published_sources = [src for src, publish in sources if publish]
        unpublished_sources = [src for src, publish in sources if not publish]

        assert len(sources) == SPEC3_SOURCE_CLOSURE_SIZE
        assert len(published_sources) == SPEC3_PUBLISHED_SOURCES
        assert published_sources[0] == "spec3-src"
        assert len(unpublished_sources) == SPEC3_UNPUBLISHED_SOURCES

        sc = self.get_source_closure("spec4")

        for key in sc.source_list:
            sc.resolve_source(source_name=key.src_name, data=key.src_name)

        sources = sc.get_source_list()
        published_sources = [src for src, publish in sources if publish]
        published_sources.sort()
        unpublished_sources = [src for src, publish in sources if not publish]

        assert len(sources) == SPEC4_SOURCE_CLOSURE_SIZE
        assert len(published_sources) == SPEC4_PUBLISHED_SOURCES
        assert published_sources == ["spec2-src", "spec4-src"]
        assert len(unpublished_sources) == SPEC4_UNPUBLISHED_SOURCES

    def test_recursive_source_closure_with_package(self) -> None:
        sc = self.get_source_closure("spec5", expand_packages=True)

        for key in sc.source_list:
            sc.resolve_source(source_name=key.src_name, data=key.src_name)

        sources = sc.get_source_list()
        published_sources = [src for src, publish in sources if publish]
        published_sources.sort()
        unpublished_sources = [src for src, publish in sources if not publish]

        assert len(sources) == SPEC4_SOURCE_CLOSURE_SIZE
        assert len(published_sources) == SPEC4_PUBLISHED_SOURCES
        assert published_sources == ["spec2-src", "spec5-src"]
        assert len(unpublished_sources) == SPEC4_UNPUBLISHED_SOURCES

        sc = self.get_source_closure("spec5", expand_packages=False)

        for key in sc.source_list:
            sc.resolve_source(source_name=key.src_name, data=key.src_name)

        for key in sc.package_list:
            if not key.track and not key.has_closure:
                print(f"skip {key.anod_uid}")
                continue
            name = key.anod_uid.split(".")[1]
            sc.resolve_package(
                key.anod_uid,
                [
                    (f"{name}-package-src", True),
                    (f"{name}-package-int-src", False),
                ],
            )

        sources = sc.get_source_list()
        published_sources = [src for src, publish in sources if publish]
        published_sources.sort()
        unpublished_sources = [src for src, publish in sources if not publish]

        assert len(sources) == SPEC4_SOURCE_CLOSURE_SIZE
        assert len(published_sources) == SPEC4_PUBLISHED_SOURCES
        assert published_sources == ["spec2-package-src", "spec5-src"]
        assert len(unpublished_sources) == SPEC4_UNPUBLISHED_SOURCES

    def test_recursive_source_closure_with_download(self) -> None:
        sc = self.get_source_closure("spec6")

        for key in sc.source_list:
            sc.resolve_source(source_name=key.src_name, data=key.src_name)

        sources = sc.get_source_list()
        published_sources = [src for src, publish in sources if publish]
        published_sources.sort()
        unpublished_sources = [src for src, publish in sources if not publish]

        assert len(sources) == SPEC4_SOURCE_CLOSURE_SIZE
        assert len(published_sources) == SPEC4_PUBLISHED_SOURCES
        assert published_sources == ["spec2-src", "spec6-src"]
        assert len(unpublished_sources) == SPEC4_UNPUBLISHED_SOURCES
