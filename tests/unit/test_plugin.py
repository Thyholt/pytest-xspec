"""Only the controller may publish the invocation's report and strict verdict."""

from pathlib import Path

import pytest

from pytest_xspec import plugin
from pytest_xspec.reporting import Report


@pytest.mark.parametrize("worker", [False, True], ids=["controller", "worker"])
def test_only_the_controller_writes_json_and_applies_strict_mode(
    pytestconfig: pytest.Config,
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
    worker: bool,
) -> None:
    written: list[tuple[Report, Path]] = []

    def write_json(report: Report, path: Path) -> None:
        written.append((report, path))

    monkeypatch.setattr(plugin, "write_json", write_json)
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

    assert [path for _, path in written] == ([] if worker else [Path("report.json")])
    assert request.session.exitstatus == (
        pytest.ExitCode.OK if worker else pytest.ExitCode.TESTS_FAILED
    )
