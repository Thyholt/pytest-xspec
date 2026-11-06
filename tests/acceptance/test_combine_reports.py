"""Separate runs retain their observations while producing one verification verdict."""

import pytest

from tests.acceptance.combine_support import (
    combine,
    read_combined,
    record_run,
    simulate_outcome,
)
from tests.acceptance.scenarios.combine_reports import (
    collection_error,
    complementary,
    interrupted,
    outcomes,
)
from tests.acceptance.scenarios.reporting import empty_inventory
from tests.acceptance.scenarios.run_identity import selected
from tests.acceptance.types import UserProject


@pytest.mark.parametrize("inputs", [("run-a.json", "run-b.json"), ("run-b.json", "run-a.json")])
def test_complementary_runs_verify_a_requirement_in_either_input_order(
    user_project: UserProject, inputs: tuple[str, str]
) -> None:
    project = user_project(["REQ-001"], complementary)
    record_run(project, "run-a", "-k", "first")
    record_run(project, "run-b", "-k", "second")

    result = combine(project, *inputs, "--output=combined.json", "--xspec-strict")

    assert result.ret == 0
    report = read_combined(project.path / "combined.json")
    assert report["requirements"] == {"REQ-001": {"status": "PASSED"}}
    assert report["summary"] == {
        "requirements": 1,
        "passed": 1,
        "unverified": 0,
        "coverage": 100.0,
        "verified": True,
        "collection_errors": 0,
    }
    result.stdout.fnmatch_lines(["*REQ-001*PASSED*2", "*Coverage: 100.0%*"])


def test_combination_preserves_each_source_report_in_input_order(user_project: UserProject) -> None:
    project = user_project(["REQ-001"], complementary)
    first = record_run(project, "run-a", "-k", "first", "--xspec-select=REQ-001")
    second = record_run(project, "run-b", "-k", "second")
    first_contents = (project.path / "run-a.json").read_bytes()
    second_contents = (project.path / "run-b.json").read_bytes()

    result = combine(project, "run-b.json", "run-a.json", "--output=combined.json")

    assert result.ret == 0
    report = read_combined(project.path / "combined.json")
    assert report["runs"] == [second, first]
    assert (project.path / "run-a.json").read_bytes() == first_contents
    assert (project.path / "run-b.json").read_bytes() == second_contents


@pytest.mark.parametrize(
    "inputs", [("adverse.json", "passed.json"), ("passed.json", "adverse.json")]
)
@pytest.mark.parametrize(
    ("outcome", "source_exit"),
    [
        pytest.param("FAILED", pytest.ExitCode.TESTS_FAILED, id="failure"),
        pytest.param("ERROR", pytest.ExitCode.TESTS_FAILED, id="setup-error"),
        pytest.param("SKIPPED", pytest.ExitCode.OK, id="skip"),
        pytest.param("XFAILED", pytest.ExitCode.OK, id="expected-failure"),
        pytest.param("XPASSED", pytest.ExitCode.OK, id="unexpected-pass"),
    ],
)
def test_a_pass_in_another_run_cannot_erase_an_adverse_outcome(
    user_project: UserProject,
    monkeypatch: pytest.MonkeyPatch,
    inputs: tuple[str, str],
    outcome: str,
    source_exit: pytest.ExitCode,
) -> None:
    project = user_project(["REQ-001"], outcomes)
    simulate_outcome(monkeypatch, outcome)
    record_run(project, "adverse", expected_exit=source_exit)
    simulate_outcome(monkeypatch, "PASSED")
    passed = record_run(project, "passed")
    assert passed["requirements"]["REQ-001"]["status"] == "PASSED"

    result = combine(project, *inputs, "--output=combined.json", "--xspec-strict")

    assert result.ret == 1
    report = read_combined(project.path / "combined.json")
    assert report["requirements"] == {"REQ-001": {"status": outcome}}
    assert report["summary"]["verified"] is False


