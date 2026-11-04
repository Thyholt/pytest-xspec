"""One invocation produces one complete report across real xdist workers."""

from types import ModuleType

import pytest

from tests.acceptance.expectations import expected
from tests.acceptance.scenarios.cli import collection_error
from tests.acceptance.scenarios.cli.unmarked_outcomes import failed
from tests.acceptance.scenarios.parallel import (
    crash,
    each_outcomes,
    grouped,
    internal_error,
    interrupted_teardown,
    parameterized,
    setup_crash,
    unmarked_crash,
)
from tests.acceptance.scenarios.requirements import invalid_deselected_marker
from tests.acceptance.scenarios.statuses import (
    early_stop,
    setup_error_over_failure,
    teardown_error_after_pass,
)
from tests.acceptance.scenarios.statuses.reported_outcome import (
    expected_failure,
    failed_test,
    setup_error,
    skipped_test,
    unexpected_pass,
)
from tests.acceptance.types import ReadReport, UserProject


@pytest.mark.parametrize(
    "scheduler", ["no", "load", "loadscope", "loadfile", "loadgroup", "worksteal", "each"]
)
def test_parallel_results_match_serial_results(
    user_project: UserProject, read_report: ReadReport, scheduler: str
) -> None:
    project = user_project(["REQ-001", "REQ-002"], parameterized)

    serial = project.runpytest_subprocess("-n", "0", "--xspec-strict", "--xspec-json=report.json")
    serial_report = read_report(project)
    (project.path / "report.json").unlink()
    parallel = project.runpytest_subprocess(
        "-n",
        "0" if scheduler == "no" else "2",
        f"--dist={scheduler}",
        "--xspec-strict",
        "--xspec-json=report.json",
    )

    assert serial.ret == parallel.ret == pytest.ExitCode.OK
    parallel.assert_outcomes(passed=4 if scheduler == "each" else 2)
    report = read_report(project)
    assert report == serial_report
    for identifier in ("REQ-001", "REQ-002"):
        assert expected(report["requirements"][identifier]).to_have(
            status="PASSED",
            tests=[
                ("test_behavior.py::test_behavior[1]", "PASSED"),
                ("test_behavior.py::test_behavior[2]", "PASSED"),
            ],
        )

    assert report["summary"]["verified"] is True
    assert parallel.stdout.str().count(" xspec ") == 1


@pytest.mark.parametrize("scheduler", ["load", "worksteal"])
@pytest.mark.parametrize(
    "case",
    [
        pytest.param((failed_test, "FAILED"), id="failed-test"),
        pytest.param((setup_error, "ERROR"), id="setup-error"),
        pytest.param((teardown_error_after_pass, "ERROR"), id="teardown-error"),
        pytest.param((skipped_test, "SKIPPED"), id="skipped-test"),
        pytest.param((expected_failure, "XFAILED"), id="expected-failure"),
        pytest.param((unexpected_pass, "XPASSED"), id="unexpected-pass"),
    ],
)
def test_parallel_unsuccessful_tests_remain_unverified(
    user_project: UserProject,
    read_report: ReadReport,
    scheduler: str,
    case: tuple[ModuleType, str],
) -> None:
    scenario, status = case
    project = user_project(["REQ-001"], scenario)

    result = project.runpytest_subprocess(
        "-n", "2", f"--dist={scheduler}", "--xspec-strict", "--xspec-json=report.json"
    )

    assert result.ret == pytest.ExitCode.TESTS_FAILED
    report = read_report(project)
    assert expected(report["requirements"]["REQ-001"]).to_have(
        status=status, tests=[("test_behavior.py::test_behavior", status)]
    )
    assert report["summary"]["verified"] is False


@pytest.mark.parametrize("scheduler", ["load", "worksteal"])
@pytest.mark.parametrize("expression", ["[1]", "absent"])
def test_parallel_filtering_preserves_deselected_identities(
    user_project: UserProject, read_report: ReadReport, scheduler: str, expression: str
) -> None:
    project = user_project(["REQ-001", "REQ-002"], parameterized)

    result = project.runpytest_subprocess(
        "-n",
        "2",
        f"--dist={scheduler}",
        "-k",
        expression,
        "--xspec-select=REQ-001",
        "--xspec-strict",
        "--xspec-json=report.json",
    )

    assert result.ret == pytest.ExitCode.TESTS_FAILED
    report = read_report(project)
    for identifier in ("REQ-001", "REQ-002"):
        assert expected(report["requirements"][identifier]).to_have(
            status="DESELECTED",
            tests=[
                (
                    "test_behavior.py::test_behavior[1]",
                    "PASSED" if expression == "[1]" else "DESELECTED",
                ),
                ("test_behavior.py::test_behavior[2]", "DESELECTED"),
            ],
        )

    assert report["summary"]["verified"] is False


