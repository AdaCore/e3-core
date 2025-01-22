import os
import subprocess
import sys

from pathlib import Path

from e3.anod.driver import AnodDriver
from e3.anod.error import AnodError, SpecError
from e3.anod.sandbox import SandBox
from e3.anod.spec import Anod, __version__, check_api_version, has_primitive
from e3.env import Env
from e3.fs import cp
from e3.os.fs import ldd_output_to_posix
from e3.os.process import Run
from e3.platform_db.knowledge_base import OS_INFO

import pytest

CHECK_DLL_CLOSURE_ARGUMENTS = [
    (
        (
            (
                "/usr/bin/ls:\n"
                "\tlinux-vdso.so.1 (0xxxx)\n"
                "\tlibselinux.so.1 => /lib/x86_64-linux-gnu/libselinux.so.1 (0xxxx)\n"
                "\tlibc.so.6 => /lib/x86_64-linux-gnu/libc.so.6 (0xxxx)\n"
                "\tlibpcre2-8.so.0 => /lib/x86_64-linux-gnu/libpcre2-8.so.0 (0xxxx)\n"
                "\t/lib64/ld-linux-x86-64.so.2 (0xxxx)\n"
                "/usr/bin/gcc:\n"
                "\tlinux-vdso.so.1 (0xxxx)\n"
                "\tlibc.so.6 => /lib/x86_64-linux-gnu/libc.so.6 (0xxxx)\n"
                "\t/lib64/ld-linux-x86-64.so.2 (0xxxx)\n"
            ),
            ["libc.so.6"],
        ),
        (
            (
                "- libpcre2-8.so.0: /lib/x86_64-linux-gnu/libpcre2-8.so.0"
                if sys.platform != "win32"
                else None
            ),
        ),
    ),
    (
        (
            None,
            [
                "libstdc++.so.6",
                "libgcc_s.so.1",
                "libpthread.so.0",
                "libdl.so.2",
                "libm.so.6",
                # Windows ignored Dlls.
                "CRYPTBASE.DLL",
                "Comctl32.dll",
                "FreeImage.dll",
                "FreeImagePlus.dll",
                "GDI32.dll",
                "IMM32.DLL",
                "IMM32.dll",
                "IMM32.dll",
                "KERNEL32.DLL",
                "KERNELBASE.dll",
                "Msimg32.DLL",
                "OLEAUT32.dll",
                "RPCRT4.dll",
                "SHLWAPI.dll",
                "USER32.dll",
                "UxTheme.dll",
                "VCRUNTIME140.dll",
                "VCRUNTIME140_1.dll",
                "VERSION.dll",
                "WS2_32.dll",
                "apphelp.dll",
                "bcrypt.dll",
                "combase.dll",
                "gdi32full.dll",
                "libcrypto-3.dll",
                "libiconv2.dll",
                "libintl3.dll",
                "msvcp_win.dll",
                "msvcrt.dll",
                "ntdll.dll",
                "ole32.dll",
                "pcre3.dll",
                "python311.dll",
                "pywintypes311.dll",
                "regex2.dll",
                "sechost.dll",
                "ucrtbase.dll",
                "win32u.dll",
            ],
        ),
        (None,),
    ),
    (
        (
            (
                "python3.dll:\n"
                "\tntdll.dll => /Windows/SYSTEM32/ntdll.dll (0xxxx)\n"
                "\tKERNEL32.DLL => /Windows/System32/KERNEL32.DLL (0xxxx)\n"
                "\tKERNELBASE.dll => /Windows/System32/KERNELBASE.dll (0xxxx)\n"
                "\tmsvcrt.dll => /Windows/System32/msvcrt.dll (0xxxx)\n"
            ),
            [],
        ),
        (
            (
                "- KERNEL32.DLL: C:/Windows/System32/KERNEL32.DLL"
                if sys.platform == "win32"
                else None
            ),
        ),
    ),
    (
        (
            (
                "/usr/bin/ls:\n"
                "\tlinux-vdso.so.1 (0xxxx)\n"
                "\tlibselinux.so.1 => /lib/x86_64-linux-gnu/libselinux.so.1 (0xxxx)\n"
                "\tlibc.so.6 => /lib/x86_64-linux-gnu/libc.so.6 (0xxxx)\n"
                "\tlibpcre2-8.so.0 => not found\n"
                "\t/lib64/ld-linux-x86-64.so.2 (0xxxx)\n"
            ),
            ["libc.so.6", "libselinux.so.1"],
        ),
        ("- libpcre2-8.so.0: not found",),
    ),
    (
        (
            (
                "/usr/bin/ls:\n"
                "\tlinux-vdso.so.1 (0xxxx)\n"
                "\tlibselinux.so.1 => /lib/x86_64-linux-gnu/libselinux.so.1 (0xxxx)\n"
                "\tlibc.so.6 => /lib/x86_64-linux-gnu/libc.so.6 (0xxxx)\n"
                "\tlibpcre2-8.so.0 => not found\n"
                "\t/lib64/ld-linux-x86-64.so.2 (0xxxx)\n"
            ),
            ["libc.so.6", "libselinux.so.1", "libpcre2-8.so.0"],
        ),
        (None,),
    ),
]


