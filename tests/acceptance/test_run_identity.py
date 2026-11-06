"""A run ID labels a report without changing selection or execution outcomes."""

import pytest

from tests.acceptance.expectations import expected
from tests.acceptance.observations import ObservedRun
from tests.acceptance.scenarios.run_identity import retried, selected, unmarked
from tests.acceptance.types import ReadReport, UserProject


def execution_events(result: pytest.RunResult) -> list[str]:
    return [
        line.partition("RUN ID SCENARIO: ")[2]
        for line in result.stdout.lines
        if "RUN ID SCENARIO: " in line
    ]


def test_a_run_id_preserves_spaces_unicode_and_punctuation(
    user_project: UserProject, read_report: ReadReport
) -> None:
    project = user_project([], unmarked)

    result = project.runpytest_subprocess(
        "--xspec-run-id=  run / æøå : 1, second  ", "--xspec-json=report.json"
    )

    assert result.ret == pytest.ExitCode.OK
    report = read_report(project)
    assert report.get("run_id") == "  run / æøå : 1, second  "


def test_labeling_a_run_preserves_selection_scope_outcomes_and_strict_verdict(
    user_project: UserProject, read_report: ReadReport
) -> None:
    project = user_project(["REQ-001", "REQ-002"], selected)
    selection = (
        "test_behavior.py",
        "--xspec-select=REQ-002",
        "-k",
        "shared",
        "-m",
        "xspec",
        "--xspec-strict",
        "--xspec-json=report.json",
        "-s",
    )
    baseline = project.runpytest_subprocess(*selection)
    baseline_report = read_report(project)

    labeled = project.runpytest_subprocess(*selection, "--xspec-run-id=selected-run")

    assert baseline.ret == labeled.ret == pytest.ExitCode.TESTS_FAILED
    assert (
        execution_events(baseline)
        == execution_events(labeled)
        == ["fixture", "shared 1", "fixture", "shared 2"]
    )
    report = read_report(project)
    assert report == {**baseline_report, "run_id": "selected-run"}


@pytest.mark.parametrize("run_id", ["", " \t\n"], ids=["empty", "whitespace"])
def test_an_invalid_run_id_is_rejected_before_fixtures_or_tests_execute(
    user_project: UserProject, run_id: str
) -> None:
    project = user_project(["REQ-001", "REQ-002"], selected)

    result = project.runpytest_subprocess(f"--xspec-run-id={run_id}", "-s")

    assert result.ret == pytest.ExitCode.USAGE_ERROR
    diagnostic = (result.stdout.str() + result.stderr.str()).lower()
    assert "--xspec-run-id" in diagnostic or "run id" in diagnostic
    assert any(word in diagnostic for word in ("empty", "blank", "whitespace"))
    assert "unrecognized arguments" not in diagnostic
    assert execution_events(result) == []


def test_a_valid_run_id_without_reporting_still_executes_tests(user_project: UserProject) -> None:
    project = user_project(["REQ-001", "REQ-002"], selected)

    result = project.runpytest_subprocess("--xspec-run-id=run-a", "-s")

    assert result.ret == pytest.ExitCode.OK
    result.assert_outcomes(passed=3)
    assert execution_events(result) == [
        "fixture",
        "shared 1",
        "fixture",
        "shared 2",
        "fixture",
        "other",
    ]


def test_an_unlabeled_report_retains_its_existing_shape(
    user_project: UserProject, read_report: ReadReport
) -> None:
    project = user_project([], unmarked)

    result = project.runpytest_subprocess("--xspec-json=report.json")

    assert result.ret == pytest.ExitCode.OK
    report = read_report(project)
    assert report == {
        "requirements": {},
        "summary": {
            "requirements": 0,
            "passed": 0,
            "unverified": 0,
            "coverage": 0.0,
            "verified": True,
            "collection_errors": 0,
        },
    }


def test_an_empty_inventory_still_retains_its_run_id(
    user_project: UserProject, read_report: ReadReport
) -> None:
    project = user_project([], unmarked)

    result = project.runpytest_subprocess(
        "--xspec-run-id=empty-run", "--xspec-strict", "--xspec-json=report.json"
    )

    assert result.ret == pytest.ExitCode.OK
    report = read_report(project)
    assert report.get("run_id") == "empty-run"
    assert report["requirements"] == {}


def test_a_missing_requirement_still_retains_its_run_id(
    user_project: UserProject, read_report: ReadReport
) -> None:
    project = user_project(["REQ-001"], unmarked)

    result = project.runpytest_subprocess(
        "--xspec-run-id=missing-run", "--xspec-strict", "--xspec-json=report.json"
    )

    assert result.ret == pytest.ExitCode.TESTS_FAILED
    report = read_report(project)
    assert report.get("run_id") == "missing-run"
    assert expected(report["requirements"]["REQ-001"]).to_have(status="MISSING", tests=[])


@pytest.mark.parametrize(
    ("scheduler", "workers", "passed"),
    [pytest.param("load", "2", 3, id="load"), pytest.param("each", "2", 6, id="each")],
)
def test_distributed_execution_keeps_one_run_id_and_one_record_per_test(
    user_project: UserProject,
    read_report: ReadReport,
    scheduler: str,
    workers: str,
    passed: int,
) -> None:
    project = user_project(["REQ-001", "REQ-002"], selected)

    result = project.runpytest_subprocess(
        "-n",
        workers,
        f"--dist={scheduler}",
        "--xspec-run-id=parallel-run",
        "--xspec-strict",
        "--xspec-json=report.json",
    )

    assert result.ret == pytest.ExitCode.OK
    result.assert_outcomes(passed=passed)
    report = read_report(project)
    assert report.get("run_id") == "parallel-run"
    assert expected(report["requirements"]["REQ-001"]).to_have(
        status="PASSED",
        tests=[
            ("test_behavior.py::test_shared_behavior[first]", "PASSED"),
            ("test_behavior.py::test_shared_behavior[second]", "PASSED"),
            ("test_behavior.py::test_other_behavior", "PASSED"),
        ],
    )
    assert expected(report["requirements"]["REQ-002"]).to_have(
        status="PASSED",
        tests=[
            ("test_behavior.py::test_shared_behavior[first]", "PASSED"),
            ("test_behavior.py::test_shared_behavior[second]", "PASSED"),
        ],
    )


def test_retry_attempts_share_one_run_id_and_report_only_the_final_outcome(
    user_project: UserProject, read_report: ReadReport
) -> None:
    project = user_project(["REQ-001"], retried)

    result = project.runpytest_subprocess(
        "--reruns=1",
        "--xspec-run-id=retried-run",
        "--xspec-strict",
        "--xspec-json=report.json",
        "-s",
    )

    assert result.ret == pytest.ExitCode.OK
    result.assert_outcomes(passed=1)
    assert ObservedRun(result).reruns == 1
    assert execution_events(result) == ["attempt 1", "attempt 2"]
    report = read_report(project)
    assert report.get("run_id") == "retried-run"
    assert expected(report["requirements"]["REQ-001"]).to_have(
        status="PASSED", tests=[("test_behavior.py::test_behavior", "PASSED")]
    )
