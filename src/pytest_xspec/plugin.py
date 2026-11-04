"""Pytest entry point for executable requirement verification."""

from collections.abc import Generator, Sequence
from pathlib import Path

import pytest
from _pytest.terminal import TerminalReporter

from pytest_xspec.collector import requirement_ids
from pytest_xspec.config import load_requirements
from pytest_xspec.execution import ExecutionResults
from pytest_xspec.outcomes import phase_outcome
from pytest_xspec.reporting import (
    ExecutionStatus,
    Report,
    SelectionScope,
    build_report,
    write_json,
    write_terminal,
)
from pytest_xspec.xdist import CollectionSnapshot, WorkerCoordinator


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("xspec")
    group.addoption("--xspec-report", action="store_true", help="Print requirement verification")
    group.addoption("--xspec-strict", action="store_true", help="Fail on unverified requirements")
    group.addoption("--xspec-json", metavar="PATH", help="Write requirement verification as JSON")
    group.addoption(
        "--xspec-select",
        action="append",
        default=[],
        metavar="ID",
        help="Select tests linked to an exact requirement ID (repeat for a union)",
    )

    parser.addini("xspec", "Requirement IDs, one per line (pytest.ini only)", "linelist")


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "xspec(id): associate a test with a declared requirement")
    plugin = RequirementPlugin(config)
    config.pluginmanager.register(plugin, "xspec-results")
    config.pluginmanager.register(plugin.workers, "xspec-workers")


class RequirementPlugin:
    def __init__(self, config: pytest.Config) -> None:
        self.config = config
        self.requirements: dict[str, list[str]] = {
            identifier: [] for identifier in load_requirements(config)
        }
        self.selected_requirements: list[str] = list(
            dict.fromkeys(config.getoption("xspec_select"))
        )
        for identifier in self.selected_requirements:
            if identifier not in self.requirements:
                raise pytest.UsageError(f"Unknown selected xspec requirement ID {identifier!r}")

        self.scope: SelectionScope | None = None
        if self.selected_requirements:
            self.scope = {
                "selected_requirements": self.selected_requirements,
                "collection_paths": (
                    ["."]
                    if config.args_source is pytest.Config.ArgsSource.INVOCATION_DIR
                    else list(config.args)
                ),
                "keyword_expression": config.getoption("keyword"),
                "marker_expression": config.getoption("markexpr"),
                "collect_only": config.getoption("collectonly"),
            }

        self.results = ExecutionResults()
        self.execution = ExecutionStatus()
        self.collection_error: str | None = None
        self._collected_nodeid = pytest.StashKey[str]()
        self.workers = WorkerCoordinator(config, self)

    @pytest.hookimpl(wrapper=True, tryfirst=True)
    def pytest_collection_modifyitems(self, items: list[pytest.Item]) -> Generator[None]:
        try:
            self._collect_requirements(items)
        except pytest.UsageError as error:
            self.collection_error = str(error)
            raise

        yield

        if self.selected_requirements:
            self._select_requirements(items)

    def _collect_requirements(self, items: Sequence[pytest.Item]) -> None:
        for item in items:
            item.stash[self._collected_nodeid] = item.nodeid
            identifiers = requirement_ids(item, self.requirements)
            if not identifiers or not self.results.collect(item.nodeid):
                continue

            for identifier in identifiers:
                self.requirements[identifier].append(item.nodeid)

    def original_nodeid(self, item: pytest.Item) -> str:
        return item.stash.get(self._collected_nodeid, item.nodeid)

    def _select_requirements(self, items: list[pytest.Item]) -> None:
        selected_nodeids = {
            nodeid
            for identifier in self.selected_requirements
            for nodeid in self.requirements[identifier]
        }
        deselected = [item for item in items if self.original_nodeid(item) not in selected_nodeids]
        items[:] = [item for item in items if self.original_nodeid(item) in selected_nodeids]
        if deselected:
            self.config.hook.pytest_deselected(items=deselected)

    def pytest_deselected(self, items: Sequence[pytest.Item]) -> None:
        for item in items:
            nodeid = self.original_nodeid(item)
            self.results.deselect(nodeid)

    def pytest_collectreport(self, report: pytest.CollectReport) -> None:
        if report.failed:
            self.execution.collection_errors.add(report.nodeid)

    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        nodeid, worker = self.workers.execution_identity(report)
        outcome = phase_outcome(
            report.when,
            report.outcome,
            wasxfail=hasattr(report, "wasxfail"),
            longrepr=report.longrepr,
        )
        self.results.record(nodeid, report.when, outcome, worker=worker)

    def collection_snapshot(self) -> CollectionSnapshot:
        return {
            "requirements": {
                identifier: list(nodeids) for identifier, nodeids in self.requirements.items()
            },
            "deselected": self.results.deselected,
            "error": self.collection_error,
        }

    def include_collection(self, collection: CollectionSnapshot) -> None:
        deselected = set(collection["deselected"])
        for identifier, nodeids in collection["requirements"].items():
            known = set(self.requirements[identifier])
            self.requirements[identifier].extend(
                nodeid for nodeid in nodeids if nodeid not in known
            )
            for nodeid in nodeids:
                self.results.collect(nodeid)
                if nodeid in deselected:
                    self.results.deselect(nodeid)

    def interrupt(self) -> None:
        self.execution.interrupted = True

    def pytest_internalerror(self) -> None:
        self.interrupt()

    def pytest_keyboard_interrupt(self) -> None:
        self.interrupt()

    def report(self) -> Report:
        return build_report(
            self.requirements,
            self.results.outcomes(),
            self.execution,
            scope=self.scope,
        )

    def pytest_sessionfinish(self, session: pytest.Session) -> None:
        if self.workers.is_worker:
            return

        report = self.report()

        path = self.config.getoption("xspec_json")
        if path:
            write_json(report, Path(path))

        if not self.config.getoption("xspec_strict") or report["summary"]["verified"]:
            return

        if session.exitstatus in (pytest.ExitCode.OK, pytest.ExitCode.NO_TESTS_COLLECTED):
            session.exitstatus = pytest.ExitCode.TESTS_FAILED

    def pytest_terminal_summary(self, terminalreporter: TerminalReporter) -> None:
        if self.workers.is_worker:
            return

        report_requested = self.config.getoption("xspec_report") or self.config.getoption(
            "xspec_strict"
        )
        if report_requested:
            write_terminal(self.report(), terminalreporter)
