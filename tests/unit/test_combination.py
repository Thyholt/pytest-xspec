"""Combination resolves observations without changing the source reports."""

from copy import deepcopy

import pytest

from pytest_xspec.combination import combine_reports, combined_test_counts
from pytest_xspec.reporting import ExecutionStatus, Report, build_report, build_summary


def make_run(run_id: str, tests: list[tuple[str, str]]) -> Report:
    report = build_report(
        {"REQ-001": [nodeid for nodeid, _ in tests]}, dict(tests), ExecutionStatus()
    )
    report["run_id"] = run_id
    return report


@pytest.mark.parametrize(
    ("first_outcome", "second_outcome", "expected_status"),
    [
        pytest.param("PASSED", "DESELECTED", "PASSED", id="complementary-selection"),
        pytest.param("DESELECTED", "DESELECTED", "DESELECTED", id="never-selected"),
        pytest.param("PASSED", "SKIPPED", "SKIPPED", id="skip-is-not-deselection"),
        pytest.param("PASSED", "XFAILED", "XFAILED", id="expected-failure"),
        pytest.param("PASSED", "XPASSED", "XPASSED", id="unexpected-pass"),
        pytest.param("PASSED", "FAILED", "FAILED", id="failure"),
        pytest.param("PASSED", "ERROR", "ERROR", id="error"),
        pytest.param("SKIPPED", "XFAILED", "XFAILED", id="xfail-over-skip"),
        pytest.param("XFAILED", "XPASSED", "XPASSED", id="xpass-over-xfail"),
        pytest.param("XPASSED", "FAILED", "FAILED", id="failure-over-xpass"),
        pytest.param("FAILED", "ERROR", "ERROR", id="error-over-failure"),
    ],
)
def test_same_test_observations_resolve_independently_of_run_order(
    first_outcome: str, second_outcome: str, expected_status: str
) -> None:
    first = make_run("first", [("test_behavior.py::test_behavior", first_outcome)])
    second = make_run("second", [("test_behavior.py::test_behavior", second_outcome)])

    forward = combine_reports([first, second])
    reversed_runs = combine_reports([second, first])

    assert (
        forward["requirements"]
        == reversed_runs["requirements"]
        == {"REQ-001": {"status": expected_status}}
    )


def test_a_deselected_distinct_test_is_not_hidden_by_another_tests_pass() -> None:
    first = make_run("first", [("test_first", "PASSED"), ("test_second", "DESELECTED")])
    second = make_run("second", [("test_first", "PASSED")])

    report = combine_reports([first, second])

    assert report["requirements"] == {"REQ-001": {"status": "DESELECTED"}}
    assert report["summary"]["verified"] is False


def test_a_test_missing_from_one_collection_can_be_verified_by_another() -> None:
    first = make_run("first", [])
    second = make_run("second", [("test_behavior", "PASSED")])

    report = combine_reports([first, second])

    assert report["requirements"] == {"REQ-001": {"status": "PASSED"}}
    assert report["summary"]["verified"] is True


def test_no_associations_in_any_run_leave_the_requirement_missing() -> None:
    runs = [make_run("first", []), make_run("second", [])]

    report = combine_reports(runs)

    assert report["requirements"] == {"REQ-001": {"status": "MISSING"}}
    assert report["summary"]["verified"] is False


def test_combination_preserves_source_reports_and_scope_without_mutating_them() -> None:
    first = make_run("first", [("test_first", "PASSED"), ("test_second", "DESELECTED")])
    first["scope"] = {
        "selected_requirements": ["REQ-001"],
        "collection_paths": ["tests"],
        "keyword_expression": "first",
        "marker_expression": "",
        "collect_only": False,
    }
    second = make_run("second", [("test_first", "DESELECTED"), ("test_second", "PASSED")])
    runs = [second, first]
    original = deepcopy(runs)

    report = combine_reports(runs)

    assert runs == original
    assert report["runs"] == original
    assert report["requirements"] == {"REQ-001": {"status": "PASSED"}}