@pytest.mark.parametrize("scheduler", ["load", "worksteal"])
def test_parallel_early_stop_preserves_unexecuted_identities(
    user_project: UserProject, read_report: ReadReport, scheduler: str
) -> None:
    project = user_project(["REQ-001", "REQ-002"], early_stop)

    result = project.runpytest_subprocess(
        "-n",
        "1",
        f"--dist={scheduler}",
        "--maxfail=1",
        "--xspec-strict",
        "--xspec-json=report.json",
    )

    assert result.ret != pytest.ExitCode.OK
    report = read_report(project)
    assert expected(report["requirements"]["REQ-001"]).to_have(
        status="FAILED", tests=[("test_behavior.py::test_first", "FAILED")]
    )
    assert expected(report["requirements"]["REQ-002"]).to_have(
        status="SKIPPED", tests=[("test_behavior.py::test_second", "SKIPPED")]
    )
    assert report["summary"]["verified"] is False


@pytest.mark.parametrize("scheduler", ["load", "worksteal"])
def test_parallel_collection_errors_prevent_verification(
    user_project: UserProject, read_report: ReadReport, scheduler: str
) -> None:
    project = user_project(["REQ-001"], collection_error)

    result = project.runpytest_subprocess(
        "-n",
        "2",
        f"--dist={scheduler}",
        "--continue-on-collection-errors",
        "--xspec-strict",
        "--xspec-json=report.json",
    )

    assert result.ret == pytest.ExitCode.TESTS_FAILED
    report = read_report(project)
    assert expected(report["requirements"]["REQ-001"]).to_have(
        status="PASSED", tests=[("test_behavior.py::test_behavior", "PASSED")]
    )
    assert report["summary"]["collection_errors"] == 1
    assert report["summary"]["verified"] is False


@pytest.mark.parametrize("scheduler", ["load", "worksteal"])
def test_crashed_workers_cannot_lose_reported_requirement_results(
    user_project: UserProject, read_report: ReadReport, scheduler: str
) -> None:
    project = user_project(["REQ-001"], crash)

    result = project.runpytest_subprocess(
        "-n",
        "2",
        f"--dist={scheduler}",
        "--max-worker-restart=0",
        "--xspec-strict",
        "--xspec-json=report.json",
    )

    assert result.ret == pytest.ExitCode.TESTS_FAILED
    report = read_report(project)
    assert expected(report["requirements"]["REQ-001"]).to_have(
        status="ERROR",
        tests=[
            ("test_behavior.py::test_behavior[1]", "ERROR"),
            ("test_behavior.py::test_behavior[2]", "ERROR"),
        ],
    )
    assert report["summary"]["verified"] is False


@pytest.mark.parametrize("scheduler", ["load", "worksteal"])
def test_an_unmarked_worker_crash_invalidates_otherwise_verified_requirements(
    user_project: UserProject, read_report: ReadReport, scheduler: str
) -> None:
    project = user_project(["REQ-001"], unmarked_crash)

    result = project.runpytest_subprocess(
        "-n",
        "1",
        f"--dist={scheduler}",
        "--max-worker-restart=0",
        "--xspec-strict",
        "--xspec-json=report.json",
    )

    assert result.ret == pytest.ExitCode.TESTS_FAILED
    report = read_report(project)
    assert expected(report["requirements"]["REQ-001"]).to_have(
        status="PASSED", tests=[("test_behavior.py::test_behavior", "PASSED")]
    )
    assert report["summary"] == {
        "requirements": 1,
        "passed": 1,
        "unverified": 0,
        "coverage": 100.0,
        "verified": False,
        "collection_errors": 0,
        "interrupted": True,
    }
    assert "Execution interrupted" in result.stdout.str()


