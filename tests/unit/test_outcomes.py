"""Phase edge cases use values, without mocking pytest's execution machinery."""

import pytest

from pytest_xspec.outcomes import phase_outcome


@pytest.mark.parametrize("when", ["setup", "teardown"])
def test_successful_fixture_phases_do_not_override_the_test_verdict(when: str) -> None:
    outcome = phase_outcome(when, "passed")

    assert outcome is None


@pytest.mark.parametrize("when", ["setup", "teardown"])
def test_fixture_failures_are_errors_even_with_xpass_text(when: str) -> None:
    diagnostic = "[XPASS(strict)] fixture diagnostic"

    outcome = phase_outcome(when, "failed", longrepr=diagnostic)

    assert outcome == "ERROR"


def test_a_strict_unexpected_pass_has_the_same_outcome_as_a_non_strict_one() -> None:
    diagnostic = "[XPASS(strict)] known issue"

    outcome = phase_outcome("call", "failed", longrepr=diagnostic)

    assert outcome == "XPASSED"


@pytest.mark.parametrize("when", ["setup", "call", "teardown"])
def test_rerun_reports_are_attempt_boundaries_not_passes(when: str) -> None:
    outcome = phase_outcome(when, "rerun")

    assert outcome == "RERUN"
