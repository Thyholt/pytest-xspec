"""Build and render the public requirement report."""

import json
from collections.abc import Mapping, Sequence
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


class _OptionalScope(TypedDict, total=False):
    scope: SelectionScope


class Report(_OptionalScope):
    requirements: dict[str, RequirementResult]
    summary: Summary


def build_report(
    requirements: Mapping[str, Sequence[str]],
    outcomes: Mapping[str, str | None],
    collection_errors: int,
    *,
    scope: SelectionScope | None = None,
    interrupted: bool = False,
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

    count = len(results)
    passed = sum(result["status"] == "PASSED" for result in results.values())

    report: Report = {
        "requirements": results,
        "summary": {
            "requirements": count,
            "passed": passed,
            "unverified": count - passed,
            "coverage": passed / count * 100 if count else 0.0,
            "verified": passed == count and collection_errors == 0 and not interrupted,
            "collection_errors": collection_errors,
        },
    }

    if interrupted:
        report["summary"]["interrupted"] = True

    if scope is not None:
        report["scope"] = scope

    return report


def write_json(report: Report, path: Path) -> None:
    try:
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except OSError as error:
        raise pytest.UsageError(f"Cannot write xspec JSON report {path}: {error}") from error


def write_terminal(report: Report, terminal: TerminalReporter) -> None:
    red = not report["summary"]["verified"]
    terminal.write_sep("=", "xspec", red=red, green=not red)

    if "scope" in report:
        scope = report["scope"]
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

    width = max([len("Requirement"), *(len(identifier) for identifier in report["requirements"])])
    terminal.write_line(f"{'Requirement':<{width}}  {'Status':<10}  Tests", red=red, green=not red)

    for identifier, result in report["requirements"].items():
        terminal.write_line(
            f"{identifier:<{width}}  {result['status']:<10}  {len(result['tests'])}",
            red=red,
            green=not red,
        )

    for label, field in (
        ("Requirements", "requirements"),
        ("Passed", "passed"),
        ("Unverified", "unverified"),
    ):
        terminal.write_line(f"{label}: {report['summary'][field]}", red=red, green=not red)

    terminal.write_line(f"Coverage: {report['summary']['coverage']:.1f}%", red=red, green=not red)

    if report["summary"]["collection_errors"]:
        terminal.write_line(
            f"Collection errors: {report['summary']['collection_errors']}", red=red, green=not red
        )

    if report["summary"].get("interrupted"):
        terminal.write_line("Execution interrupted", red=True)
