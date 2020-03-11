from e3.anod.context import AnodContext
from e3.anod.loader import AnodSpecRepository
from e3.anod.queries import SourceClosure, get_build_node
import os


class TestSourceClosure(object):

    spec_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "source_closure_specs")
    )

    def get_source_closure(self, name, expand_packages=True, other_builds=None):
        asr = AnodSpecRepository(self.spec_dir)
        ac = AnodContext(asr)
        anod_instance = ac.add_anod_action(name, primitive="build").data
        anod_instance = get_build_node(anod_instance, ac, anod_instance)
        if other_builds is not None:
            for b in other_builds:
                ac.add_anod_action(b, primitive="build")
        return SourceClosure(
            anod_instance=anod_instance, context=ac, expand_packages=expand_packages
        )

    def test_empty_source_closure(self):
        """Simple test with null source closure."""
        sc = self.get_source_closure("spec1")
        sources = sc.get_source_list()
        assert len(sources) == 0

    def test_simple_source_closure(self):
        """Simple test with one public and one private source."""
        sc = self.get_source_closure("spec2", other_builds=["spec1"])
        for key in sc.source_list:
            sc.resolve_source(source_name=key.src_name, data=key.src_name)

        sources = sc.get_source_list()
        published_sources = [src for src, publish in sources if publish]
        unpublished_sources = [src for src, publish in sources if not publish]

        assert len(sources) == 2
        assert len(published_sources) == 1 and published_sources[0] == "spec2-src"
        assert (
            len(unpublished_sources) == 1
            and unpublished_sources[0] == "spec2-internal-src"
        )

    def test_recursive_source_closure(self):
        sc = self.get_source_closure("spec3")

        for key in sc.source_list:
            sc.resolve_source(source_name=key.src_name, data=key.src_name)

        sources = sc.get_source_list()
        published_sources = [src for src, publish in sources if publish]
        unpublished_sources = [src for src, publish in sources if not publish]

        assert len(sources) == 4
        assert len(published_sources) == 1
        assert published_sources[0] == "spec3-src"
        assert len(unpublished_sources) == 3

        sc = self.get_source_closure("spec4")

        for key in sc.source_list:
            sc.resolve_source(source_name=key.src_name, data=key.src_name)

        sources = sc.get_source_list()
        published_sources = [src for src, publish in sources if publish]
        published_sources.sort()
        unpublished_sources = [src for src, publish in sources if not publish]

        assert len(sources) == 4
        assert len(published_sources) == 2
        assert published_sources == ["spec2-src", "spec4-src"]
        assert len(unpublished_sources) == 2

    def test_recursive_source_closure_with_package(self):
        sc = self.get_source_closure("spec5", expand_packages=True)

        for key in sc.source_list:
            sc.resolve_source(source_name=key.src_name, data=key.src_name)

        sources = sc.get_source_list()
        published_sources = [src for src, publish in sources if publish]
        published_sources.sort()
        unpublished_sources = [src for src, publish in sources if not publish]

        assert len(sources) == 4
        assert len(published_sources) == 2
        assert published_sources == ["spec2-src", "spec5-src"]
        assert len(unpublished_sources) == 2

        sc = self.get_source_closure("spec5", expand_packages=False)

        for key in sc.source_list:
            sc.resolve_source(source_name=key.src_name, data=key.src_name)

        for key in sc.package_list:
            if not key.track and not key.has_closure:
                print("skip %s" % key.anod_uid)
                continue
            name = key.anod_uid.split(".")[2]
            sc.resolve_package(
                key.anod_uid,
                [("%s-package-src" % name, True), ("%s-package-int-src" % name, False)],
            )

        sources = sc.get_source_list()
        published_sources = [src for src, publish in sources if publish]
        published_sources.sort()
        unpublished_sources = [src for src, publish in sources if not publish]

        assert len(sources) == 4
        assert len(published_sources) == 2
        assert published_sources == ["spec2-package-src", "spec5-src"]
        assert len(unpublished_sources) == 2
