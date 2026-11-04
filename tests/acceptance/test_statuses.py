"""Users can see why a requirement is or is not verified."""

from types import ModuleType

import pytest

from tests.acceptance.expectations import expected
from tests.acceptance.scenarios.statuses import (
    assertion_with_xpass_text,
    both_tests_pass,
    deselection_over_pass,
    early_stop,
    failure_over_xpass,
    fixture_skip,
    setup_error_over_failure,
    setup_xfail,
    skip_over_deselection,
    strict_xpass,
    teardown_error_after_failure,
    teardown_error_after_pass,
    teardown_xfail,
    xfail_over_skip,
    xpass_over_xfail,
)
from tests.acceptance.scenarios.statuses.partial_verification import (
    one_failed_test,
    one_skipped_test,
    one_unexecuted_test,
)
from tests.acceptance.scenarios.statuses.reported_outcome import (
    expected_failure,
    failed_test,
    passing_test,
    setup_error,
    skipped_test,
    unexpected_pass,
)
from tests.acceptance.types import ReadReport, UserProject


@pytest.mark.parametrize(
    ("scenario", "status"),
    [
        pytest.param(passing_test, "PASSED", id="passing-test"),
        pytest.param(failed_test, "FAILED", id="failed-test"),
        pytest.param(setup_error, "ERROR", id="setup-error"),
        pytest.param(skipped_test, "SKIPPED", id="skipped-test"),
        pytest.param(expected_failure, "XFAILED", id="expected-failure"),
        pytest.param(unexpected_pass, "XPASSED", id="unexpected-pass"),
    ],
)
def test_the_report_explains_the_outcome_of_a_marked_test(
    user_project: UserProject, read_report: ReadReport, scenario: ModuleType, status: str
) -> None:
    project = user_project(["REQ-001"], scenario)

    project.runpytest_subprocess("--xspec-json=report.json")

    report = read_report(project)
    assert expected(report["requirements"]["REQ-001"]).to_have(
        status=status, tests=[("test_behavior.py::test_behavior", status)]
    )
    assert report["summary"]["verified"] is (status == "PASSED")


@pytest.mark.parametrize(
    "scenario",
    [
        pytest.param(teardown_error_after_pass, id="after-passing-test"),
        pytest.param(teardown_error_after_failure, id="after-failing-test"),
    ],
)
def test_teardown_errors_take_precedence_over_the_test_body_outcome(
    user_project: UserProject, read_report: ReadReport, scenario: ModuleType
) -> None:
    project = user_project(["REQ-001"], scenario)

    result = project.runpytest_subprocess("--xspec-json=report.json")

    assert result.ret == pytest.ExitCode.TESTS_FAILED
    report = read_report(project)
    assert expected(report["requirements"]["REQ-001"]).to_have(
        status="ERROR", tests=[("test_behavior.py::test_behavior", "ERROR")]
    )


def test_a_fixture_skip_is_reported_as_skipped(
    user_project: UserProject, read_report: ReadReport
) -> None:
    project = user_project(["REQ-001"], fixture_skip)

    result = project.runpytest_subprocess("--xspec-json=report.json")

    assert result.ret == pytest.ExitCode.OK
    report = read_report(project)
    assert expected(report["requirements"]["REQ-001"]).to_have(
        status="SKIPPED",
        tests=[("test_behavior.py::test_behavior", "SKIPPED")],
    )


@pytest.mark.parametrize(
    "scenario",
    [pytest.param(setup_xfail, id="setup"), pytest.param(teardown_xfail, id="teardown")],
)
@pytest.mark.parametrize(
    ("options", "expected_exit"),
    [
        pytest.param((), pytest.ExitCode.OK, id="report"),
        pytest.param(("--xspec-strict",), pytest.ExitCode.TESTS_FAILED, id="strict"),
    ],
)
def test_fixture_expected_failures_are_xfailed_and_keep_requirements_unverified(
    user_project: UserProject,
    read_report: ReadReport,
    scenario: ModuleType,
    options: tuple[str, ...],
    expected_exit: pytest.ExitCode,
) -> None:
    project = user_project(["REQ-001"], scenario)

    result = project.runpytest_subprocess("--xspec-json=report.json", *options)

    assert result.ret == expected_exit
    report = read_report(project)
    assert expected(report["requirements"]["REQ-001"]).to_have(
        status="XFAILED", tests=[("test_behavior.py::test_behavior", "XFAILED")]
    )
    assert report["summary"]["verified"] is False


