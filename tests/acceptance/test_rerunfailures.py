"""Retries preserve verification invariants across attempts and workers."""

from types import ModuleType

import pytest

from tests.acceptance.expectations import expected
from tests.acceptance.observations import ObservedRun
from tests.acceptance.scenarios.reruns import (
    final_outcome,
    interrupted,
    recovered,
    shared_requirement,
    worker_outcomes,
)
from tests.acceptance.scenarios.statuses import teardown_error_after_pass
from tests.acceptance.scenarios.statuses.reported_outcome import failed_test, setup_error
from tests.acceptance.types import ReadReport, UserProject


@pytest.mark.parametrize("phase", ["call", "setup", "teardown"])
def test_a_complete_successful_retry_verifies_the_requirement(
    user_project: UserProject, read_report: ReadReport, phase: str
) -> None:
    project = user_project(["REQ-001"], recovered)
    nodeid = f"test_behavior.py::test_{phase}"

    result = project.runpytest_subprocess(
        nodeid, "--reruns=1", "--xspec-strict", "--xspec-json=report.json"
    )

    observed = ObservedRun(result)
    assert result.ret == pytest.ExitCode.OK
    assert observed.reruns == 1
    report = read_report(project)
    assert expected(report["requirements"]["REQ-001"]).to_have(
        status="PASSED", tests=[(nodeid, "PASSED")]
    )
    assert report["summary"]["verified"] is True


@pytest.mark.parametrize(
    ("scenario", "status"),
    [
        pytest.param(failed_test, "FAILED", id="call"),
        pytest.param(setup_error, "ERROR", id="setup"),
        pytest.param(teardown_error_after_pass, "ERROR", id="teardown-after-passing-call"),
    ],
)
def test_exhausted_retries_preserve_the_final_failure(
    user_project: UserProject, read_report: ReadReport, scenario: ModuleType, status: str
) -> None:
    project = user_project(["REQ-001"], scenario)

    result = project.runpytest_subprocess(
        "--reruns=1", "--xspec-strict", "--xspec-json=report.json"
    )

    observed = ObservedRun(result)
    assert result.ret == pytest.ExitCode.TESTS_FAILED
    assert observed.reruns == 1
    report = read_report(project)
    assert expected(report["requirements"]["REQ-001"]).to_have(
        status=status, tests=[("test_behavior.py::test_behavior", status)]
    )
    assert report["summary"]["verified"] is False


@pytest.mark.parametrize(
    ("status", "mode"),
    [
        pytest.param("SKIPPED", ("--xspec-report", pytest.ExitCode.OK), id="skipped-report"),
        pytest.param(
            "SKIPPED", ("--xspec-strict", pytest.ExitCode.TESTS_FAILED), id="skipped-strict"
        ),
        pytest.param("XFAILED", ("--xspec-report", pytest.ExitCode.OK), id="xfailed"),
        pytest.param("XPASSED", ("--xspec-report", pytest.ExitCode.OK), id="xpassed"),
    ],
)
def test_an_unsuccessful_final_attempt_cannot_verify_a_requirement(
    user_project: UserProject,
    read_report: ReadReport,
    status: str,
    mode: tuple[str, pytest.ExitCode],
) -> None:
    option, exit_code = mode
    project = user_project(["REQ-001"], final_outcome)
    nodeid = f"test_behavior.py::test_behavior[{status}]"

    result = project.runpytest_subprocess(nodeid, "--reruns=1", option, "--xspec-json=report.json")

    observed = ObservedRun(result)
    assert result.ret == exit_code
    assert observed.reruns == 1
    report = read_report(project)
    assert expected(report["requirements"]["REQ-001"]).to_have(
        status=status, tests=[(nodeid, status)]
    )
    assert report["summary"]["verified"] is False


@pytest.mark.parametrize(
    ("interruption", "expected_phases"),
    [
        pytest.param("call", ("teardown",), id="during-call"),
        pytest.param("teardown", ("call",), id="after-passing-call"),
    ],
)
def test_an_interrupted_retry_cannot_verify_a_requirement(
    user_project: UserProject,
    read_report: ReadReport,
    interruption: str,
    expected_phases: tuple[str, ...],
) -> None:
    project = user_project(["REQ-001"], interrupted)
    nodeid = f"test_behavior.py::test_behavior[{interruption}]"

    result = project.runpytest_subprocess(
        nodeid, "--reruns=1", "-s", "--xspec-strict", "--xspec-json=report.json"
    )

    assert result.ret == pytest.ExitCode.INTERRUPTED
    assert shows_in_order(
        result, "attempt 1 started", "attempt 1 teardown completed", "attempt 2 started"
    )
    assert completed_phases(result, attempt=2) == expected_phases
    report = read_report(project)
    assert expected(report["requirements"]["REQ-001"]).to_have(
        status="SKIPPED", tests=[(nodeid, "SKIPPED")]
    )
    assert report["summary"]["verified"] is False
    assert report["summary"]["coverage"] == 0.0
    assert report["summary"].get("interrupted", False) is True


