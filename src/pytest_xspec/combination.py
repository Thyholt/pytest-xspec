"""Derive verification conclusions from separate, validated run reports."""

from collections.abc import Sequence

from pytest_xspec.outcomes import aggregate
from pytest_xspec.reporting import CombinedReport, CombinedRequirement, Report, build_summary


def combine_reports(runs: Sequence[Report]) -> CombinedReport:
    if not runs:
        raise ValueError("At least one run report is required")

    _validate_runs(runs)
    requirements = {
        identifier: _combine_requirement(runs, identifier) for identifier in runs[0]["requirements"]
    }

    return {
        "runs": list(runs),
        "requirements": requirements,
        "summary": build_summary(
            (requirement["status"] for requirement in requirements.values()),
            collection_errors=sum(run["summary"]["collection_errors"] for run in runs),
            interrupted=any(run["summary"].get("interrupted", False) for run in runs),
        ),
    }


def _validate_runs(runs: Sequence[Report]) -> None:
    inventory = runs[0]["requirements"]
    seen: set[str] = set()
    for run in runs:
        run_id = run["run_id"]
        if run_id in seen:
            raise ValueError(f"Duplicate run ID {run_id!r}")

        seen.add(run_id)
        if run["requirements"].keys() != inventory.keys():
            difference = sorted(run["requirements"].keys() ^ inventory.keys())
            raise ValueError(
                f"Run {run_id!r} has a different requirement inventory: {difference!r}"
            )


def _combine_requirement(runs: Sequence[Report], identifier: str) -> CombinedRequirement:
    observations: dict[str, set[str]] = {}
    for run in runs:
        for test in run["requirements"][identifier]["tests"]:
            observations.setdefault(test["nodeid"], set()).add(test["outcome"])

    outcomes = (
        aggregate(outcomes - {"DESELECTED"} or outcomes) for outcomes in observations.values()
    )
    return {"status": aggregate(outcomes)}


def combined_test_counts(report: CombinedReport) -> dict[str, int]:
    return {
        identifier: len(
            {
                test["nodeid"]
                for run in report["runs"]
                for test in run["requirements"][identifier]["tests"]
            }
        )
        for identifier in report["requirements"]
    }
