"""Report validation rejects malformed or contradictory evidence before combination."""

from copy import deepcopy

import pytest

from pytest_xspec.report_input import validate_report


def valid_summary() -> dict[str, object]:
    return {
        "requirements": 1,
        "passed": 1,
        "unverified": 0,
        "coverage": 100.0,
        "verified": True,
        "collection_errors": 0,
    }


def valid_report() -> dict[str, object]:
    return {
        "run_id": " run / æøå : 1 ",
        "requirements": {
            "REQ-001": {
                "status": "PASSED",
                "tests": [{"nodeid": "test_behavior.py::test_first", "outcome": "PASSED"}],
            }
        },
        "summary": valid_summary(),
    }


def test_valid_report_is_preserved_without_normalizing_opaque_identity() -> None:
    report = valid_report()

    validated = validate_report(report)

    assert validated == report
    assert validated["run_id"] == " run / æøå : 1 "


@pytest.mark.parametrize("value", [None, [], "report", 1])
def test_report_must_be_an_object(value: object) -> None:
    with pytest.raises(ValueError, match="object"):
        validate_report(value)


def test_unlabeled_report_explains_the_required_producer_option() -> None:
    report = valid_report()
    del report["run_id"]

    with pytest.raises(ValueError, match="--xspec-run-id"):
        validate_report(report)


@pytest.mark.parametrize("run_id", [None, 1, "", " \t\n"])
def test_run_identity_requires_a_nonblank_string(run_id: object) -> None:
    report = valid_report()
    report["run_id"] = run_id

    with pytest.raises(ValueError, match="run_id"):
        validate_report(report)


@pytest.mark.parametrize("field", ["requirements", "summary"])
def test_required_report_fields_cannot_be_omitted(field: str) -> None:
    report = valid_report()
    del report[field]

    with pytest.raises(ValueError, match=field):
        validate_report(report)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("requirements", []),
        ("requirements", {1: {}}),
        ("summary", []),
        ("scope", None),
    ],
)
def test_report_fields_require_their_declared_shapes(field: str, value: object) -> None:
    report = valid_report()
    report[field] = value

    with pytest.raises(ValueError, match=field):
        validate_report(report)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("status", "FAILED"),
        ("status", None),
        ("tests", {}),
        ("tests", [None]),
        ("tests", [{"nodeid": 1, "outcome": "PASSED"}]),
        ("tests", [{"nodeid": "test_behavior.py::test_first", "outcome": "MISSING"}]),
        ("tests", [{"nodeid": "test_behavior.py::test_first", "outcome": "UNKNOWN"}]),
        ("tests", [{"nodeid": "test_behavior.py::test_first"}]),
    ],
)
def test_requirement_contents_must_be_well_formed_and_consistent(field: str, value: object) -> None:
    report = valid_report()
    requirement: dict[str, object] = {
        "status": "PASSED",
        "tests": [{"nodeid": "test_behavior.py::test_first", "outcome": "PASSED"}],
    }
    requirement[field] = value
    report["requirements"] = {"REQ-001": requirement}

    with pytest.raises(ValueError, match="REQ-001"):
        validate_report(report)


def test_duplicate_nodeids_within_a_requirement_are_rejected() -> None:
    report = valid_report()
    report["requirements"] = {
        "REQ-001": {
            "status": "PASSED",
            "tests": [
                {"nodeid": "test_behavior.py::test_first", "outcome": "PASSED"},
                {"nodeid": "test_behavior.py::test_first", "outcome": "PASSED"},
            ],
        }
    }

    with pytest.raises(ValueError, match=r"Duplicate.*test_behavior\.py::test_first"):
        validate_report(report)


@pytest.mark.parametrize("outcome", ["FAILED", "DESELECTED"])
def test_shared_test_cannot_have_different_outcomes_within_one_run(outcome: str) -> None:
    report = valid_report()
    report["requirements"] = {
        "REQ-001": {
            "status": "PASSED",
            "tests": [{"nodeid": "test_behavior.py::test_first", "outcome": "PASSED"}],
        },
        "REQ-002": {
            "status": outcome,
            "tests": [{"nodeid": "test_behavior.py::test_first", "outcome": outcome}],
        },
    }

    with pytest.raises(ValueError, match=r"Inconsistent.*test_behavior\.py::test_first"):
        validate_report(report)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("requirements", True),
        ("requirements", 1.0),
        ("passed", -1),
        ("passed", 0),
        ("unverified", 1),
        ("coverage", True),
        ("coverage", "100"),
        ("coverage", float("nan")),
        ("coverage", float("inf")),
        ("coverage", 50.0),
        ("verified", 1),
        ("verified", False),
        ("collection_errors", -1),
        ("collection_errors", True),
        ("interrupted", "true"),
    ],
)
def test_summary_fields_reject_wrong_types_and_inconsistent_values(
    field: str, value: object
) -> None:
    report = valid_report()
    summary = valid_summary()
    summary[field] = value
    report["summary"] = summary

    with pytest.raises(ValueError, match=field):
        validate_report(report)