def test_combined_counts_distinguish_parameterized_ids_and_shared_associations() -> None:
    first = make_run("first", [("test_behavior[first]", "PASSED")])
    first["requirements"]["REQ-002"] = deepcopy(first["requirements"]["REQ-001"])
    first["summary"] = build_summary(["PASSED", "PASSED"])
    second = make_run(
        "second", [("test_behavior[first]", "PASSED"), ("test_behavior[second]", "PASSED")]
    )
    second["requirements"]["REQ-002"] = {"status": "MISSING", "tests": []}
    second["summary"] = build_summary(["PASSED", "MISSING"])
    report = combine_reports([first, second])

    counts = combined_test_counts(report)

    assert counts == {"REQ-001": 2, "REQ-002": 1}


def test_first_inventory_order_is_preserved_when_later_inventory_order_differs() -> None:
    first = make_run("first", [("test_behavior", "PASSED")])
    first["requirements"] = {
        "REQ-002": {"status": "MISSING", "tests": []},
        **first["requirements"],
    }
    first["summary"] = build_summary(["MISSING", "PASSED"])
    second = make_run("second", [("test_behavior", "PASSED")])
    second["requirements"]["REQ-002"] = {"status": "MISSING", "tests": []}
    second["summary"] = build_summary(["PASSED", "MISSING"])

    report = combine_reports([first, second])

    assert list(report["requirements"]) == ["REQ-002", "REQ-001"]
    assert report["summary"] == {
        "requirements": 2,
        "passed": 1,
        "unverified": 1,
        "coverage": 50.0,
        "verified": False,
        "collection_errors": 0,
    }


def test_collection_errors_are_summed_instead_of_deduplicated_between_runs() -> None:
    first = make_run("first", [("test_behavior", "PASSED")])
    second = make_run("second", [("test_behavior", "PASSED")])
    first["summary"]["collection_errors"] = 2
    first["summary"]["verified"] = False
    second["summary"]["collection_errors"] = 3
    second["summary"]["verified"] = False

    report = combine_reports([first, second])

    assert report["summary"]["collection_errors"] == 5
    assert report["summary"]["coverage"] == 100.0
    assert report["summary"]["verified"] is False


@pytest.mark.parametrize("interrupted_index", [0, 1])
def test_one_interrupted_run_invalidates_the_combined_verdict(interrupted_index: int) -> None:
    runs = [make_run("first", [("test", "PASSED")]), make_run("second", [("test", "PASSED")])]
    runs[interrupted_index]["summary"]["interrupted"] = True
    runs[interrupted_index]["summary"]["verified"] = False

    report = combine_reports(runs)

    assert report["summary"].get("interrupted") is True
    assert report["summary"]["verified"] is False


def test_empty_inventories_have_a_successful_verdict_and_zero_coverage() -> None:
    first: Report = {"run_id": "empty", **build_report({}, {}, ExecutionStatus())}

    report = combine_reports([first])
    counts = combined_test_counts(report)

    assert report["requirements"] == {}
    assert counts == {}
    assert report["summary"] == {
        "requirements": 0,
        "passed": 0,
        "unverified": 0,
        "coverage": 0.0,
        "verified": True,
        "collection_errors": 0,
    }


def test_combination_requires_at_least_one_run() -> None:
    with pytest.raises(ValueError, match=r"(?i)at least one"):
        combine_reports([])


def test_duplicate_run_ids_are_rejected() -> None:
    runs = [make_run("same", []), make_run("same", [])]

    with pytest.raises(ValueError, match=r"(?i)duplicate.*same"):
        combine_reports(runs)


def test_different_requirement_inventories_identify_the_run_and_difference() -> None:
    first = make_run("first", [])
    second = make_run("different", [])
    second["requirements"] = {"REQ-002": {"status": "MISSING", "tests": []}}

    with pytest.raises(ValueError, match="inventory") as error:
        combine_reports([first, second])

    assert "different" in str(error.value)
    assert "REQ-001" in str(error.value)
    assert "REQ-002" in str(error.value)