def test_strict_xfail_still_reports_an_unexpected_pass_as_xpassed(
    user_project: UserProject, read_report: ReadReport
) -> None:
    project = user_project(["REQ-001"], strict_xpass)

    result = project.runpytest_subprocess("--xspec-json=report.json")

    assert result.ret == pytest.ExitCode.TESTS_FAILED
    report = read_report(project)
    assert expected(report["requirements"]["REQ-001"]).to_have(
        status="XPASSED",
        tests=[("test_behavior.py::test_behavior", "XPASSED")],
    )


def test_an_assertion_mentioning_xpass_is_reported_as_failed(
    user_project: UserProject, read_report: ReadReport
) -> None:
    project = user_project(["REQ-001"], assertion_with_xpass_text)

    result = project.runpytest_subprocess("--xspec-strict", "--xspec-json=report.json")

    assert result.ret == pytest.ExitCode.TESTS_FAILED
    report = read_report(project)
    assert expected(report["requirements"]["REQ-001"]).to_have(
        status="FAILED", tests=[("test_behavior.py::test_behavior", "FAILED")]
    )
    assert report["summary"]["verified"] is False


@pytest.mark.parametrize(
    ("scenario", "test_outcomes", "status", "expected_exit"),
    [
        pytest.param(
            setup_error_over_failure,
            (
                ("test_behavior.py::test_setup_error", "ERROR"),
                ("test_behavior.py::test_failure", "FAILED"),
            ),
            "ERROR",
            pytest.ExitCode.TESTS_FAILED,
            id="setup-errors-over-failures",
        ),
        pytest.param(
            failure_over_xpass,
            (
                ("test_behavior.py::test_failure", "FAILED"),
                ("test_behavior.py::test_unexpected_pass", "XPASSED"),
            ),
            "FAILED",
            pytest.ExitCode.TESTS_FAILED,
            id="failures-over-unexpected-passes",
        ),
        pytest.param(
            xpass_over_xfail,
            (
                ("test_behavior.py::test_unexpected_pass", "XPASSED"),
                ("test_behavior.py::test_expected_failure", "XFAILED"),
            ),
            "XPASSED",
            pytest.ExitCode.OK,
            id="unexpected-passes-over-expected-failures",
        ),
        pytest.param(
            xfail_over_skip,
            (
                ("test_behavior.py::test_expected_failure", "XFAILED"),
                ("test_behavior.py::test_skipped", "SKIPPED"),
            ),
            "XFAILED",
            pytest.ExitCode.OK,
            id="expected-failures-over-skips",
        ),
    ],
)
@pytest.mark.parametrize("test_order", [(0, 1), (1, 0)], ids=["listed-order", "reversed-order"])
def test_executed_outcomes_follow_precedence_in_either_collection_order(
    user_project: UserProject,
    read_report: ReadReport,
    scenario: ModuleType,
    test_outcomes: tuple[tuple[str, str], tuple[str, str]],
    status: str,
    expected_exit: pytest.ExitCode,
    test_order: tuple[int, int],
) -> None:
    project = user_project(["REQ-001"], scenario)
    expected_tests = [test_outcomes[index] for index in test_order]
    node_ids = [node_id for node_id, _ in expected_tests]

    result = project.runpytest_subprocess("--xspec-json=report.json", *node_ids)

    assert result.ret == expected_exit
    report = read_report(project)
    assert expected(report["requirements"]["REQ-001"]).to_have(status=status, tests=expected_tests)


@pytest.mark.parametrize(
    ("scenario", "test_outcomes", "status"),
    [
        pytest.param(
            skip_over_deselection,
            (
                ("test_behavior.py::test_skipped", "SKIPPED"),
                ("test_behavior.py::test_excluded", "DESELECTED"),
            ),
            "SKIPPED",
            id="skips-over-deselection",
        ),
        pytest.param(
            deselection_over_pass,
            (
                ("test_behavior.py::test_excluded", "DESELECTED"),
                ("test_behavior.py::test_passed", "PASSED"),
            ),
            "DESELECTED",
            id="deselection-over-passes",
        ),
    ],
)
@pytest.mark.parametrize("test_order", [(0, 1), (1, 0)], ids=["listed-order", "reversed-order"])
def test_deselection_follow_precedence_in_either_collection_order(
    user_project: UserProject,
    read_report: ReadReport,
    scenario: ModuleType,
    test_outcomes: tuple[tuple[str, str], tuple[str, str]],
    status: str,
    test_order: tuple[int, int],
) -> None:
    project = user_project(["REQ-001"], scenario)
    expected_tests = [test_outcomes[index] for index in test_order]
    node_ids = [node_id for node_id, _ in expected_tests]

    result = project.runpytest_subprocess(
        "--xspec-json=report.json", *node_ids, "-k", "not excluded"
    )

    assert result.ret == pytest.ExitCode.OK
    report = read_report(project)
    assert expected(report["requirements"]["REQ-001"]).to_have(status=status, tests=expected_tests)