@pytest.mark.parametrize(
    "field", ["requirements", "passed", "unverified", "coverage", "verified", "collection_errors"]
)
def test_summary_fields_are_required(field: str) -> None:
    report = valid_report()
    summary = valid_summary()
    del summary[field]
    report["summary"] = summary

    with pytest.raises(ValueError, match=field):
        validate_report(report)


@pytest.mark.parametrize(("problem", "value"), [("collection_errors", 1), ("interrupted", True)])
def test_execution_problems_allow_full_coverage_but_require_a_false_verdict(
    problem: str, value: object
) -> None:
    report = valid_report()
    summary = valid_summary()
    summary[problem] = value
    summary["verified"] = False
    report["summary"] = summary

    validated = validate_report(report)

    assert validated == report


@pytest.mark.parametrize(
    "outcome", ["ERROR", "FAILED", "XPASSED", "XFAILED", "SKIPPED", "DESELECTED"]
)
def test_valid_unverified_outcomes_are_accepted(outcome: str) -> None:
    report = valid_report()
    report["requirements"] = {
        "REQ-001": {
            "status": outcome,
            "tests": [{"nodeid": "test_behavior.py::test_first", "outcome": outcome}],
        }
    }
    report["summary"] = {
        "requirements": 1,
        "passed": 0,
        "unverified": 1,
        "coverage": 0.0,
        "verified": False,
        "collection_errors": 0,
    }

    validated = validate_report(report)

    assert validated == report


def test_a_missing_requirement_has_no_test_observations() -> None:
    report = valid_report()
    report["requirements"] = {"REQ-001": {"status": "MISSING", "tests": []}}
    report["summary"] = {
        "requirements": 1,
        "passed": 0,
        "unverified": 1,
        "coverage": 0.0,
        "verified": False,
        "collection_errors": 0,
    }

    validated = validate_report(report)

    assert validated == report


def test_zero_requirements_can_be_verified_at_zero_coverage() -> None:
    report = valid_report()
    report["requirements"] = {}
    report["summary"] = {
        "requirements": 0,
        "passed": 0,
        "unverified": 0,
        "coverage": 0.0,
        "verified": True,
        "collection_errors": 0,
    }

    validated = validate_report(report)

    assert validated == report


def test_valid_scope_and_shared_test_observations_are_preserved() -> None:
    report = valid_report()
    report["requirements"] = {
        "REQ-002": {
            "status": "PASSED",
            "tests": [{"nodeid": "test_behavior.py::test_first", "outcome": "PASSED"}],
        },
        "REQ-001": {
            "status": "PASSED",
            "tests": [{"nodeid": "test_behavior.py::test_first", "outcome": "PASSED"}],
        },
    }
    report["summary"] = {
        "requirements": 2,
        "passed": 2,
        "unverified": 0,
        "coverage": 100.0,
        "verified": True,
        "collection_errors": 0,
    }
    report["scope"] = {
        "selected_requirements": ["REQ-001", "REQ-002"],
        "collection_paths": ["tests", "other/test_behavior.py::test_other"],
        "keyword_expression": "first",
        "marker_expression": "xspec",
        "collect_only": False,
    }

    validated = validate_report(report)

    assert validated == report
    assert list(validated["requirements"]) == ["REQ-002", "REQ-001"]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("selected_requirements", "REQ-001"),
        ("selected_requirements", [1]),
        ("selected_requirements", ["UNKNOWN"]),
        ("selected_requirements", ["REQ-001", "REQ-001"]),
        ("collection_paths", [None]),
        ("keyword_expression", None),
        ("marker_expression", []),
        ("collect_only", 0),
    ],
)
def test_scope_fields_require_valid_selection_metadata(field: str, value: object) -> None:
    report = valid_report()
    scope: dict[str, object] = {
        "selected_requirements": ["REQ-001"],
        "collection_paths": ["."],
        "keyword_expression": "",
        "marker_expression": "",
        "collect_only": False,
    }
    scope[field] = value
    report["scope"] = scope

    with pytest.raises(ValueError, match=field):
        validate_report(report)


def test_validation_preserves_extra_metadata_and_omitted_fields() -> None:
    report: dict[str, object] = {
        "run_id": " run-a ",
        "metadata": {"device": "bench-a"},
        "requirements": {
            "REQ-001": {
                "status": "PASSED",
                "description": "First requirement",
                "tests": [{"nodeid": "test_first", "outcome": "PASSED", "duration": 0.25}],
            }
        },
        "summary": {**valid_summary(), "coverage": 100, "duration": 0.25},
    }
    original = deepcopy(report)

    validated = validate_report(report)

    assert validated == original
    assert type(validated["summary"]["coverage"]) is int
