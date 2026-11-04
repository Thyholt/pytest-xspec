"""Only the controller may publish the invocation's report and strict verdict."""

from pathlib import Path

import pytest
from _pytest.terminal import TerminalReporter

from pytest_xspec import plugin
from pytest_xspec.reporting import Report


@pytest.mark.parametrize("worker", [False, True], ids=["controller", "worker"])
def test_only_the_controller_publishes_reports_and_applies_strict_mode(
    pytestconfig: pytest.Config,
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
    worker: bool,
) -> None:
    written: list[tuple[Report, Path]] = []
    rendered: list[Report] = []

    def write_json(report: Report, path: Path) -> None:
        written.append((report, path))

    def write_terminal(report: Report, _terminal: TerminalReporter) -> None:
        rendered.append(report)

    monkeypatch.setattr(plugin, "write_json", write_json)
    monkeypatch.setattr(plugin, "write_terminal", write_terminal)
    monkeypatch.setattr(plugin, "load_requirements", lambda _config: ["REQ-001"])
    monkeypatch.setattr(pytestconfig.option, "xspec_json", "report.json")
    monkeypatch.setattr(pytestconfig.option, "xspec_strict", True)
    monkeypatch.setattr(request.session, "exitstatus", pytest.ExitCode.OK)
    if worker:
        monkeypatch.setattr(pytestconfig, "workerinput", {}, raising=False)
    else:
        monkeypatch.delattr(pytestconfig, "workerinput", raising=False)

    results = plugin.RequirementPlugin(pytestconfig)

    results.pytest_sessionfinish(request.session)
    results.pytest_terminal_summary(TerminalReporter(pytestconfig))

    assert [path for _, path in written] == ([] if worker else [Path("report.json")])
    assert rendered == [report for report, _ in written]
    assert request.session.exitstatus == (
        pytest.ExitCode.OK if worker else pytest.ExitCode.TESTS_FAILED
    )
