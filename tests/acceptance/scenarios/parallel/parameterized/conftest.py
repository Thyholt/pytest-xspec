import sys
from pathlib import Path

import pytest


def pytest_sessionstart(session: pytest.Session) -> None:
    writer = "worker" if hasattr(session.config, "workerinput") else "controller"

    def record_report_write(event: str, args: tuple[object, ...]) -> None:
        if event == "open" and args[:2] == ("report.json", "w"):
            with Path("report-writers.txt").open("a", encoding="utf-8") as log:
                log.write(f"{writer}\n")

    sys.addaudithook(record_report_write)
