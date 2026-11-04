"""Translate execution phases into requirement verification outcomes."""

from collections.abc import Iterable

PRECEDENCE = {
    status: rank
    for rank, status in enumerate(
        ("PASSED", "DESELECTED", "SKIPPED", "XFAILED", "XPASSED", "FAILED", "ERROR")
    )
}


def phase_outcome(
    when: str | None, outcome: str, *, wasxfail: bool = False, longrepr: object = None
) -> str | None:
    if outcome == "rerun":
        return "RERUN"

    if outcome == "failed":
        return _failure_outcome(when, longrepr)

    if outcome == "skipped":
        return "XFAILED" if wasxfail else "SKIPPED"

    if when == "call":
        return "XPASSED" if wasxfail else "PASSED"

    return None


def _failure_outcome(when: str | None, longrepr: object) -> str:
    if when != "call":
        return "ERROR"

    if isinstance(longrepr, str) and longrepr.startswith("[XPASS(strict)] "):
        return "XPASSED"

    return "FAILED"


def aggregate(outcomes: Iterable[str]) -> str:
    return max(outcomes, key=PRECEDENCE.__getitem__, default="MISSING")
