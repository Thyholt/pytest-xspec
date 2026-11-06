"""Run the example projects and check that their advertised behavior stays true."""

import json
import sys
from collections.abc import Callable
from pathlib import Path
from shutil import copytree, ignore_patterns
from types import ModuleType

import pytest

from examples import (
    acceptance_only,
    combine_reports,
    missing_requirement,
    partial_verification,
    quickstart,
    specification_document,
)

pytest_plugins = ["pytester"]


@pytest.fixture
def example_project(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> Callable[[ModuleType], pytest.Pytester]:
    monkeypatch.delenv("PYTEST_DISABLE_PLUGIN_AUTOLOAD", raising=False)
    monkeypatch.delenv("PYTEST_ADDOPTS", raising=False)
    monkeypatch.delenv("PYTEST_PLUGINS", raising=False)

    def copy(example: ModuleType) -> pytest.Pytester:
        (example_path,) = example.__path__
        copytree(
            example_path,
            pytester.path,
            dirs_exist_ok=True,
            ignore=ignore_patterns(
                "__pycache__",
                ".pytest_cache",
                "report.json",
                "report-a.json",
                "report-b.json",
                "combined.json",
            ),
        )
        return pytester

    return copy


def test_quickstart_verifies_the_pizza(
    example_project: Callable[[ModuleType], pytest.Pytester],
) -> None:
    project = example_project(quickstart)

    result = project.runpytest_subprocess("--xspec-strict", "--xspec-json=report.json")

    assert result.ret == pytest.ExitCode.OK
    result.assert_outcomes(passed=1)
    report = json.loads((project.path / "report.json").read_text(encoding="utf-8"))
    assert report == json.loads(
        (Path(quickstart.__path__[0]) / "report.json").read_text(encoding="utf-8")
    )
    assert report["requirements"] == {
        "REQ-001": {
            "status": "PASSED",
            "tests": [
                {"nodeid": "test_behavior.py::test_pizza_has_two_slices", "outcome": "PASSED"}
            ],
        },
    }
    assert report["summary"]["verified"] is True
    assert report["summary"]["coverage"] == 100.0
    result.stdout.fnmatch_lines(["*REQ-001*PASSED*", "*Coverage:*100.0%*"])


def test_specification_document_verifies_the_addition_requirements(
    example_project: Callable[[ModuleType], pytest.Pytester],
) -> None:
    project = example_project(specification_document)

    result = project.runpytest_subprocess("--xspec-strict", "--xspec-json=report.json")

    assert result.ret == pytest.ExitCode.OK
    result.assert_outcomes(passed=2)
    report = json.loads((project.path / "report.json").read_text(encoding="utf-8"))
    assert report["requirements"] == {
        "REQ-001": {
            "status": "PASSED",
            "tests": [
                {
                    "nodeid": "test_behavior.py::test_adding_two_integers_returns_their_sum",
                    "outcome": "PASSED",
                },
                {
                    "nodeid": "test_behavior.py::test_adding_zero_preserves_the_value",
                    "outcome": "PASSED",
                },
            ],
        },
        "REQ-002": {
            "status": "PASSED",
            "tests": [
                {
                    "nodeid": "test_behavior.py::test_adding_zero_preserves_the_value",
                    "outcome": "PASSED",
                },
            ],
        },
    }
    assert report["summary"]["verified"] is True
    assert report["summary"]["coverage"] == 100.0
    result.stdout.fnmatch_lines(["*REQ-001*PASSED*2*", "*REQ-002*PASSED*1*"])


def test_missing_requirement_reports_the_other_sock(
    example_project: Callable[[ModuleType], pytest.Pytester],
) -> None:
    project = example_project(missing_requirement)

    result = project.runpytest_subprocess("--xspec-strict", "--xspec-json=report.json")

    assert result.ret == pytest.ExitCode.TESTS_FAILED
    result.assert_outcomes(passed=1)
    report = json.loads((project.path / "report.json").read_text(encoding="utf-8"))
    assert report["requirements"] == {
        "REQ-001": {
            "status": "PASSED",
            "tests": [
                {"nodeid": "test_behavior.py::test_one_sock_survives", "outcome": "PASSED"},
            ],
        },
        "REQ-002": {"status": "MISSING", "tests": []},
    }
    assert report["summary"]["verified"] is False
    assert report["summary"]["coverage"] == 50.0
    result.stdout.fnmatch_lines(["*REQ-002*MISSING*", "*Coverage:*50.0%*"])


def test_partial_verification_keeps_the_cat_unverified(
    example_project: Callable[[ModuleType], pytest.Pytester],
) -> None:
    project = example_project(partial_verification)

    result = project.runpytest_subprocess("--xspec-strict", "--xspec-json=report.json")

    assert result.ret == pytest.ExitCode.TESTS_FAILED
    result.assert_outcomes(passed=1, skipped=1)
    report = json.loads((project.path / "report.json").read_text(encoding="utf-8"))
    assert report["requirements"] == {
        "REQ-001": {
            "status": "SKIPPED",
            "tests": [
                {"nodeid": "test_behavior.py::test_cat_has_a_name", "outcome": "PASSED"},
                {"nodeid": "test_behavior.py::test_cat_attends_meetings", "outcome": "SKIPPED"},
            ],
        },
    }
    assert report["summary"]["verified"] is False
    assert report["summary"]["coverage"] == 0.0
    result.stdout.fnmatch_lines(["*REQ-001*SKIPPED*", "*Coverage:*0.0%*"])


def test_acceptance_only_verifies_the_duck_without_the_moon_test(
    example_project: Callable[[ModuleType], pytest.Pytester],
) -> None:
    project = example_project(acceptance_only)

    result = project.runpytest_subprocess(
        "-m", "xspec", "--xspec-strict", "--xspec-json=report.json"
    )

    assert result.ret == pytest.ExitCode.OK
    result.assert_outcomes(passed=1, deselected=1)
    report = json.loads((project.path / "report.json").read_text(encoding="utf-8"))
    assert report["requirements"] == {
        "REQ-001": {
            "status": "PASSED",
            "tests": [{"nodeid": "test_behavior.py::test_duck_says_quack", "outcome": "PASSED"}],
        },
    }
    assert report["summary"]["verified"] is True
    assert report["summary"]["coverage"] == 100.0


def test_plain_pytest_in_acceptance_only_still_fails_the_moon_test(
    example_project: Callable[[ModuleType], pytest.Pytester],
) -> None:
    project = example_project(acceptance_only)

    result = project.runpytest_subprocess("--xspec-strict", "--xspec-json=report.json")

    assert result.ret == pytest.ExitCode.TESTS_FAILED
    result.assert_outcomes(passed=1, failed=1)
    report = json.loads((project.path / "report.json").read_text(encoding="utf-8"))
    assert report["requirements"] == {
        "REQ-001": {
            "status": "PASSED",
            "tests": [{"nodeid": "test_behavior.py::test_duck_says_quack", "outcome": "PASSED"}],
        },
    }
    assert report["summary"]["verified"] is True
    result.stdout.fnmatch_lines(["*test_moon_is_made_of_cheese*", "*REQ-001*PASSED*"])


def test_complementary_bench_runs_verify_the_requirement_together(
    example_project: Callable[[ModuleType], pytest.Pytester],
) -> None:
    project = example_project(combine_reports)
    first = project.runpytest_subprocess(
        "-k", "delivery_volume", "--xspec-run-id=run-a", "--xspec-json=report-a.json"
    )
    second = project.runpytest_subprocess(
        "-k", "occlusion_alarm", "--xspec-run-id=run-b", "--xspec-json=report-b.json"
    )
    assert first.ret == second.ret == pytest.ExitCode.OK

    result = project.run(
        sys.executable,
        "-m",
        "pytest_xspec",
        "combine",
        "report-a.json",
        "report-b.json",
        "--output=combined.json",
        "--xspec-strict",
    )

    assert result.ret == pytest.ExitCode.OK
    report = json.loads((project.path / "combined.json").read_text(encoding="utf-8"))
    assert report == json.loads(
        (Path(combine_reports.__path__[0]) / "combined.json").read_text(encoding="utf-8")
    )
    result.stdout.fnmatch_lines(["*REQ-001*PASSED*2*", "*Coverage:*100.0%*"])
