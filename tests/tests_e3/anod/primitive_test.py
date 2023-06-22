import os

from pathlib import Path

from e3.anod.driver import AnodDriver
from e3.anod.sandbox import SandBox
from e3.anod.spec import Anod


def test_primitive_with_pre():
    """Test an Anod primitive with a *pre* parameter of type string."""
    build_called: str = "build called"
    setup_called: str = "setup called + "

    class SimpleWithPreStr(Anod):
        # Define a global string to be updated by both methods.
        common: str = ""

        @Anod.primitive()
        def setup(self, *_args) -> None:
            self.common += setup_called

        @Anod.primitive(pre="setup")
        def build(self) -> str:
            self.common += build_called
            self.log.debug(" build returning {0}".format(self.common))
            return self.common

    class SimpleWithPreCallable(Anod):
        # Define a global string to be updated by both methods.
        common: str = ""

        @Anod.primitive()
        def setup(self, *_args) -> None:
            self.common = setup_called

        # noinspection PyTypeChecker
        @Anod.primitive(pre=setup)
        def build(self) -> str:
            self.common += build_called
            self.log.debug(" build returning {0}".format(self.common))
            return self.common

    spec_dir = Path(Path(__file__).parent, "data").resolve()

    with_pre_str = SimpleWithPreStr("", "build")
    with_pre_callable = SimpleWithPreCallable("", "build")

    Anod.sandbox = SandBox(root_dir=os.getcwd())
    Anod.sandbox.spec_dir = str(spec_dir.resolve())
    Anod.sandbox.create_dirs()

    AnodDriver(anod_instance=with_pre_str, store=None).activate(Anod.sandbox, None)
    AnodDriver(anod_instance=with_pre_callable, store=None).activate(Anod.sandbox, None)

    for anod_class in with_pre_str, with_pre_callable:
        anod_class.build_space.create()
        anod_class.build()
        assert anod_class.common == setup_called + build_called


def test_primitive_with_post():
    """Test an Anod primitive with a *post* parameter of any type."""
    build_called: str = "build called"
    install_called: str = " + install called"

    class SimpleWithPostStr(Anod):
        # Define a global string to be updated by both methods.
        common: str = ""

        @Anod.primitive()
        def install(self, *_args) -> None:
            self.common += install_called

        @Anod.primitive(post="install")
        def build(self) -> str:
            self.common += build_called
            self.log.debug(" build returning {0}".format(self.common))
            return self.common

    class SimpleWithPostCallable(Anod):
        # Define a global string to be updated by both methods.
        common: str = ""

        @Anod.primitive()
        def install(self, *_args) -> None:
            self.common += install_called

        @Anod.primitive(post=install)
        def build(self) -> str:
            self.common += build_called
            self.log.debug(" build returning {0}".format(self.common))
            return self.common

    spec_dir = Path(Path(__file__).parent, "data").resolve()

    with_post_str = SimpleWithPostStr("", "build")
    with_post_callable = SimpleWithPostCallable("", "build")

    Anod.sandbox = SandBox(root_dir=os.getcwd())
    Anod.sandbox.spec_dir = str(spec_dir.resolve())
    Anod.sandbox.create_dirs()

    AnodDriver(anod_instance=with_post_str, store=None).activate(Anod.sandbox, None)
    AnodDriver(anod_instance=with_post_callable, store=None).activate(
        Anod.sandbox, None
    )

    for anod_class in with_post_str, with_post_callable:
        anod_class.build_space.create()
        anod_class.build()
        assert anod_class.common == build_called + install_called


def test_primitive_with_pre_and_post():
    """Test an Anod primitive with a *post* parameter of any type."""
    build_called: str = "build called"
    install_called: str = " + install called"
    setup_called: str = "setup called + "

    class SimpleWithPreStrPostStr(Anod):
        # Define a global string to be updated by both methods.
        common: str = ""

        @Anod.primitive()
        def setup(self, *_args) -> None:
            self.common += setup_called

        @Anod.primitive()
        def install(self, *_args) -> None:
            self.common += install_called

        @Anod.primitive(pre="setup", post="install")
        def build(self) -> str:
            self.common += build_called
            self.log.debug(" build returning {0}".format(self.common))
            return self.common

    class SimpleWithPreCallablePostStr(Anod):
        # Define a global string to be updated by both methods.
        common: str = ""

        @Anod.primitive()
        def setup(self, *_args) -> None:
            self.common += setup_called

        @Anod.primitive()
        def install(self, *_args) -> None:
            self.common += install_called

        # noinspection PyTypeChecker
        @Anod.primitive(pre=setup, post="install")
        def build(self) -> str:
            self.common += build_called
            self.log.debug(" build returning {0}".format(self.common))
            return self.common

    class SimpleWithPreCallablePostCallable(Anod):
        # Define a global string to be updated by both methods.
        common: str = ""

        @Anod.primitive()
        def setup(self, *_args) -> None:
            self.common += setup_called

        @Anod.primitive()
        def install(self, *_args) -> None:
            self.common += install_called

        # noinspection PyTypeChecker
        @Anod.primitive(pre=setup, post=install)
        def build(self) -> str:
            self.common += build_called
            self.log.debug(" build returning {0}".format(self.common))
            return self.common

    class SimpleWithPreStrPostCallable(Anod):
        # Define a global string to be updated by both methods.
        common: str = ""

        @Anod.primitive()
        def setup(self, *_args) -> None:
            self.common += setup_called

        @Anod.primitive()
        def install(self, *_args) -> None:
            self.common += install_called

        # noinspection PyTypeChecker
        @Anod.primitive(pre="setup", post=install)
        def build(self) -> str:
            self.common += build_called
            self.log.debug(" build returning {0}".format(self.common))
            return self.common

    spec_dir = Path(Path(__file__).parent, "data").resolve()

    pre_str_post_str = SimpleWithPreStrPostStr("", "build")
    pre_callable_post_str = SimpleWithPreCallablePostStr("", "build")
    pre_callable_post_callable = SimpleWithPreCallablePostCallable("", "build")
    pre_str_post_callable = SimpleWithPreStrPostCallable("", "build")

    Anod.sandbox = SandBox(root_dir=os.getcwd())
    Anod.sandbox.spec_dir = str(spec_dir.resolve())
    Anod.sandbox.create_dirs()

    AnodDriver(anod_instance=pre_str_post_str, store=None).activate(Anod.sandbox, None)
    AnodDriver(anod_instance=pre_callable_post_str, store=None).activate(
        Anod.sandbox, None
    )
    AnodDriver(anod_instance=pre_callable_post_callable, store=None).activate(
        Anod.sandbox, None
    )
    AnodDriver(anod_instance=pre_str_post_callable, store=None).activate(
        Anod.sandbox, None
    )

    for anod_class in (
        pre_str_post_str,
        pre_callable_post_str,
        pre_callable_post_callable,
        pre_str_post_callable,
    ):
        anod_class.build_space.create()
        anod_class.build()
        assert anod_class.common == setup_called + build_called + install_called
