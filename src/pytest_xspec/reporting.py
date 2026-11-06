"""Build and render the public requirement report."""

import json
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import TypedDict

import pytest
from _pytest.terminal import TerminalReporter

from pytest_xspec.outcomes import aggregate


class TestResult(TypedDict):
    nodeid: str
    outcome: str


class RequirementResult(TypedDict):
    status: str
    tests: list[TestResult]


class _OptionalInterruption(TypedDict, total=False):
    interrupted: bool


class Summary(_OptionalInterruption):
    requirements: int
    passed: int
    unverified: int
    coverage: float
    verified: bool
    collection_errors: int


class SelectionScope(TypedDict):
    selected_requirements: list[str]
    collection_paths: list[str]
    keyword_expression: str
    marker_expression: str
    collect_only: bool


class ReportMetadata(TypedDict, total=False):
    scope: SelectionScope
    run_id: str


class Report(ReportMetadata):
    requirements: dict[str, RequirementResult]
    summary: Summary


class CombinedRequirement(TypedDict):
    status: str


class CombinedReport(TypedDict):
    runs: list[Report]
    requirements: dict[str, CombinedRequirement]
    summary: Summary


@dataclass
class ExecutionStatus:
    collection_errors: set[str] = field(default_factory=set)
    interrupted: bool = False


def build_report(
    requirements: Mapping[str, Sequence[str]],
    outcomes: Mapping[str, str | None],
    execution: ExecutionStatus,
    *,
    metadata: ReportMetadata | None = None,
) -> Report:
    results: dict[str, RequirementResult] = {}

    for identifier, nodeids in requirements.items():
        tests: list[TestResult] = [
            {"nodeid": nodeid, "outcome": outcomes[nodeid] or "SKIPPED"} for nodeid in nodeids
        ]
        results[identifier] = {
            "status": aggregate(test["outcome"] for test in tests),
            "tests": tests,
        }

    report: Report = {
        "requirements": results,
        "summary": build_summary(
            (result["status"] for result in results.values()),
            collection_errors=len(execution.collection_errors),
            interrupted=execution.interrupted,
        ),
    }

    return {**report, **(metadata or {})}


def build_summary(
    statuses: Iterable[str], *, collection_errors: int = 0, interrupted: bool = False
) -> Summary:
    outcomes = list(statuses)
    count = len(outcomes)
    passed = outcomes.count("PASSED")
    summary: Summary = {
        "requirements": count,
        "passed": passed,
        "unverified": count - passed,
        "coverage": passed / count * 100 if count else 0.0,
        "verified": passed == count and not collection_errors and not interrupted,
        "collection_errors": collection_errors,
    }
    if interrupted:
        summary["interrupted"] = True

    return summary


def write_json(report: Report | CombinedReport, path: Path) -> None:
    try:
        content = (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        path.write_bytes(content)
    except (OSError, UnicodeError) as error:
        raise pytest.UsageError(f"Cannot write xspec JSON report {path}: {error}") from error


def write_terminal(report: Report, terminal: TerminalReporter) -> None:
    red = not report["summary"]["verified"]
    terminal.write_sep("=", "xspec", red=red, green=not red)

    if "scope" in report:
        _write_scope(report["scope"], terminal, red=red)

    _write_requirements(report["requirements"], terminal, red=red)
    _write_summary(report["summary"], terminal, red=red)


def _write_scope(scope: SelectionScope, terminal: TerminalReporter, *, red: bool) -> None:
    for label, value in (
        (
            "Selected requirements",
            json.dumps(scope["selected_requirements"], ensure_ascii=False),
        ),
        ("Collection paths", json.dumps(scope["collection_paths"], ensure_ascii=False)),
        ("Keyword filter", scope["keyword_expression"] or "(none)"),
        ("Marker filter", scope["marker_expression"] or "(none)"),
        ("Discovery only", "yes" if scope["collect_only"] else "no"),
    ):
        terminal.write_line(f"{label}: {value}", red=red, green=not red)


def _write_requirements(
    requirements: Mapping[str, RequirementResult], terminal: TerminalReporter, *, red: bool
) -> None:
    rows = [
        (identifier, result["status"], len(result["tests"]))
        for identifier, result in requirements.items()
    ]
    for line in requirement_lines(rows):
        terminal.write_line(line, red=red, green=not red)


def _write_summary(summary: Summary, terminal: TerminalReporter, *, red: bool) -> None:
    for line in summary_lines(summary):
        terminal.write_line(line, red=red, green=not red)


def requirement_lines(rows: Sequence[tuple[str, str, int]]) -> Iterator[str]:
    width = max([len("Requirement"), *(len(identifier) for identifier, _, _ in rows)])
    yield f"{'Requirement':<{width}}  {'Status':<10}  Tests"
    for identifier, status, count in rows:
        yield f"{identifier:<{width}}  {status:<10}  {count}"


def summary_lines(summary: Summary) -> Iterator[str]:
    for label, key in (
        ("Requirements", "requirements"),
        ("Passed", "passed"),
        ("Unverified", "unverified"),
    ):
        yield f"{label}: {summary[key]}"

    yield f"Coverage: {summary['coverage']:.1f}%"

    if summary["collection_errors"]:
        yield f"Collection errors: {summary['collection_errors']}"

    if summary.get("interrupted"):
        yield "Execution interrupted"