@pytest.mark.parametrize("inputs", [("first.json", "second.json"), ("second.json", "first.json")])
def test_a_successful_distinct_test_does_not_hide_a_failure(
    user_project: UserProject, monkeypatch: pytest.MonkeyPatch, inputs: tuple[str, str]
) -> None:
    project = user_project(["REQ-001"], outcomes)
    simulate_outcome(monkeypatch, "FAILED")
    record_run(project, "first", "-k", "first", expected_exit=pytest.ExitCode.TESTS_FAILED)
    record_run(project, "second", "-k", "second")

    result = combine(project, *inputs, "--output=combined.json", "--xspec-strict")

    assert result.ret == 1
    report = read_combined(project.path / "combined.json")
    assert report["requirements"] == {"REQ-001": {"status": "FAILED"}}
    assert report["summary"]["verified"] is False


@pytest.mark.parametrize(
    ("options", "exit_code"),
    [pytest.param((), 0, id="report-only"), pytest.param(("--xspec-strict",), 1, id="strict")],
)
def test_missing_and_deselected_requirements_remain_unverified(
    user_project: UserProject, options: tuple[str, ...], exit_code: int
) -> None:
    project = user_project(["REQ-001", "REQ-002"], complementary)
    record_run(project, "run-a", "-k", "first")
    record_run(project, "run-b", "-k", "first")

    result = combine(project, "run-a.json", "run-b.json", "--output=combined.json", *options)

    assert result.ret == exit_code
    report = read_combined(project.path / "combined.json")
    assert report["requirements"] == {
        "REQ-001": {"status": "DESELECTED"},
        "REQ-002": {"status": "MISSING"},
    }
    assert report["summary"]["verified"] is False


def test_scope_stays_with_its_run(user_project: UserProject) -> None:
    project = user_project(["REQ-001"], complementary)
    record_run(
        project,
        "selected",
        "test_behavior.py",
        "--xspec-select=REQ-001",
        "-k",
        "first",
        "-m",
        "xspec",
    )
    record_run(project, "unfiltered")

    result = combine(project, "selected.json", "unfiltered.json", "--output=combined.json")

    assert result.ret == 0
    report = read_combined(project.path / "combined.json")
    assert [run["run_id"] for run in report["runs"]] == ["selected", "unfiltered"]
    assert report["runs"][0].get("scope") == {
        "selected_requirements": ["REQ-001"],
        "collection_paths": ["test_behavior.py"],
        "keyword_expression": "first",
        "marker_expression": "xspec",
        "collect_only": False,
    }
    assert "scope" not in report["runs"][1]
    assert "scope" not in report


def test_collection_error_counts_are_summed_and_prevent_verification(
    user_project: UserProject,
) -> None:
    project = user_project(["REQ-001"], collection_error)
    record_run(
        project,
        "run-a",
        "--continue-on-collection-errors",
        expected_exit=pytest.ExitCode.TESTS_FAILED,
    )
    record_run(
        project,
        "run-b",
        "--continue-on-collection-errors",
        expected_exit=pytest.ExitCode.TESTS_FAILED,
    )

    result = combine(
        project, "run-a.json", "run-b.json", "--output=combined.json", "--xspec-strict"
    )

    assert result.ret == 1
    report = read_combined(project.path / "combined.json")
    assert report["summary"]["collection_errors"] == 2
    assert report["summary"]["coverage"] == 100.0
    assert report["summary"]["verified"] is False


@pytest.mark.parametrize(
    "inputs", [("interrupted.json", "completed.json"), ("completed.json", "interrupted.json")]
)
def test_one_interrupted_run_prevents_verification_even_when_all_requirements_pass(
    user_project: UserProject, inputs: tuple[str, str]
) -> None:
    project = user_project(["REQ-001"], interrupted)
    record_run(project, "interrupted", expected_exit=pytest.ExitCode.INTERRUPTED)
    completed = record_run(project, "completed", "-k", "first")
    assert completed["summary"]["verified"] is True

    result = combine(project, *inputs, "--output=combined.json", "--xspec-strict")

    assert result.ret == 1
    report = read_combined(project.path / "combined.json")
    assert report["summary"].get("interrupted") is True
    assert report["summary"]["coverage"] == 100.0
    assert report["summary"]["verified"] is False


