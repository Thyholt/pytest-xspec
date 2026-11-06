"""Generate real input reports and invoke the public combination command."""

import json
import sys
from pathlib import Path
from typing import TypedDict, cast

import pytest

from tests.acceptance.types import AcceptanceReport, ReportSummary


class RunReport(AcceptanceReport):
    run_id: str


class CombinedRequirement(TypedDict):
    status: str


class CombinedReport(TypedDict):
    runs: list[RunReport]
    requirements: dict[str, CombinedRequirement]
    summary: ReportSummary


def simulate_outcome(monkeypatch: pytest.MonkeyPatch, outcome: str) -> None:
    """Set test_first_behavior's outcome for subsequent runs of the outcomes scenario."""
    monkeypatch.setenv("XSPEC_SCENARIO_OUTCOME", outcome)


def record_run(
    project: pytest.Pytester,
    run_id: str,
    *options: str,
    expected_exit: pytest.ExitCode = pytest.ExitCode.OK,
) -> RunReport:
    result = project.runpytest_subprocess(
        f"--xspec-run-id={run_id}", f"--xspec-json={run_id}.json", *options
    )
    assert result.ret == expected_exit, result.stdout.str() + result.stderr.str()
    path = project.path / f"{run_id}.json"
    assert path.is_file(), "The source run must produce its report before combination"
    return cast(RunReport, json.loads(path.read_text(encoding="utf-8")))


def combine(project: pytest.Pytester, *arguments: str) -> pytest.RunResult:
    return project.run(sys.executable, "-m", "pytest_xspec", "combine", *arguments)


def read_combined(path: Path) -> CombinedReport:
    assert path.is_file(), "Combination must produce the requested report"
    return cast(CombinedReport, json.loads(path.read_text(encoding="utf-8")))