def test_a_requirement_is_verified_when_both_associated_tests_pass(
    user_project: UserProject, read_report: ReadReport
) -> None:
    project = user_project(["REQ-001"], both_tests_pass)

    result = project.runpytest_subprocess("--xspec-strict", "--xspec-json=report.json")

    assert result.ret == pytest.ExitCode.OK
    report = read_report(project)
    assert expected(report["requirements"]["REQ-001"]).to_have(
        status="PASSED",
        tests=[
            ("test_behavior.py::test_first", "PASSED"),
            ("test_behavior.py::test_second", "PASSED"),
        ],
    )
    assert report["summary"]["verified"] is True


@pytest.mark.parametrize(
    ("scenario", "status"),
    [
        pytest.param(one_failed_test, "FAILED", id="one-failed-test"),
        pytest.param(one_skipped_test, "SKIPPED", id="one-skipped-test"),
    ],
)
def test_one_passing_test_does_not_verify_a_requirement_with_an_unverified_test(
    user_project: UserProject, read_report: ReadReport, scenario: ModuleType, status: str
) -> None:
    project = user_project(["REQ-001"], scenario)

    result = project.runpytest_subprocess("--xspec-strict", "--xspec-json=report.json")

    assert result.ret != pytest.ExitCode.OK
    report = read_report(project)
    assert expected(report["requirements"]["REQ-001"]).to_have(
        status=status,
        tests=[
            ("test_behavior.py::test_first", "PASSED"),
            ("test_behavior.py::test_second", status),
        ],
    )
    assert report["summary"]["verified"] is False


def test_collect_only_keeps_associated_tests_unverified(
    user_project: UserProject, read_report: ReadReport
) -> None:
    project = user_project(["REQ-001"], both_tests_pass)

    result = project.runpytest_subprocess(
        "--collect-only", "--xspec-strict", "--xspec-json=report.json"
    )

    assert result.ret == pytest.ExitCode.TESTS_FAILED
    report = read_report(project)
    assert expected(report["requirements"]["REQ-001"]).to_have(
        status="SKIPPED",
        tests=[
            ("test_behavior.py::test_first", "SKIPPED"),
            ("test_behavior.py::test_second", "SKIPPED"),
        ],
    )
    assert report["summary"]["verified"] is False


def test_early_stop_reports_a_collected_but_unexecuted_test_as_skipped(
    user_project: UserProject, read_report: ReadReport
) -> None:
    project = user_project(["REQ-001", "REQ-002"], early_stop)

    result = project.runpytest_subprocess(
        "--maxfail=1", "--xspec-strict", "--xspec-json=report.json"
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


@pytest.mark.parametrize(
    "test_order", [("test_first", "test_second"), ("test_second", "test_first")]
)
def test_a_passing_test_does_not_verify_a_requirement_when_another_test_never_runs(
    user_project: UserProject, read_report: ReadReport, test_order: tuple[str, str]
) -> None:
    project = user_project(["REQ-001"], one_unexecuted_test)
    node_ids = [
        f"test_behavior.py::{test_order[0]}",
        "test_behavior.py::test_unmarked_failure",
        f"test_behavior.py::{test_order[1]}",
    ]

    result = project.runpytest_subprocess(
        "--maxfail=1", "--xspec-strict", "--xspec-json=report.json", *node_ids
    )

    assert result.ret == pytest.ExitCode.TESTS_FAILED
    report = read_report(project)
    assert expected(report["requirements"]["REQ-001"]).to_have(
        status="SKIPPED", tests=[(node_ids[0], "PASSED"), (node_ids[2], "SKIPPED")]
    )
    assert report["summary"] == {
        "requirements": 1,
        "passed": 0,
        "unverified": 1,
        "coverage": 0.0,
        "verified": False,
        "collection_errors": 0,
    }
