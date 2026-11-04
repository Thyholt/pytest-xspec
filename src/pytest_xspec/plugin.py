"""Pytest entry point for executable requirement verification."""

from collections.abc import Generator, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, TypedDict, cast

import pytest
from _pytest.terminal import TerminalReporter

from pytest_xspec.collector import requirement_ids
from pytest_xspec.config import load_requirements
from pytest_xspec.outcomes import aggregate, phase_outcome
from pytest_xspec.reporting import (
    ExecutionStatus,
    Report,
    SelectionScope,
    build_report,
    write_json,
    write_terminal,
)

if TYPE_CHECKING:
    from execnet import Channel
    from xdist.workermanage import WorkerController

COLLECTED_NODEID = pytest.StashKey[str]()


class WorkerCollection(TypedDict):
    requirements: dict[str, list[str]]
    deselected: list[str]
    error: str | None
    nodeids: dict[str, str]


class WorkerConfig(Protocol):
    workerinput: dict[str, object]


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
    config.pluginmanager.register(RequirementPlugin(config), "xspec-results")


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

        self.outcomes: dict[str, str | None] = {}
        self.execution = ExecutionStatus()
        self.is_worker = hasattr(config, "workerinput")
        self.completed: set[str] = set()
        self.collection_error: str | None = None
        self.collected_nodeids: dict[str, str] = {}

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
            item.stash[COLLECTED_NODEID] = item.nodeid
            identifiers = requirement_ids(item, self.requirements)
            if not identifiers or item.nodeid in self.outcomes:
                continue

            self.outcomes[item.nodeid] = None
            for identifier in identifiers:
                self.requirements[identifier].append(item.nodeid)

    def _select_requirements(self, items: list[pytest.Item]) -> None:
        selected_nodeids = {
            nodeid
            for identifier in self.selected_requirements
            for nodeid in self.requirements[identifier]
        }
        deselected = [
            item for item in items if item.stash[COLLECTED_NODEID] not in selected_nodeids
        ]
        items[:] = [item for item in items if item.stash[COLLECTED_NODEID] in selected_nodeids]
        if deselected:
            self.config.hook.pytest_deselected(items=deselected)

    def pytest_deselected(self, items: Sequence[pytest.Item]) -> None:
        for item in items:
            nodeid = item.stash.get(COLLECTED_NODEID, item.nodeid)
            if nodeid in self.outcomes:
                self.outcomes[nodeid] = "DESELECTED"

    def pytest_collectreport(self, report: pytest.CollectReport) -> None:
        if report.failed:
            self.execution.collection_errors.add(report.nodeid)

    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        nodeid = self.collected_nodeids.get(report.nodeid, report.nodeid)
        if report.when == "teardown":
            self.completed.add(nodeid)

        if nodeid not in self.outcomes:
            return

        outcome = phase_outcome(
            report.when,
            report.outcome,
            wasxfail=hasattr(report, "wasxfail"),
            longrepr=report.longrepr,
        )
        if outcome is None:
            return

        previous = self.outcomes[nodeid]
        self.outcomes[nodeid] = aggregate(
            [previous, outcome] if previous is not None else [outcome]
        )

    @pytest.hookimpl(optionalhook=True)
    def pytest_configure_node(self, node: "WorkerController") -> None:
        node.workerinput["xspec_channel"] = node.gateway.newchannel()

    @pytest.hookimpl(tryfirst=True)
    def pytest_collection_finish(self, session: pytest.Session) -> None:
        if not self.is_worker:
            return

        # loadgroup appends group names to execution IDs after associations
        # are collected. Keep the original IDs for selection and reporting.
        for item in session.items:
            original = item.stash.get(COLLECTED_NODEID, item.nodeid)
            if item.nodeid != original:
                self.collected_nodeids[item.nodeid] = original

        workerinput = cast(WorkerConfig, self.config).workerinput
        channel = cast("Channel", workerinput["xspec_channel"])
        # Send before xdist announces collection completion, so even a crash
        # in the first fixture cannot lose collected or deselected identities.
        channel.send(
            {
                "requirements": self.requirements,
                "deselected": [
                    nodeid for nodeid, status in self.outcomes.items() if status == "DESELECTED"
                ],
                "error": self.collection_error,
                "nodeids": self.collected_nodeids,
            }
        )
        channel.close()

    @pytest.hookimpl(optionalhook=True)
    def pytest_xdist_node_collection_finished(self, node: "WorkerController") -> None:
        channel = cast("Channel", node.workerinput["xspec_channel"])
        # The collection event follows the payload. Receive on the controller
        # thread so merging cannot race with another worker or a test report.
        collection = cast(WorkerCollection, channel.receive())
        if collection["error"] is not None:
            self.execution.interrupted = True
            raise pytest.UsageError(collection["error"])

        self.collected_nodeids.update(collection["nodeids"])
        deselected = set(collection["deselected"])
        for identifier, nodeids in collection["requirements"].items():
            known = set(self.requirements[identifier])
            self.requirements[identifier].extend(
                nodeid for nodeid in nodeids if nodeid not in known
            )
            for nodeid in nodeids:
                self.outcomes.setdefault(nodeid, "DESELECTED" if nodeid in deselected else None)

    @pytest.hookimpl(optionalhook=True)
    def pytest_testnodedown(self, node: "WorkerController", error: object | None) -> None:
        if error is not None or node.workeroutput["exitstatus"] in (
            pytest.ExitCode.INTERRUPTED,
            pytest.ExitCode.INTERNAL_ERROR,
            pytest.ExitCode.USAGE_ERROR,
        ):
            self.execution.interrupted = True

    def pytest_internalerror(self) -> None:
        self.execution.interrupted = True

    def pytest_keyboard_interrupt(self) -> None:
        self.execution.interrupted = True

    def report(self) -> Report:
        outcomes = {
            nodeid: "SKIPPED" if status == "PASSED" and nodeid not in self.completed else status
            for nodeid, status in self.outcomes.items()
        }
        return build_report(
            self.requirements,
            outcomes,
            self.execution,
            scope=self.scope,
        )

    def pytest_sessionfinish(self, session: pytest.Session) -> None:
        if self.is_worker:
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
        if self.is_worker:
            return

        report_requested = self.config.getoption("xspec_report") or self.config.getoption(
            "xspec_strict"
        )
        if report_requested:
            write_terminal(self.report(), terminalreporter)
