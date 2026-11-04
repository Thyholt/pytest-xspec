"""Run observations retain evidence of execution without exposing stdout plumbing."""

import pytest

from tests.acceptance.observations import ObservedRun
from tests.acceptance.test_rerunfailures import completed_phases, shows_in_order


@pytest.mark.parametrize(
    ("events", "matches"),
    [
        pytest.param(("attempt 1", "attempt 2"), True, id="ordered"),
        pytest.param(("attempt 2", "attempt 1"), False, id="reversed"),
        pytest.param(("attempt 1", "attempt 3"), False, id="missing"),
        pytest.param(("attempt 1", "attempt 1"), False, id="repeated"),
        pytest.param(("attempt *",), False, id="literal-text"),
    ],
)
def test_execution_events_must_appear_in_order(events: tuple[str, ...], matches: bool) -> None:
    result = pytest.RunResult(pytest.ExitCode.OK, ["attempt 1", "attempt 2"], [], 0.0)

    found = shows_in_order(result, *events)

    assert found is matches


def test_completed_phases_belong_to_the_requested_attempt() -> None:
    result = pytest.RunResult(
        pytest.ExitCode.INTERRUPTED,
        [
            "attempt 1 teardown completed",
            "attempt 2 call completed",
            "attempt 2 teardown started",
        ],
        [],
        0.0,
    )

    first = completed_phases(result, attempt=1)
    second = completed_phases(result, attempt=2)
    missing = completed_phases(result, attempt=3)

    assert first == ("teardown",)
    assert second == ("call",)
    assert missing == ()


def test_counts_include_duplicate_requirement_reports() -> None:
    result = pytest.RunResult(
        pytest.ExitCode.OK,
        ["=== xspec ===", "=== xspec ===", "=== 2 passed, 3 rerun in 0.01s ==="],
        [],
        0.0,
    )

    observed = ObservedRun(result)

    assert observed.passed == 2
    assert observed.reruns == 3
    assert observed.requirement_reports == 2


def test_missing_execution_evidence_is_not_success() -> None:
    result = pytest.RunResult(pytest.ExitCode.USAGE_ERROR, [], ["invalid option"], 0.0)

    observed = ObservedRun(result)

    with pytest.raises(ValueError):  # noqa: PT011 - pytest's exception wording is not our contract
        _ = observed.reruns

    assert observed.requirement_reports == 0
    assert completed_phases(result, attempt=1) == ()
    assert shows_in_order(result, "attempt 1") is False