def test_inventory_order_may_differ_and_first_input_controls_output_order(
    user_project: UserProject,
) -> None:
    project = user_project(["REQ-002", "REQ-001"], complementary)
    record_run(project, "run-a")
    user_project(["REQ-001", "REQ-002"], complementary)
    record_run(project, "run-b")

    result = combine(project, "run-a.json", "run-b.json", "--output=combined.json")

    assert result.ret == 0
    report = read_combined(project.path / "combined.json")
    assert list(report["requirements"]) == ["REQ-002", "REQ-001"]


def test_combined_coverage_counts_requirements_not_observations(user_project: UserProject) -> None:
    project = user_project(["REQ-001", "REQ-002"], complementary)
    record_run(project, "run-a", "-k", "first")
    record_run(project, "run-b", "-k", "second")

    result = combine(project, "run-a.json", "run-b.json", "--output=combined.json")

    assert result.ret == 0
    report = read_combined(project.path / "combined.json")
    assert report["summary"]["requirements"] == 2
    assert report["summary"]["passed"] == 1
    assert report["summary"]["unverified"] == 1
    assert report["summary"]["coverage"] == 50.0


def test_a_single_empty_inventory_can_be_combined(user_project: UserProject) -> None:
    project = user_project([], empty_inventory)
    record_run(project, "empty")

    result = combine(project, "empty.json", "--output=combined.json", "--xspec-strict")

    assert result.ret == 0
    report = read_combined(project.path / "combined.json")
    assert report["requirements"] == {}
    assert report["summary"] == {
        "requirements": 0,
        "passed": 0,
        "unverified": 0,
        "coverage": 0.0,
        "verified": True,
        "collection_errors": 0,
    }


def test_shared_parameterized_tests_keep_their_complete_identities_in_each_run(
    user_project: UserProject,
) -> None:
    project = user_project(["REQ-001", "REQ-002"], selected)
    first = record_run(project, "run-a", "-k", "first or other")
    second = record_run(project, "run-b", "-k", "second")

    result = combine(
        project, "run-a.json", "run-b.json", "--output=combined.json", "--xspec-strict"
    )

    assert result.ret == 0
    report = read_combined(project.path / "combined.json")
    assert report["runs"] == [first, second]
    assert report["requirements"] == {
        "REQ-001": {"status": "PASSED"},
        "REQ-002": {"status": "PASSED"},
    }
    assert report["summary"]["verified"] is True


def test_discovery_observations_remain_skipped_when_another_run_passes(
    user_project: UserProject,
) -> None:
    project = user_project(["REQ-001"], complementary)
    record_run(project, "discovery", "--collect-only", "--xspec-select=REQ-001")
    executed = record_run(project, "executed")
    assert executed["summary"]["verified"] is True

    result = combine(
        project, "discovery.json", "executed.json", "--output=combined.json", "--xspec-strict"
    )

    assert result.ret == 1
    report = read_combined(project.path / "combined.json")
    assert report["requirements"] == {"REQ-001": {"status": "SKIPPED"}}
    assert report["summary"]["verified"] is False


def test_combination_does_not_execute_available_tests(
    user_project: UserProject,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = user_project(["REQ-001"], complementary)
    monkeypatch.setenv("PYTEST_ADDOPTS", "-s")
    execution = project.runpytest_subprocess(
        "-s", "--xspec-run-id=source", "--xspec-json=source.json"
    )
    assert execution.ret == pytest.ExitCode.OK
    execution.stdout.fnmatch_lines(["*EXECUTED: first behavior*", "*EXECUTED: second behavior*"])

    result = combine(project, "source.json", "--output=combined.json", "--xspec-strict")

    assert result.ret == 0
    assert "EXECUTED:" not in result.stdout.str()


def test_combination_succeeds_without_the_original_project(user_project: UserProject) -> None:
    project = user_project(["REQ-001"], complementary)
    record_run(project, "source")
    (project.path / "test_behavior.py").unlink()
    (project.path / "pyproject.toml").unlink()

    result = combine(project, "source.json", "--output=combined.json", "--xspec-strict")

    assert result.ret == 0
    report = read_combined(project.path / "combined.json")
    assert report["requirements"] == {"REQ-001": {"status": "PASSED"}}
