"""Observe execution evidence in a real pytest run's terminal output."""

import pytest


class ObservedRun:
    def __init__(self, result: pytest.RunResult) -> None:
        self._result = result
        self._stdout = "\n".join(result.outlines)

    @property
    def reruns(self) -> int:
        return self._result.parseoutcomes().get("rerun", 0)

    @property
    def passed(self) -> int:
        return self._result.parseoutcomes().get("passed", 0)

    @property
    def requirement_reports(self) -> int:
        return self._stdout.count(" xspec ")