@pytest.mark.parametrize(("workers", "status"), [("0", "SKIPPED"), ("2", "ERROR")])
def test_a_passing_call_with_interrupted_teardown_does_not_verify_a_requirement(
    user_project: UserProject, read_report: ReadReport, workers: str, status: str
) -> None:
    project = user_project(["REQ-001"], interrupted_teardown)

    result = project.runpytest_subprocess(
        "-n",
        workers,
        "--xspec-strict",
        "--xspec-json=report.json",
    )

    assert result.ret == pytest.ExitCode.INTERRUPTED
    report = read_report(project)
    assert expected(report["requirements"]["REQ-001"]).to_have(
        status=status, tests=[("test_behavior.py::test_behavior", status)]
    )
    assert report["summary"]["verified"] is False


def test_serial_reporting_works_without_loading_xdist(
    user_project: UserProject, read_report: ReadReport
) -> None:
    project = user_project(["REQ-001", "REQ-002"], parameterized)

    result = project.runpytest_subprocess(
        "-p",
        "no:xdist",
        "-p",
        "no:xdist.looponfail",
        "--xspec-strict",
        "--xspec-json=report.json",
    )

    assert result.ret == pytest.ExitCode.OK
    report = read_report(project)
    for identifier in ("REQ-001", "REQ-002"):
        assert expected(report["requirements"][identifier]).to_have(
            status="PASSED",
            tests=[
                ("test_behavior.py::test_behavior[1]", "PASSED"),
                ("test_behavior.py::test_behavior[2]", "PASSED"),
            ],
        )


@pytest.mark.parametrize("scheduler", ["load", "worksteal"])
@pytest.mark.parametrize(
    "test_order", [("test_setup_error", "test_failure"), ("test_failure", "test_setup_error")]
)
def test_parallel_outcome_precedence_preserves_collection_order(
    user_project: UserProject,
    read_report: ReadReport,
    scheduler: str,
    test_order: tuple[str, str],
) -> None:
    project = user_project(["REQ-001"], setup_error_over_failure)
    outcomes = {"test_setup_error": "ERROR", "test_failure": "FAILED"}
    nodeids = [f"test_behavior.py::{name}" for name in test_order]

    result = project.runpytest_subprocess(
        *nodeids,
        "-n",
        "2",
        f"--dist={scheduler}",
        "--xspec-json=report.json",
    )

    assert result.ret == pytest.ExitCode.TESTS_FAILED
    report = read_report(project)
    assert expected(report["requirements"]["REQ-001"]).to_have(
        status="ERROR",
        tests=[(f"test_behavior.py::{name}", outcomes[name]) for name in test_order],
    )


@pytest.mark.parametrize("scheduler", ["load", "worksteal"])
def test_all_workers_crashing_before_the_first_report_preserves_collection(
    user_project: UserProject, read_report: ReadReport, scheduler: str
) -> None:
    project = user_project(["REQ-001"], setup_crash)

    result = project.runpytest_subprocess(
        "-n",
        "2",
        f"--dist={scheduler}",
        "--max-worker-restart=0",
        "--xspec-strict",
        "--xspec-json=report.json",
    )

    assert result.ret == pytest.ExitCode.TESTS_FAILED
    crashed_nodeids = [
        path.read_text(encoding="utf-8") for path in project.path.glob("crashed-*.txt")
    ]
    assert len(crashed_nodeids) == 2
    collected_nodeids = [f"test_behavior.py::test_behavior[{value}]" for value in range(4)]
    report = read_report(project)
    assert expected(report["requirements"]["REQ-001"]).to_have(
        status="ERROR",
        tests=[
            (nodeid, "ERROR" if nodeid in crashed_nodeids else "SKIPPED")
            for nodeid in collected_nodeids
        ],
    )
    assert report["summary"]["verified"] is False


