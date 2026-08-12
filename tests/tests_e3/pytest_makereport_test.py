"""Tests for the pytest_runtest_makereport hook."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pytest

pytest_plugins = ("pytester",)


def test_makereport_no_results_dir(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Nothing is written when RESULTS_DIR is not set.

    :param pytester: pytest fixture to run in-subprocess pytest tests
    :param monkeypatch: pytest monkeypatch fixture
    """
    monkeypatch.delenv("RESULTS_DIR", raising=False)
    pytester.makepyfile(test_example="def test_pass(): pass")
    result = pytester.runpytest()
    result.assert_outcomes(passed=1)


def test_makereport_nonexistent_results_dir(
    pytester: pytest.Pytester,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Nothing is written when RESULTS_DIR points to a nonexistent directory.

    :param pytester: pytest fixture to run in-subprocess pytest tests
    :param tmp_path: pytest temporary path fixture
    :param monkeypatch: pytest monkeypatch fixture
    """
    nonexistent = str(tmp_path / "nonexistent")
    monkeypatch.setenv("RESULTS_DIR", nonexistent)
    pytester.makepyfile(test_example="def test_pass(): pass")
    result = pytester.runpytest()
    result.assert_outcomes(passed=1)
    assert not Path(nonexistent, "results").exists()


def test_makereport_passed_writes_result(
    pytester: pytest.Pytester,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A passing test writes a PASSED entry to the results file.

    :param pytester: pytest fixture to run in-subprocess pytest tests
    :param tmp_path: pytest temporary path fixture
    :param monkeypatch: pytest monkeypatch fixture
    """
    results_dir = tmp_path / "results_dir"
    results_dir.mkdir()
    monkeypatch.setenv("RESULTS_DIR", str(results_dir))
    pytester.makepyfile(test_example="def test_pass(): pass")
    result = pytester.runpytest()
    result.assert_outcomes(passed=1)
    content = (results_dir / "results").read_text()
    assert content == "test_example.py++test_pass:PASSED\n"


def test_makereport_failed_writes_result_and_diff(
    pytester: pytest.Pytester,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failing test writes a FAILED entry and a .diff file with the failure text.

    :param pytester: pytest fixture to run in-subprocess pytest tests
    :param tmp_path: pytest temporary path fixture
    :param monkeypatch: pytest monkeypatch fixture
    """
    results_dir = tmp_path / "results_dir"
    results_dir.mkdir()
    monkeypatch.setenv("RESULTS_DIR", str(results_dir))
    pytester.makepyfile(
        test_example="def test_fail(): assert False, 'expected failure'"
    )
    result = pytester.runpytest()
    result.assert_outcomes(failed=1)
    content = (results_dir / "results").read_text()
    assert content == "test_example.py++test_fail:FAILED\n"
    diff_files = list(results_dir.glob("*.diff"))
    assert len(diff_files) == 1
    assert "expected failure" in diff_files[0].read_text()


def test_makereport_multiple_tests_appended(
    pytester: pytest.Pytester,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Results for multiple tests are all appended to the same results file.

    :param pytester: pytest fixture to run in-subprocess pytest tests
    :param tmp_path: pytest temporary path fixture
    :param monkeypatch: pytest monkeypatch fixture
    """
    results_dir = tmp_path / "results_dir"
    results_dir.mkdir()
    monkeypatch.setenv("RESULTS_DIR", str(results_dir))
    pytester.makepyfile(
        test_example="""
def test_first(): pass
def test_second(): assert False
"""
    )
    pytester.runpytest()
    lines = (results_dir / "results").read_text().splitlines()
    assert "test_example.py++test_first:PASSED" in lines
    assert "test_example.py++test_second:FAILED" in lines


def test_makereport_setup_failure_sets_error_state(
    pytester: pytest.Pytester,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A fixture setup failure sets _state.test_errors, causing exit code 3 with --e3.

    :param pytester: pytest fixture to run in-subprocess pytest tests
    :param tmp_path: pytest temporary path fixture
    :param monkeypatch: pytest monkeypatch fixture
    """
    results_dir = tmp_path / "results_dir"
    results_dir.mkdir()
    monkeypatch.setenv("RESULTS_DIR", str(results_dir))
    pytester.makepyfile(
        test_example="""
import pytest

@pytest.fixture
def broken_fixture():
    raise RuntimeError("fixture setup failure")

def test_with_broken_fixture(broken_fixture):
    pass
"""
    )
    result = pytester.runpytest("--e3")
    assert result.ret == 3  # noqa: PLR2004


def test_makereport_nodeid_slash_replaced(
    pytester: pytest.Pytester,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Slashes in the node ID (subdirectory separators) are replaced with tildes.

    :param pytester: pytest fixture to run in-subprocess pytest tests
    :param tmp_path: pytest temporary path fixture
    :param monkeypatch: pytest monkeypatch fixture
    """
    results_dir = tmp_path / "results_dir"
    results_dir.mkdir()
    monkeypatch.setenv("RESULTS_DIR", str(results_dir))
    subdir = pytester.path / "subdir"
    subdir.mkdir()
    (subdir / "test_sub.py").write_text("def test_pass(): pass")
    result = pytester.runpytest()
    result.assert_outcomes(passed=1)
    content = (results_dir / "results").read_text()
    assert content == "subdir~test_sub.py++test_pass:PASSED\n"


def test_makereport_nodeid_double_colon_replaced(
    pytester: pytest.Pytester,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Double colons in the node ID (class/method separators) are replaced with '++'.

    :param pytester: pytest fixture to run in-subprocess pytest tests
    :param tmp_path: pytest temporary path fixture
    :param monkeypatch: pytest monkeypatch fixture
    """
    results_dir = tmp_path / "results_dir"
    results_dir.mkdir()
    monkeypatch.setenv("RESULTS_DIR", str(results_dir))
    pytester.makepyfile(
        test_example="""
class TestGroup:
    def test_method(self): pass
"""
    )
    result = pytester.runpytest()
    result.assert_outcomes(passed=1)
    content = (results_dir / "results").read_text()
    assert content == "test_example.py++TestGroup++test_method:PASSED\n"


def test_makereport_nodeid_single_colon_in_param_replaced(
    pytester: pytest.Pytester,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Single colons remaining after '::' substitution (e.g. in param IDs) become '+'.

    :param pytester: pytest fixture to run in-subprocess pytest tests
    :param tmp_path: pytest temporary path fixture
    :param monkeypatch: pytest monkeypatch fixture
    """
    results_dir = tmp_path / "results_dir"
    results_dir.mkdir()
    monkeypatch.setenv("RESULTS_DIR", str(results_dir))
    pytester.makepyfile(
        test_example="""
import pytest

@pytest.mark.parametrize("val", ["key:value"])
def test_param(val): pass
"""
    )
    result = pytester.runpytest()
    result.assert_outcomes(passed=1)
    content = (results_dir / "results").read_text()
    # ':' in param → '+'; no '+' in original, so no %2B escaping here
    assert content == "test_example.py++test_param[key+value]:PASSED\n"


def test_makereport_colliding_nodeids_are_distinct(
    pytester: pytest.Pytester,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Node IDs that differ only by ':' vs '+' in a param produce distinct result names.

    Before the fix, both mapped to the same name and the second .diff would
    silently overwrite the first.

    :param pytester: pytest fixture to run in-subprocess pytest tests
    :param tmp_path: pytest temporary path fixture
    :param monkeypatch: pytest monkeypatch fixture
    """
    results_dir = tmp_path / "results_dir"
    results_dir.mkdir()
    monkeypatch.setenv("RESULTS_DIR", str(results_dir))
    pytester.makepyfile(
        test_example="""
import pytest

@pytest.mark.parametrize("val", ["key:value", "key+value"])
def test_param(val): assert False, f"failure for {val!r}"
"""
    )
    result = pytester.runpytest()
    result.assert_outcomes(failed=2)

    lines = (results_dir / "results").read_text().splitlines()
    # ':' → '+' and '+' → '%2B', so the two names must be distinct
    colon_name = "test_example.py++test_param[key+value]"
    plus_name = "test_example.py++test_param[key%2Bvalue]"
    assert f"{colon_name}:FAILED" in lines
    assert f"{plus_name}:FAILED" in lines

    diff_files = {f.stem for f in results_dir.glob("*.diff")}
    assert colon_name in diff_files
    assert plus_name in diff_files