def test_simple_spec():
    class Simple(Anod):
        test_qualifier_format = (("with_bar", False),)

        build_source_list = [
            Anod.Source("foo-src", publish=False),
            Anod.Source("bar-src", publish=True),
        ]

        @property
        def test_source_list(self):
            result = [Anod.Source("foo-test-src", publish=False)]
            if self.parsed_qualifier.get("with_bar"):
                result.append(Anod.Source("bar-test-src", publish=False))
            return result

    simple_build = Simple("", kind="build")
    assert len(simple_build.build_source_list) == 2

    simple_test = Simple("", kind="test")
    assert len(simple_test.test_source_list) == 1

    simple_test_with_bar = Simple("with_bar=true", kind="test")
    assert len(simple_test_with_bar.test_source_list) == 2


def test_spec_buildvars():
    """Build vars are used by the driver and not visible in deps."""

    class MySpec(Anod):
        build_deps = [Anod.BuildVar("key", "value")]

        @Anod.primitive()
        def build(self):
            pass

    ms = MySpec("", kind="build")
    assert len(ms.deps) == 0


# noinspection PyUnusedLocal
@pytest.mark.parametrize("arguments,expected", CHECK_DLL_CLOSURE_ARGUMENTS)
def test_spec_check_dll_closure(ldd, arguments: tuple, expected: tuple) -> None:  # type: ignore[no-untyped-def]
    """Create a simple spec with dependency to python and run dll closure."""
    ldd_output, ignored = arguments
    (errors,) = expected
    test_spec: Anod = Anod("", kind="install")
    test_spec.sandbox = SandBox(root_dir=os.getcwd())

    if ldd_output is None:
        # Use the current executable lib directory.
        exe_path: Path = Path(sys.executable)
        lib_path: Path = Path(
            exe_path.parent.parent, "lib" if sys.platform != "win32" else ""
        )
        try:
            test_spec.check_shared_libraries_closure(
                prefix=str(lib_path), ignored_libs=ignored, ldd_output=None
            )
        except AnodError as ae:
            # As the list of shared libraries used by the interpreter varies
            # from a host to another, we may catch exceptions. In that case,
            # just make sure the libraries listed in the ignored list do not
            # appear in the error message.
            if len(ae.messages) > 0:
                error_messages: list[str] = ae.messages[0].splitlines()
                culprit_dlls: list[str] = []
                dll_name: str
                for msg in error_messages:
                    if msg.strip().startswith("- "):
                        dll_name = msg.strip()[2:].split(":")[0].strip()
                        if dll_name not in culprit_dlls:
                            culprit_dlls.append(dll_name)
                # Check that none of the dlls listed in the error message
                # actually belongs to the ignored dlls.
                for culprit_dll in culprit_dlls:
                    if culprit_dll in ignored:
                        raise Exception(
                            f"Shared library {culprit_dll} is listed in the "
                            "dll closure errors, while it should be ignored"
                        ) from ae
            else:
                raise ae
    elif errors:
        with pytest.raises(AnodError) as anod_error:
            test_spec.check_shared_libraries_closure(
                prefix=None, ignored_libs=ignored, ldd_output=ldd_output
            )
        assert errors in anod_error.value.args[0]
    else:
        # There is an ldd_output, but no errors may be raised on unix hosts.
        test_spec.check_shared_libraries_closure(
            prefix=None, ignored_libs=ignored, ldd_output=ldd_output
        )


