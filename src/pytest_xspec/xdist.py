"""Exchange collection evidence and coordinate pytest-xdist workers."""

from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING, Protocol, TypedDict, cast

import pytest

if TYPE_CHECKING:
    from execnet import Channel
    from xdist.workermanage import WorkerController


class CollectionSnapshot(TypedDict):
    requirements: dict[str, list[str]]
    deselected: list[str]
    error: str | None


class WorkerCollection(CollectionSnapshot):
    nodeids: dict[str, str]


class WorkerConfig(Protocol):
    workerinput: dict[str, object]


class WorkerHost(Protocol):
    def collection_snapshot(self) -> CollectionSnapshot: ...

    def original_nodeid(self, item: pytest.Item) -> str: ...

    def include_collection(self, collection: CollectionSnapshot) -> None: ...

    def interrupt(self) -> None: ...


class WorkerCoordinator:
    def __init__(self, config: pytest.Config, host: WorkerHost) -> None:
        self._config = config
        self._host = host
        self._nodeids: dict[str, str] = {}
        self.is_worker = hasattr(config, "workerinput")

    def execution_identity(self, report: pytest.TestReport) -> tuple[str, object]:
        return self._nodeids.get(report.nodeid, report.nodeid), getattr(report, "node", None)

    @pytest.hookimpl(optionalhook=True)
    def pytest_configure_node(self, node: "WorkerController") -> None:
        node.workerinput["xspec_channel"] = node.gateway.newchannel()

    # Send collection evidence before xdist announces readiness to run tests.
    @pytest.hookimpl(tryfirst=True)
    def pytest_collection_finish(self, session: pytest.Session) -> None:
        if not self.is_worker:
            return

        self._nodeids.update(_capture_execution_ids(session.items, self._host.original_nodeid))
        collection: WorkerCollection = {
            **self._host.collection_snapshot(),
            "nodeids": self._nodeids,
        }
        self._send_collection(collection)

    def _send_collection(self, collection: WorkerCollection) -> None:
        workerinput = cast(WorkerConfig, self._config).workerinput
        channel = cast("Channel", workerinput["xspec_channel"])
        channel.send(collection)
        channel.close()

    @pytest.hookimpl(optionalhook=True)
    def pytest_xdist_node_collection_finished(self, node: "WorkerController") -> None:
        collection = _receive_collection(node)
        if collection["error"] is not None:
            self._host.interrupt()
            raise pytest.UsageError(collection["error"])

        self._nodeids.update(collection["nodeids"])
        self._host.include_collection(collection)

    @pytest.hookimpl(optionalhook=True)
    def pytest_testnodedown(self, node: "WorkerController", error: object | None) -> None:
        if error is not None or node.workeroutput["exitstatus"] in (
            pytest.ExitCode.INTERRUPTED,
            pytest.ExitCode.INTERNAL_ERROR,
            pytest.ExitCode.USAGE_ERROR,
        ):
            self._host.interrupt()


def _capture_execution_ids(
    items: Sequence[pytest.Item], original_nodeid: Callable[[pytest.Item], str]
) -> dict[str, str]:
    original_nodeids = {}
    for item in items:
        original = original_nodeid(item)
        if item.nodeid != original:
            original_nodeids[item.nodeid] = original

    return original_nodeids


def _receive_collection(node: "WorkerController") -> WorkerCollection:
    channel = cast("Channel", node.workerinput["xspec_channel"])
    return cast(WorkerCollection, channel.receive())