@pytest.mark.parametrize(
    "selection", [(), ("--xspec-select=REQ-001",)], ids=["all-requirements", "selected-requirement"]
)
def test_loadgroup_preserves_requirement_selection_and_parameterized_identities(
    user_project: UserProject, read_report: ReadReport, selection: tuple[str, ...]
) -> None:
    project = user_project(["REQ-001", "REQ-002"], grouped)

    result = project.runpytest_subprocess(
        "-n",
        "2",
        "--dist=loadgroup",
        "-k",
        "not excluded",
        "--xspec-strict",
        "--xspec-json=report.json",
        *selection,
    )

    assert result.ret == pytest.ExitCode.TESTS_FAILED
    result.assert_outcomes(passed=2)
    report = read_report(project)
    assert expected(report["requirements"]["REQ-001"]).to_have(
        status="PASSED",
        tests=[
            ("test_behavior.py::test_behavior[first@case]", "PASSED"),
            ("test_behavior.py::test_behavior[second]", "PASSED"),
        ],
    )
    assert expected(report["requirements"]["REQ-002"]).to_have(
        status="DESELECTED",
        tests=[("test_behavior.py::test_excluded", "DESELECTED")],
    )


def test_each_aggregates_different_worker_outcomes_without_duplicate_records(
    user_project: UserProject, read_report: ReadReport
) -> None:
    project = user_project(["REQ-001"], each_outcomes)

    result = project.runpytest_subprocess(
        "-n",
        "2",
        "--dist=each",
        "--xspec-strict",
        "--xspec-json=report.json",
    )

    assert result.ret == pytest.ExitCode.TESTS_FAILED
    result.assert_outcomes(passed=1, skipped=1)
    report = read_report(project)
    assert expected(report["requirements"]["REQ-001"]).to_have(
        status="SKIPPED",
        tests=[("test_behavior.py::test_behavior", "SKIPPED")],
    )
    assert report["summary"]["verified"] is False


@pytest.mark.parametrize("workers", ["0", "2"], ids=["serial", "parallel"])
def test_an_internal_error_invalidates_otherwise_verified_requirements(
    user_project: UserProject, read_report: ReadReport, workers: str
) -> None:
    project = user_project(["REQ-001"], internal_error)

    result = project.runpytest_subprocess(
        "-n",
        workers,
        "--xspec-strict",
        "--xspec-json=report.json",
    )

    assert result.ret == pytest.ExitCode.INTERNAL_ERROR
    assert "Intentional plugin error after execution" in result.stdout.str()
    report = read_report(project)
    assert expected(report["requirements"]["REQ-001"]).to_have(
        status="PASSED",
        tests=[("test_behavior.py::test_behavior", "PASSED")],
    )
    assert report["summary"]["verified"] is False


@pytest.mark.parametrize("scheduler", ["load", "worksteal"])
def test_an_ordinary_unmarked_failure_preserves_a_successful_verdict(
    user_project: UserProject, read_report: ReadReport, scheduler: str
) -> None:
    project = user_project(["REQ-001"], failed)

    result = project.runpytest_subprocess(
        "-n",
        "2",
        f"--dist={scheduler}",
        "--xspec-strict",
        "--xspec-json=report.json",
    )

    assert result.ret == pytest.ExitCode.TESTS_FAILED
    report = read_report(project)
    assert expected(report["requirements"]["REQ-001"]).to_have(
        status="PASSED", tests=[("test_behavior.py::test_marked", "PASSED")]
    )
    assert report["summary"]["verified"] is True


def test_a_worker_crash_invalidates_an_empty_inventory(
    user_project: UserProject, read_report: ReadReport
) -> None:
    project = user_project([], unmarked_crash)

    result = project.runpytest_subprocess(
        "test_behavior.py::test_crash",
        "-n",
        "2",
        "--max-worker-restart=0",
        "--xspec-strict",
        "--xspec-json=report.json",
    )

    assert result.ret == pytest.ExitCode.TESTS_FAILED
    report = read_report(project)
    assert report["requirements"] == {}
    assert report["summary"]["verified"] is False


def test_worker_marker_validation_errors_cannot_verify_an_empty_inventory(
    user_project: UserProject, read_report: ReadReport
) -> None:
    project = user_project([], invalid_deselected_marker)

    result = project.runpytest_subprocess(
        "-n",
        "2",
        "--xspec-strict",
        "--xspec-json=report.json",
    )

    assert result.ret == pytest.ExitCode.USAGE_ERROR
    assert "unknown xspec requirement ID 'UNKNOWN'" in result.stderr.str()
    report = read_report(project)
    assert report["requirements"] == {}
    assert report["summary"]["verified"] is False