# noinspection PyUnusedLocal
def test_spec_check_dll_closure_single_file(ldd) -> None:  # type: ignore[no-untyped-def]
    """Create a simple spec with dependency to python and run dll closure."""
    name: str | None = None
    path: str | None = None

    test_spec: Anod = Anod("", kind="install")
    test_spec.sandbox = SandBox(root_dir=os.getcwd())

    # Get the ldd output of the current executable.
    ldd_output = ldd_output_to_posix(Run(["ldd"] + [sys.executable]).out or "")

    # Extract the first dll with a path from the ldd output.
    for line in ldd_output.splitlines():
        if " => " in line:
            name, path = line.strip().split(" => ", 1)
            # Remove the load address from the file path.
            path = path.split("(")[0].strip()
            break

    if name is None or path is None:
        # Skip test.
        pytest.skip("No shared library to analyse")

    # Copy that file in here. As the share lib may have a name like
    # my_shlib.so.1.0, better rename it simply my_shlib.so.
    shlib_ext: str = f"{OS_INFO[Env().build.os.name]['dllext']}"
    prefix: Path = Path(Path.cwd(), "prefix")
    name = name.split(shlib_ext)[0] + shlib_ext
    shlib_path: str = Path(prefix, name).as_posix()
    prefix.mkdir()
    cp(path, shlib_path)

    # And now run check_shared_libraries_closure() on that shared library.
    # As we do not define exceptions (ignored system libraries), and that the
    # library may link with system libraries, take all possibilities into
    # account:
    # - exception: the analysis was ok, since it detected system libraries
    # - result: make sure there is only one element in the result

    try:
        result = test_spec.check_shared_libraries_closure(prefix=str(prefix))
        assert len(result) == 1
        assert Path(shlib_path).as_posix() in result
    except AnodError as ae:
        assert shlib_path in ae.messages[0]


def test_spec_wrong_dep():
    """Check exception message when wrong dependency is set."""
    with pytest.raises(SpecError) as err:
        Anod.Dependency("foo", require="invalid")

    assert (
        "require should be build_tree, download, installation,"
        " or source_pkg not invalid" in str(err)
    )


def test_primitive():
    class NoPrimitive(Anod):
        @staticmethod
        def build():
            return 2

    no_primitive = NoPrimitive("", "build")
    assert has_primitive(no_primitive, "build") is False

    class WithPrimitive(Anod):
        build_qualifier_format = (("error", False),)

        package = Anod.Package(prefix="mypackage", version=lambda: "42")

        @Anod.primitive()
        def build(self):
            if "error" in self.parsed_qualifier:
                raise ValueError(self.parsed_qualifier["error"])
            elif "error2" in self.parsed_qualifier:
                self.shell(sys.executable, "-c", "import sys; sys.exit(2)")
            else:
                hello = self.shell(
                    sys.executable, "-c", 'print("world")', output=subprocess.PIPE
                )
                return hello.out.strip()

    with_primitive = WithPrimitive("", "build")
    with_primitive2 = WithPrimitive("error=foobar", "build")
    with_primitive3 = WithPrimitive("error2", "build")
    with_primitive4 = WithPrimitive("error3", "build")

    Anod.sandbox = SandBox(root_dir=os.getcwd())
    Anod.sandbox.spec_dir = os.path.join(os.path.dirname(__file__), "data")
    Anod.sandbox.create_dirs()
    # Activate the logging
    AnodDriver(anod_instance=with_primitive, store=None).activate(Anod.sandbox, None)
    AnodDriver(anod_instance=with_primitive2, store=None).activate(Anod.sandbox, None)
    AnodDriver(anod_instance=with_primitive3, store=None).activate(Anod.sandbox, None)
    AnodDriver(anod_instance=with_primitive4, store=None)  # don't activate

    with_primitive.build_space.create()

    assert has_primitive(with_primitive, "build") is True
    assert with_primitive.build() == "world"

    with_primitive2.build_space.create()

    with pytest.raises(AnodError):
        with_primitive2.build()

    assert with_primitive2.package.name.startswith("mypackage")

    # Check __getitem__
    # PKG_DIR returns the path to the pkg directory
    assert with_primitive2["PKG_DIR"].endswith("pkg")

    with_primitive3.build_space.create()
    with pytest.raises(AnodError):
        with_primitive3.build()


def test_api_version():
    # __version__ is supported
    check_api_version(__version__)

    with pytest.raises(AnodError):
        check_api_version("0.0")


def test_spec_qualifier():
    class GeneratorEnabled(Anod):
        enable_name_generator = True

        def declare_qualifiers_and_components(self, qm):
            qm.declare_tag_qualifier(
                "q1",
                description="???",
            )

    class GeneratorDisabled(Anod):
        enable_name_generator = False

    spec_enable = GeneratorEnabled(qualifier="q1", kind="build")
    spec_disable = GeneratorDisabled(qualifier="q1", kind="build")

    assert spec_enable.args == {"q1": True}
    assert spec_disable.args == {"q1": ""}


def test_missing_property():
    class NoProperty(Anod):
        def source_pkg_build(self) -> list:  # type: ignore[override]
            return []

    noproperty = NoProperty(qualifier="", kind="source")
    assert noproperty.source_pkg_build == []