def test_a_retry_that_completes_both_phases_verifies_a_requirement(
    user_project: UserProject, read_report: ReadReport
) -> None:
    project = user_project(["REQ-001"], interrupted)
    nodeid = "test_behavior.py::test_behavior[none]"

    result = project.runpytest_subprocess(
        nodeid, "--reruns=1", "-s", "--xspec-strict", "--xspec-json=report.json"
    )

    assert result.ret == pytest.ExitCode.OK
    assert shows_in_order(
        result, "attempt 1 started", "attempt 1 teardown completed", "attempt 2 started"
    )
    assert completed_phases(result, attempt=2) == ("call", "teardown")
    report = read_report(project)
    assert expected(report["requirements"]["REQ-001"]).to_have(
        status="PASSED", tests=[(nodeid, "PASSED")]
    )
    assert report["summary"]["verified"] is True
    assert report["summary"]["coverage"] == 100.0
    assert report["summary"].get("interrupted", False) is False


@pytest.mark.parametrize(
    "test_order", [("test_recovered", "test_failed"), ("test_failed", "test_recovered")]
)
def test_a_successful_retry_cannot_hide_another_associated_test_failure(
    user_project: UserProject, read_report: ReadReport, test_order: tuple[str, str]
) -> None:
    project = user_project(["REQ-001"], shared_requirement)
    nodeids = [f"test_behavior.py::{name}" for name in test_order]
    outcomes = {"test_recovered": "PASSED", "test_failed": "FAILED"}

    result = project.runpytest_subprocess(
        *nodeids, "--reruns=1", "--xspec-strict", "--xspec-json=report.json"
    )

    observed = ObservedRun(result)
    assert result.ret == pytest.ExitCode.TESTS_FAILED
    assert observed.reruns == 2
    report = read_report(project)
    assert expected(report["requirements"]["REQ-001"]).to_have(
        status="FAILED",
        tests=[(f"test_behavior.py::{name}", outcomes[name]) for name in test_order],
    )
    assert report["summary"]["verified"] is False


@pytest.mark.parametrize(
    ("execution", "reruns"),
    [pytest.param(("load", "2"), 3, id="load"), pytest.param(("each", "2"), 6, id="each")],
)
def test_distributed_retries_preserve_identities_and_report_once(
    user_project: UserProject,
    read_report: ReadReport,
    execution: tuple[str, str],
    reruns: int,
) -> None:
    scheduler, workers = execution
    project = user_project(["REQ-001"], recovered)

    result = project.runpytest_subprocess(
        "-n",
        workers,
        f"--dist={scheduler}",
        "--reruns=1",
        "--xspec-strict",
        "--xspec-json=report.json",
    )

    observed = ObservedRun(result)
    assert result.ret == pytest.ExitCode.OK
    assert observed.reruns == reruns
    report = read_report(project)
    assert expected(report["requirements"]["REQ-001"]).to_have(
        status="PASSED",
        tests=[
            ("test_behavior.py::test_call", "PASSED"),
            ("test_behavior.py::test_setup", "PASSED"),
            ("test_behavior.py::test_teardown", "PASSED"),
        ],
    )
    assert report["summary"]["verified"] is True
    assert observed.requirement_reports == 1


@pytest.mark.parametrize(
    ("case", "exit_code"),
    [
        pytest.param(("failed", "FAILED", 1), pytest.ExitCode.TESTS_FAILED, id="exhausted"),
        pytest.param(("skipped", "SKIPPED", 1), pytest.ExitCode.TESTS_FAILED, id="skipped"),
        pytest.param(("interrupted", "ERROR", 1), pytest.ExitCode.INTERRUPTED, id="interrupted"),
        pytest.param(("teardown_error", "ERROR", 2), pytest.ExitCode.TESTS_FAILED, id="teardown"),
    ],
)
def test_a_successful_worker_retry_cannot_hide_another_workers_outcome(
    user_project: UserProject,
    read_report: ReadReport,
    case: tuple[str, str, int],
    exit_code: pytest.ExitCode,
) -> None:
    outcome, status, passed = case
    project = user_project(["REQ-001"], worker_outcomes)
    nodeid = f"test_behavior.py::test_behavior[{outcome}]"

    result = project.runpytest_subprocess(
        nodeid,
        "-n",
        "2",
        "--dist=each",
        "--reruns=1",
        "--max-worker-restart=0",
        "--xspec-strict",
        "--xspec-json=report.json",
    )

    observed = ObservedRun(result)
    assert result.ret == exit_code
    assert observed.reruns == 2
    assert observed.passed == passed
    report = read_report(project)
    assert expected(report["requirements"]["REQ-001"]).to_have(
        status=status, tests=[(nodeid, status)]
    )
    assert report["summary"]["verified"] is False


def shows_in_order(result: pytest.RunResult, *events: str) -> bool:
    output = "\n".join(result.outlines)
    position = 0
    for event in events:
        found = output.find(event, position)
        if found == -1:
            return False

        position = found + len(event)

    return True


def completed_phases(result: pytest.RunResult, *, attempt: int) -> tuple[str, ...]:
    output = "\n".join(result.outlines)
    return tuple(
        phase for phase in ("call", "teardown") if f"attempt {attempt} {phase} completed" in output
    )
