"""Resolve final attempts independently before combining worker evidence."""

from dataclasses import dataclass

from pytest_xspec.outcomes import aggregate


@dataclass
class Attempt:
    status: str | None = None
    completed: bool = False
    retrying: bool = False

    def record(self, phase: str | None, status: str | None) -> None:
        if status == "RERUN":
            self.status = None
            self.completed = False
            self.retrying = True
            return

        if phase == "setup":
            self.retrying = False

        # Rerunfailures can publish remaining phases of the discarded attempt.
        # They cannot provide evidence for the retry, even if it never reports.
        if self.retrying and phase in ("call", "teardown"):
            return

        if status is not None:
            self.status = aggregate([self.status, status] if self.status is not None else [status])

        if phase == "teardown":
            self.completed = True

    def outcome(self) -> str:
        if self.status is None:
            return "SKIPPED"

        if self.status == "PASSED" and not self.completed:
            return "SKIPPED"

        return self.status


class ExecutionResults:
    def __init__(self) -> None:
        self._tests: dict[str, dict[object, Attempt]] = {}
        self._deselected: set[str] = set()

    def collect(self, nodeid: str) -> bool:
        if nodeid in self._tests:
            return False

        self._tests[nodeid] = {}
        return True

    def deselect(self, nodeid: str) -> None:
        if nodeid in self._tests:
            self._deselected.add(nodeid)

    @property
    def deselected(self) -> list[str]:
        return [nodeid for nodeid in self._tests if nodeid in self._deselected]

    def record(
        self, nodeid: str, phase: str | None, status: str | None, *, worker: object = None
    ) -> None:
        if nodeid not in self._tests:
            return

        attempt = self._tests[nodeid].setdefault(worker, Attempt())
        attempt.record(phase, status)

    def outcomes(self) -> dict[str, str | None]:
        outcomes: dict[str, str | None] = {
            nodeid: "DESELECTED" if nodeid in self._deselected else None for nodeid in self._tests
        }
        for nodeid, workers in self._tests.items():
            if not workers:
                continue

            outcomes[nodeid] = aggregate(attempt.outcome() for attempt in workers.values())

        return outcomes
