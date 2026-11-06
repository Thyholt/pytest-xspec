"""Validate single-run JSON evidence before it participates in combination."""

from typing import cast

from pytest_xspec import report_fields as fields
from pytest_xspec.outcomes import PRECEDENCE, aggregate
from pytest_xspec.report_fields import InvalidReport
from pytest_xspec.reporting import Report, build_summary


def validate_report(value: object) -> Report:
    report = fields.object_value(value, "report")
    if "runs" in report:
        raise InvalidReport("Expected a single-run report, not a combined report with runs")

    if "run_id" not in report:
        raise InvalidReport("Missing run_id: produce the report with --xspec-run-id")

    run_id = fields.string(report["run_id"], "run_id")
    if not run_id.strip():
        raise InvalidReport("run_id must not be empty or whitespace-only")

    requirements = fields.object_value(report.get("requirements"), "requirements")
    statuses = _validate_requirements(requirements)
    _validate_summary(report.get("summary"), statuses)
    if "scope" in report:
        _validate_scope(report["scope"], requirements)

    # Every required field and optional field in Report has been validated above.
    return cast(Report, report)


def _validate_requirements(requirements: dict[str, object]) -> list[str]:
    shared_outcomes: dict[str, str] = {}
    return [
        _validate_requirement(value, f"requirements[{identifier!r}]", shared_outcomes)
        for identifier, value in requirements.items()
    ]


def _validate_requirement(value: object, field: str, shared_outcomes: dict[str, str]) -> str:
    requirement = fields.object_value(value, field)
    status = fields.string(requirement.get("status"), f"{field}.status")
    outcomes = _validate_observations(requirement.get("tests"), field, shared_outcomes)
    if status != aggregate(outcomes.values()):
        raise InvalidReport(f"{field}.status is inconsistent with its test outcomes")

    return status


def _validate_observations(
    value: object, field: str, shared_outcomes: dict[str, str]
) -> dict[str, str]:
    observations = fields.array(value, f"{field}.tests")
    outcomes: dict[str, str] = {}
    for index, observation in enumerate(observations):
        nodeid, outcome = _test_observation(observation, f"{field}.tests[{index}]")
        if nodeid in outcomes:
            raise InvalidReport(f"Duplicate nodeid {nodeid!r} in {field}.tests")

        previous_outcome = shared_outcomes.setdefault(nodeid, outcome)
        if previous_outcome != outcome:
            raise InvalidReport(f"Inconsistent outcome for shared nodeid {nodeid!r} in {field}")

        outcomes[nodeid] = outcome

    return outcomes


def _test_observation(value: object, field: str) -> tuple[str, str]:
    test = fields.object_value(value, field)
    nodeid = fields.string(test.get("nodeid"), f"{field}.nodeid")
    outcome = fields.string(test.get("outcome"), f"{field}.outcome")
    if outcome not in PRECEDENCE:
        raise InvalidReport(f"{field}.outcome has unknown test outcome {outcome!r}")

    return nodeid, outcome


def _validate_summary(value: object, statuses: list[str]) -> None:
    summary = fields.object_value(value, "summary")
    for field in ("requirements", "passed", "unverified", "collection_errors"):
        fields.nonnegative_integer(summary.get(field), f"summary.{field}")

    fields.percentage(summary.get("coverage"), "summary.coverage")
    fields.boolean(summary.get("verified"), "summary.verified")
    interrupted = fields.boolean(summary.get("interrupted", False), "summary.interrupted")
    collection_errors = fields.nonnegative_integer(
        summary["collection_errors"], "summary.collection_errors"
    )
    expected = build_summary(statuses, collection_errors=collection_errors, interrupted=interrupted)
    for field, expected_value in expected.items():
        if summary.get(field) != expected_value:
            raise InvalidReport(f"summary.{field} is inconsistent with the report observations")


def _validate_scope(value: object, requirements: dict[str, object]) -> None:
    scope = fields.object_value(value, "scope")
    selected = fields.string_list(scope.get("selected_requirements"), "scope.selected_requirements")
    if len(selected) != len(set(selected)) or any(item not in requirements for item in selected):
        raise InvalidReport(
            "scope.selected_requirements must contain unique declared requirement IDs"
        )

    fields.string_list(scope.get("collection_paths"), "scope.collection_paths")
    fields.string(scope.get("keyword_expression"), "scope.keyword_expression")
    fields.string(scope.get("marker_expression"), "scope.marker_expression")
    fields.boolean(scope.get("collect_only"), "scope.collect_only")
